import importlib.util
import json
import os
import random
import re
import string
import time

import click

from .analyzer import BenchmarkAnalyzer
from .utils.gh_client import GitHubClient
from .utils.provisioner import RepoProvisioner


class BenchmarkRunner:
    """Orchestrates the execution of a benchmark test on real GitHub."""

    def __init__(self, workspace_dir, repo_prefix="benchmark-run"):
        self.workspace_dir = workspace_dir
        self.repo_prefix = repo_prefix
        self.repo = self._generate_repo_name(repo_prefix)
        self.gh_client = GitHubClient(repo=self.repo)
        self.provisioner = RepoProvisioner(self.gh_client)
        self.analyzer = BenchmarkAnalyzer(workspace_dir, repo=self.repo)

    def _generate_repo_name(self, prefix):
        """Generates a unique repo name based on a prefix."""
        # If prefix contains a slash, assume it's owner/prefix
        if "/" in prefix:
            owner, name_prefix = prefix.split("/", 1)
        else:
            # Try to get current user from gh CLI
            stdout, _ = GitHubClient().run_gh(["api", "user", "-q", ".login"], use_repo=False)
            if stdout:
                owner = stdout.strip()
            else:
                owner = None
            name_prefix = prefix

        random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        repo_name = f"{name_prefix}-{random_suffix}"

        if owner:
            return f"{owner}/{repo_name}"
        return repo_name

    def run(self, workflow_id, scenario_id, cleanup=True):
        """Triggers a GitHub workflow and waits for completion."""
        workflow_dir = os.path.join(self.workspace_dir, "src/benchmark/workflows", workflow_id)
        scenario_path = os.path.join(self.workspace_dir, "src/benchmark/scenarios", scenario_id)

        if not os.path.exists(workflow_dir) or not os.path.exists(scenario_path):
            return {"error": f"Workflow dir ({workflow_id}) or scenario ({scenario_id}) not found."}

        # 1. Load scenario
        scenario = self._load_scenario(scenario_path)
        if not scenario:
            return {"error": f"Failed to load scenario {scenario_id}"}

        try:
            # 2. Discover and Validate Requirements (Secrets/Vars)
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

            if missing:
                return {"error": "Missing required environment variables:\n  - " + "\n  - ".join(missing)}

            # 3. Provision Infrastructure
            target_branch = getattr(scenario, "branch", None)
            template_repo = scenario.get_template_repo()

            click.echo(f"Provisioning repository {self.repo}...")
            self.provisioner.provision(
                workflow_dir,
                scenario.get_required_files(),
                branch=target_branch,
                template_repo=template_repo,
                secrets=secrets,
                variables=variables,
            )

            # 4. Prepare Dynamic State (Issues/PRs)
            click.echo(f"Preparing repository state for scenario '{scenario_id}'...")
            scenario.setup_state(self.gh_client)

            # 5. Trigger Workflow via GitHub CLI
            time.sleep(1)
            click.echo(f"Triggering workflow '{workflow_id}' on GitHub...")
            start_time = time.time()
            trigger_success, trigger_error = self._trigger_event(scenario)
            if not trigger_success:
                return {"error": f"Failed to trigger GitHub event: {trigger_error}"}

            # 6. Poll for completion
            click.echo("Waiting for workflow run to start and complete...")
            run_id = self._wait_for_run(start_time)

            if not run_id:
                return {"error": "Timed out waiting for workflow run or could not find it."}

            # 7. Fetch logs
            click.echo(f"Fetching logs for run {run_id}...")
            stdout, stderr = self._get_workflow_logs(run_id)

            run_result = {"stdout": stdout, "stderr": stderr, "exit_code": 0}

            analysis = self.analyzer.analyze(run_result, scenario)

            result = {
                "workflow": workflow_id,
                "scenario": scenario_id,
                "analysis": analysis,
                "run_id": run_id,
                "repo": self.repo,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "message": f"Successfully executed and analyzed run {run_id}.",
            }

            self._save_run_locally(result, run_result)
            return result

        finally:
            if cleanup:
                click.echo(f"Cleaning up repository state for scenario '{scenario_id}'...")
                scenario.teardown_state(self.gh_client)
                # 8. Teardown entire repo
                self.provisioner.teardown()
            else:
                click.echo(click.style(f"SKIP CLEANUP: Repository {self.repo} remains active for debugging.", fg="yellow"))

    def _get_workflow_requirements(self, workflow_dir):
        """Scans workflow YAML files for 'secrets.NAME' and 'vars.NAME' patterns."""
        requirements = {"secrets": set(), "vars": set()}

        # Regex patterns for GitHub Actions syntax
        # Matches: ${{ secrets.NAME }} or ${{ vars.NAME }}
        secret_pattern = re.compile(r"\$\{\{\s*secrets\.(\w+)\s*\}\}")
        var_pattern = re.compile(r"\$\{\{\s*vars\.(\w+)\s*\}\}")

        if os.path.isdir(workflow_dir):
            files = [
                os.path.join(workflow_dir, f) for f in os.listdir(workflow_dir) if f.endswith(".yml") or f.endswith(".yaml")
            ]
        else:
            files = [workflow_dir]

        for file_path in files:
            if not os.path.exists(file_path):
                continue
            with open(file_path, "r") as f:
                content = f.read()

                # Find all secrets
                for match in secret_pattern.finditer(content):
                    requirements["secrets"].add(match.group(1))

                # Find all vars
                for match in var_pattern.finditer(content):
                    requirements["vars"].add(match.group(1))

        # Always ignore GITHUB_TOKEN as it's provided by GitHub
        if "GITHUB_TOKEN" in requirements["secrets"]:
            requirements["secrets"].remove("GITHUB_TOKEN")

        return requirements

    def _save_run_locally(self, result, run_result):
        """Saves run metadata and logs to the local 'runs/' directory."""
        runs_dir = os.path.join(self.workspace_dir, "runs", result["timestamp"].replace(":", "-"))
        os.makedirs(runs_dir, exist_ok=True)

        # Save metadata and analysis
        with open(os.path.join(runs_dir, "metadata.json"), "w") as f:
            json.dump(result, f, indent=4)

        # Save logs
        with open(os.path.join(runs_dir, "stdout.log"), "w") as f:
            f.write(run_result.get("stdout", ""))
        with open(os.path.join(runs_dir, "stderr.log"), "w") as f:
            f.write(run_result.get("stderr", ""))

        click.echo(f"Run results saved to: {runs_dir}")

    def _trigger_event(self, scenario):
        """Triggers a GitHub event (Issue/PR/Comment) to start the workflow."""
        scenario_event = scenario.get_event()
        event_type = scenario_event.get("event_type")
        data = scenario_event.get("data", {})

        if event_type == "issue":
            stdout, stderr = self.gh_client.run_gh(
                [
                    "issue",
                    "create",
                    "--title",
                    data.get("title", "Test Issue"),
                    "--body",
                    data.get("body", "Test Body"),
                ]
            )
            if stdout and "https://github.com/" in stdout:
                issue_number = stdout.strip().split("/")[-1]
                scenario.runtime_state["issue_number"] = int(issue_number)
                return True, None
            return False, stderr
        elif event_type == "pull_request":
            stdout, stderr = self.gh_client.run_gh(
                [
                    "pr",
                    "create",
                    "--title",
                    data.get("title", "Test PR"),
                    "--body",
                    data.get("body", "Test Body"),
                    "--head",
                    data.get("head", "main"),
                    "--base",
                    data.get("base", "main"),
                ]
            )
            if stdout and "https://github.com/" in stdout:
                pr_number = stdout.strip().split("/")[-1]
                scenario.runtime_state["pr_number"] = int(pr_number)
                return True, None
            return False, stderr
        elif event_type == "issue_comment":
            # For comments, we need an existing issue or PR.
            # Scenarios using this should have created it in setup_state.
            # We look for the most recent PR/Issue if number isn't provided.
            target_number = data.get("number")
            if not target_number:
                # Try to find the PR created in setup_state
                stdout, _ = self.gh_client.run_gh(["pr", "list", "--limit", "1", "--json", "number"])
                import json

                prs = json.loads(stdout) if stdout else []
                if prs:
                    target_number = prs[0]["number"]

            if target_number:
                stdout, stderr = self.gh_client.run_gh(
                    [
                        "pr",
                        "comment",
                        str(target_number),
                        "--body",
                        data.get("body", "/review"),
                    ]
                )
                if stdout and "https://github.com/" in stdout:
                    return True, None
                return False, stderr
            return False, "Could not find a target PR/Issue for the comment."

        return False, f"Unknown event type: {event_type}"

    def _load_scenario(self, scenario_path):
        """Loads a Python scenario class."""
        if not scenario_path.endswith(".py"):
            return None

        module_name = os.path.basename(scenario_path).replace(".py", "")
        spec = importlib.util.spec_from_file_location(module_name, scenario_path)
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
                    scenario_obj.runtime_state["repo"] = self.repo
                    return scenario_obj
        return None

    def _wait_for_run(self, start_time, timeout=600):
        """Waits for any workflow run to start after start_time and then wait for completion."""
        elapsed = 0
        interval = 5
        run_id = None
        from datetime import datetime, timezone

        # 1. Wait for run to appear
        while elapsed < 120:  # Wait up to 2 mins for it to appear
            stdout, _ = self.gh_client.run_gh(
                [
                    "run",
                    "list",
                    "--json",
                    "databaseId,status,conclusion,createdAt",
                    "--limit",
                    "5",
                ]
            )
            if stdout:
                try:
                    runs = json.loads(stdout)
                    for run in runs:
                        created_at = datetime.strptime(run["createdAt"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        if created_at.timestamp() > start_time - 30:
                            run_id = run["databaseId"]
                            click.echo(f"Found workflow run {run_id} (status: {run['status']})")
                            break
                except (json.JSONDecodeError, ValueError):
                    pass

            if run_id:
                break

            time.sleep(interval)
            elapsed += interval

        if not run_id:
            return None

        # 2. Wait for this specific run to complete
        elapsed = 0
        interval = 5
        while elapsed < timeout:
            stdout, _ = self.gh_client.run_gh(
                [
                    "run",
                    "view",
                    str(run_id),
                    "--json",
                    "status,conclusion",
                ]
            )
            if stdout:
                try:
                    run = json.loads(stdout)
                    if run["status"] == "completed":
                        return run_id
                except (json.JSONDecodeError, ValueError):
                    pass

            time.sleep(interval)
            elapsed += interval

        return None

    def _get_workflow_logs(self, run_id):
        """Retrieves the full logs for a specific workflow run."""
        stdout, stderr = self.gh_client.run_gh(["run", "view", str(run_id), "--log"])
        return stdout, stderr
