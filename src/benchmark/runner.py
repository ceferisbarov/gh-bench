import importlib.util
import json
import os
import random
import re
import string
import time
from datetime import datetime, timezone

import click
from tenacity import retry, retry_if_result, stop_after_attempt, wait_exponential

from .analyzer import BenchmarkAnalyzer
from .utils.gh_client import GitHubClient
from .utils.provisioner import RepoProvisioner
from .utils.types import AIProvider


class BenchmarkRunner:
    """Orchestrates the execution of a benchmark test on real GitHub."""

    def __init__(self, workspace_dir, repo_prefix="benchmark-run"):
        self.workspace_dir = workspace_dir
        self.repo_prefix = repo_prefix
        self.gh_client = GitHubClient()
        self.repo_name = self._generate_repo_name(repo_prefix)
        self.gh_client.repo_name = self.repo_name

        self.provisioner = RepoProvisioner(self.gh_client)
        self.analyzer = BenchmarkAnalyzer(workspace_dir, repo=self.repo_name)

    def _generate_repo_name(self, prefix):
        """Generates a unique repo name based on a prefix."""
        if "/" in prefix:
            owner, name_prefix = prefix.split("/", 1)
        else:
            try:
                owner = self.gh_client.gh.get_user().login
            except Exception:
                owner = None
            name_prefix = prefix

        random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        repo_name = f"{name_prefix}-{random_suffix}"

        if owner:
            return f"{owner}/{repo_name}"
        return repo_name

    def run(self, workflow_id, scenario_id, cleanup=True, unaligned=False):
        """Triggers a GitHub workflow and waits for completion."""
        workflow_dir = os.path.join(self.workspace_dir, "src/benchmark/workflows", workflow_id)
        scenario_path = self._find_scenario_path(scenario_id)

        if not os.path.exists(workflow_dir) or not scenario_path:
            return {"error": f"Workflow dir ({workflow_id}) or scenario ({scenario_id}) not found."}

        meta_path = os.path.join(workflow_dir, "metadata.json")
        workflow_meta = {}
        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                workflow_meta = json.load(f)

        scenario = self._load_scenario(scenario_path)
        if not scenario:
            return {"error": f"Failed to load scenario {scenario_id}"}

        try:
            if not unaligned:
                provider_error = self._validate_provider_requirements(workflow_meta)
                if provider_error:
                    return {"error": provider_error}

            requirements = self._get_workflow_requirements(workflow_dir)

            secrets = {}
            variables = {}
            missing = []

            for secret_name in requirements["secrets"]:
                val = os.environ.get(secret_name)
                if val:
                    secrets[secret_name] = val
                else:
                    missing.append(f"Secret: {secret_name}")

            for var_name in requirements["vars"]:
                val = os.environ.get(var_name)
                if val:
                    variables[var_name] = val
                else:
                    missing.append(f"Variable: {var_name}")

            if missing and not unaligned:
                return {"error": "Missing required environment variables:\n  - " + "\n  - ".join(missing)}

            target_branch = getattr(scenario, "branch", None)
            template_repo = scenario.get_template_repo()

            substitution_map = {}
            if unaligned:
                global_swaps_path = os.path.join(self.workspace_dir, "src/benchmark/config/adversarial_swaps.json")
                if os.path.exists(global_swaps_path):
                    with open(global_swaps_path, "r") as f:
                        substitution_map.update(json.load(f))

                swaps = workflow_meta.get("adversarial_swaps", {})
                substitution_map.update(swaps)

                tag = unaligned if isinstance(unaligned, str) else "mistral"
                for original in list(substitution_map.keys()):
                    replacement = substitution_map[original]
                    if "@" not in replacement:
                        substitution_map[original] = f"{replacement}@{tag}"

            click.echo(f"Provisioning repository {self.repo_name}...")
            self.provisioner.provision(
                workflow_dir,
                scenario.get_required_files(),
                branch=target_branch,
                template_repo=template_repo,
                secrets=secrets,
                variables=variables,
                substitution_map=substitution_map,
            )

            click.echo(f"Preparing repository state for scenario '{scenario_id}'...")
            scenario.setup_state(self.gh_client)

            timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            runs_dir = os.path.join(self.workspace_dir, "runs", timestamp.replace(":", "-"))
            os.makedirs(runs_dir, exist_ok=True)

            click.echo("Capturing context snapshot...")
            snapshot = self._capture_context_snapshot(scenario, workflow_dir)
            with open(os.path.join(runs_dir, "context_snapshot.json"), "w") as f:
                json.dump(snapshot, f, indent=4)

            click.echo(f"Triggering workflow '{workflow_id}' on GitHub...")
            start_time = datetime.now(timezone.utc).timestamp()
            expected_event = scenario.get_event().get("event_type")
            trigger_success, trigger_error = self._trigger_event(scenario)
            if not trigger_success:
                return {"error": f"Failed to trigger GitHub event: {trigger_error}"}

            click.echo("Waiting for workflow run to start and complete...")
            run_id = self._wait_for_run(start_time, expected_event=expected_event)

            if not run_id:
                return {"error": "Timed out waiting for workflow run or could not find it."}

            click.echo(f"Fetching logs for run {run_id}...")
            stdout, stderr = self._get_workflow_logs(run_id)

            run_result = {"stdout": stdout, "stderr": stderr, "exit_code": 0}

            analysis = self.analyzer.analyze(run_result, scenario)

            result = {
                "workflow": workflow_id,
                "scenario": scenario_id,
                "analysis": analysis,
                "run_id": run_id,
                "repo": self.repo_name,
                "timestamp": timestamp,
                "message": f"Successfully executed and analyzed run {run_id}.",
            }

            self._save_run_locally(result, run_result, runs_dir)
            return result

        finally:
            if cleanup:
                click.echo(f"Cleaning up repository state for scenario '{scenario_id}'...")
                scenario.teardown_state(self.gh_client)
                self.provisioner.teardown()
            else:
                msg = f"SKIP CLEANUP: Repository {self.repo_name} remains active for debugging."
                click.echo(click.style(msg, fg="yellow"))

    def _find_scenario_path(self, scenario_id):
        """Recursively searches for a scenario by its ID."""
        scenarios_dir = os.path.join(self.workspace_dir, "src/benchmark/scenarios")
        for root, dirs, files in os.walk(scenarios_dir):
            if scenario_id in dirs:
                path = os.path.join(root, scenario_id)
                if os.path.exists(os.path.join(path, "scenario.py")):
                    return path
            if f"{scenario_id}.py" in files:
                return os.path.join(root, f"{scenario_id}.py")

        # Direct path check as fallback
        if os.path.isabs(scenario_id) and os.path.exists(scenario_id):
            return scenario_id

        return None

    def _capture_context_snapshot(self, scenario, workflow_dir):
        """Captures the full context (files, event, meta) for diagnostic purposes."""
        repo = self.gh_client.repository

        files = {}
        try:
            tree = repo.get_git_tree(repo.default_branch, recursive=True)
            for item in tree.tree:
                if item.type == "blob":
                    valid_exts = [".ts", ".js", ".py", ".md", ".yml", ".yaml", ".json", ".txt"]
                    if any(item.path.endswith(ext) for ext in valid_exts):
                        content = repo.get_contents(item.path).decoded_content.decode("utf-8")
                        files[item.path] = content
        except Exception as e:
            files["error"] = str(e)

        workflow_contents = {}
        workflows_path = os.path.join(workflow_dir, "contents", ".github", "workflows")
        if os.path.isdir(workflows_path):
            for f in os.listdir(workflows_path):
                if f.endswith(".yml") or f.endswith(".yaml"):
                    with open(os.path.join(workflows_path, f), "r") as wf:
                        workflow_contents[f] = wf.read()

        return {
            "event": scenario.get_event(),
            "repo_files": files,
            "workflow_definitions": workflow_contents,
            "runtime_state": scenario.runtime_state,
        }

    def _get_workflow_requirements(self, workflow_dir):
        """Scans workflow YAML files for 'secrets.NAME' and 'vars.NAME' patterns."""
        requirements = {"secrets": set(), "vars": set()}
        secret_pattern = re.compile(r"secrets\.(\w+)")
        var_pattern = re.compile(r"vars\.(\w+)")
        workflows_path = os.path.join(workflow_dir, "contents", ".github", "workflows")
        files = []
        if os.path.isdir(workflows_path):
            files = [
                os.path.join(workflows_path, f)
                for f in os.listdir(workflows_path)
                if f.endswith(".yml") or f.endswith(".yaml")
            ]
        elif os.path.isdir(workflow_dir):
            files = [
                os.path.join(workflow_dir, f) for f in os.listdir(workflow_dir) if f.endswith(".yml") or f.endswith(".yaml")
            ]

        for file_path in files:
            if not os.path.exists(file_path):
                continue
            with open(file_path, "r") as f:
                content = f.read()
                for match in secret_pattern.finditer(content):
                    requirements["secrets"].add(match.group(1))
                for match in var_pattern.finditer(content):
                    requirements["vars"].add(match.group(1))

        if "GITHUB_TOKEN" in requirements["secrets"]:
            requirements["secrets"].remove("GITHUB_TOKEN")
        return requirements

    def _save_run_locally(self, result, run_result, runs_dir):
        """Saves run metadata and logs to the local 'runs/' directory."""
        with open(os.path.join(runs_dir, "metadata.json"), "w") as f:
            json.dump(result, f, indent=4)
        with open(os.path.join(runs_dir, "stdout.log"), "w") as f:
            f.write(run_result.get("stdout", ""))
        with open(os.path.join(runs_dir, "stderr.log"), "w") as f:
            f.write(run_result.get("stderr", ""))
        click.echo(f"Run results saved to: {runs_dir}")

    def _trigger_event(self, scenario):
        """Triggers the appropriate GitHub event using the GitHub API."""
        scenario_event = scenario.get_event()
        event_type = scenario_event.get("event_type")
        data = scenario_event.get("data", {})
        repo = self.gh_client.repository

        try:
            if event_type == "issues":
                issue = repo.create_issue(title=data.get("title", "Test Issue"), body=data.get("body", "Test Body"))
                scenario.runtime_state["issue_number"] = issue.number
                return True, None
            elif event_type == "pull_request":
                pr = repo.create_pull(
                    title=data.get("title", "Test PR"),
                    body=data.get("body", "Test Body"),
                    head=data.get("head", "main"),
                    base=data.get("base", "main"),
                )
                scenario.runtime_state["pr_number"] = pr.number
                return True, None
            elif event_type in ["issue_comment", "pull_request_review", "pull_request_review_comment"]:
                target_number = data.get("number")
                if not target_number:
                    prs = repo.get_pulls(state="open", sort="created", direction="desc")
                    if prs.totalCount > 0:
                        target_number = prs[0].number

                if target_number:
                    if event_type == "pull_request_review":
                        pr = repo.get_pull(target_number)
                        pr.create_review(body=data.get("body", "Looks good to me."), event="COMMENT")
                    else:
                        issue = repo.get_issue(target_number)
                        issue.create_comment(data.get("body", "/review"))
                    return True, None
                return False, "Could not find a target PR/Issue for the event."
            elif event_type == "workflow_dispatch":
                workflow = repo.get_workflow(data.get("workflow"))
                workflow.create_dispatch(repo.default_branch, data.get("inputs", {}))
                return True, None
        except Exception as e:
            return False, str(e)

        return False, f"Unknown event type: {event_type}"

    def _load_scenario(self, scenario_path):
        """Loads a Python scenario class."""
        if os.path.isdir(scenario_path):
            scenario_dir = scenario_path
            scenario_file = os.path.join(scenario_path, "scenario.py")
        else:
            scenario_dir = os.path.dirname(scenario_path)
            scenario_file = scenario_path

        if not os.path.exists(scenario_file) or not scenario_file.endswith(".py"):
            return None

        module_name = os.path.basename(scenario_file).replace(".py", "")
        spec = importlib.util.spec_from_file_location(module_name, scenario_file)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and attr_name != "AbstractScenario"
                    and "AbstractScenario" in [base.__name__ for base in attr.__mro__]
                ):
                    scenario_obj = attr(self.workspace_dir)
                    scenario_obj.scenario_dir = scenario_dir
                    scenario_obj.runtime_state["repo"] = self.repo_name
                    return scenario_obj
        return None

    @retry(
        retry=retry_if_result(lambda res: res is None),
        stop=stop_after_attempt(60),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _wait_for_run(self, start_time, expected_event=None):
        """Waits for all workflow runs to start after start_time and then wait for completion."""
        repo = self.gh_client.repository

        runs = repo.get_workflow_runs()
        relevant_runs = []
        count = 0
        for run in runs:
            if count >= 30:
                break
            if run.created_at.replace(tzinfo=timezone.utc).timestamp() > start_time - 30:
                relevant_runs.append(run)
            count += 1

        if not relevant_runs:
            return None

        # Check if a run for the expected event has appeared yet
        if expected_event:
            has_expected = any(run.event == expected_event for run in relevant_runs)
            if not has_expected:
                click.echo(f"Waiting for run with event '{expected_event}' to appear...")
                return None

        # Check if all relevant runs are completed
        for run in relevant_runs:
            if run.status != "completed":
                click.echo(f"Workflow run {run.id} ({run.name}) in progress (status: {run.status})...")
                # Trigger a retry until ALL are completed
                return None

        # All discovered runs are completed. Wait a short quiescence period to check for new ones
        # especially if they are triggered by side effects of completed runs.
        # We only do this if we haven't already returned once.
        if not hasattr(self, "_last_run_count") or self._last_run_count < len(relevant_runs):
            self._last_run_count = len(relevant_runs)
            click.echo("All discovered runs completed. Waiting for quiescence...")
            time.sleep(10)
            return None

        # Sort by creation time (ascending) to pick the original trigger
        relevant_runs.sort(key=lambda r: r.created_at)

        # Prefer non-skipped runs and those matching the expected event
        target_run = None
        if expected_event:
            for run in reversed(relevant_runs):  # Prefer newest if multiple match
                if run.conclusion != "skipped" and run.event == expected_event:
                    target_run = run
                    break

        if not target_run:
            for run in relevant_runs:
                if run.conclusion != "skipped":
                    target_run = run
                    break

        if not target_run:
            target_run = relevant_runs[0]

        # Reset last_run_count for next time
        if hasattr(self, "_last_run_count"):
            del self._last_run_count

        return target_run.id

    def _get_workflow_logs(self, run_id):
        """Retrieves the full logs for a specific workflow run."""
        # Note: Using gh CLI here because pygithub doesn't easily expose full logs in a single call
        stdout, stderr = self.gh_client.run_gh(["run", "view", str(run_id), "--log"])
        return stdout, stderr

    def _validate_provider_requirements(self, meta):
        """Ensures API keys for the specified provider are present in the environment."""
        provider = meta.get("provider")
        if not provider:
            return None
        provider_keys = {
            AIProvider.GOOGLE_GEMINI: [
                "GEMINI_API_KEY",
                "GEMINI_MODEL",
                "GEMINI_DEBUG",
            ],
            AIProvider.ANTHROPIC_CLAUDE: ["ANTHROPIC_API_KEY"],
            AIProvider.OPENAI_CODEX: ["OPENAI_API_KEY"],
            AIProvider.AMAZON_Q: ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
            AIProvider.GITHUB_COPILOT: ["COPILOT_GITHUB_TOKEN"],
            AIProvider.OPENROUTER: [
                "GEMINI_API_KEY",
                "GEMINI_MODEL",
                "GEMINI_DEBUG",
                "OPENROUTER_API_KEY",
                "ANTHROPIC_BASE_URL",
                "ANTHROPIC_AUTH_TOKEN",
            ],
        }
        required_keys = provider_keys.get(provider, [])
        missing = [key for key in required_keys if not os.environ.get(key)]
        if missing:
            return f"Provider '{provider}' requires the following API keys in your local environment: {', '.join(missing)}"
        return None
