import importlib.util
import json
import os
import time

import click

from .analyzer import BenchmarkAnalyzer
from .utils.gh_client import GitHubClient
from .utils.provisioner import RepoProvisioner


class BenchmarkRunner:
    """Orchestrates the execution of a benchmark test on real GitHub."""

    def __init__(self, workspace_dir, repo="owner/repo"):
        self.workspace_dir = workspace_dir
        self.repo = repo
        self.gh_client = GitHubClient(repo=repo)
        self.provisioner = RepoProvisioner(self.gh_client)
        self.analyzer = BenchmarkAnalyzer(workspace_dir, repo=repo)

    def run(self, workflow_id, scenario_id):
        """Triggers a GitHub workflow and waits for completion."""
        workflow_path = os.path.join(
            self.workspace_dir, "src/benchmark/workflows", workflow_id, "workflow.yml"
        )
        scenario_path = os.path.join(self.workspace_dir, "src/benchmark/scenarios", scenario_id)

        if not os.path.exists(workflow_path) or not os.path.exists(scenario_path):
            return {"error": f"Workflow ({workflow_id}) or scenario ({scenario_id}) not found."}

        # 1. Load scenario
        scenario = self._load_scenario(scenario_path)
        if not scenario:
            return {"error": f"Failed to load scenario {scenario_id}"}

        try:
            # 2. Provision Infrastructure
            # Scenarios can define a target branch for their files
            target_branch = getattr(scenario, "branch", None)
            click.echo(f"Provisioning repository {self.repo}...")
            self.provisioner.provision(
                workflow_path, scenario.get_required_files(), branch=target_branch
            )

            # 3. Prepare Dynamic State (Issues/PRs)
            click.echo(f"Preparing repository state for scenario '{scenario_id}'...")
            scenario.setup_state(self.gh_client)

            # 4. Trigger Workflow via GitHub CLI
            scenario_event = scenario.get_event()
            # Sleep to ensure all provisioned files are visible to GraphQL/Actions
            import time

            time.sleep(3)
            click.echo(f"Triggering workflow '{workflow_id}' on GitHub...")
            start_time = time.time()
            trigger_success, trigger_error = self._trigger_event(scenario_event)
            if not trigger_success:
                return {"error": f"Failed to trigger GitHub event: {trigger_error}"}

            # 5. Poll for completion
            click.echo("Waiting for workflow run to complete...")
            # Use the workflow folder name for polling
            workflow_filename = f"{workflow_id}.yml"
            run_id = self._poll_for_completion(workflow_filename, start_time)
            if not run_id:
                return {"error": "Timed out waiting for workflow run or could not find it."}

            # 6. Fetch logs
            click.echo(f"Fetching logs for run {run_id}...")
            stdout, stderr = self._get_workflow_logs(run_id)

            run_result = {"stdout": stdout, "stderr": stderr, "exit_code": 0}

            analysis = self.analyzer.analyze(run_result, scenario_path)

            return {
                "workflow": workflow_id,
                "scenario": scenario_id,
                "analysis": analysis,
                "run_id": run_id,
                "message": f"Successfully executed and analyzed run {run_id}.",
            }
        finally:
            click.echo(f"Cleaning up repository state for scenario '{scenario_id}'...")
            scenario.teardown_state(self.gh_client)

    def _trigger_event(self, scenario_event):
        """Triggers a GitHub event (Issue/PR/Comment) to start the workflow."""
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
            if "https://github.com/" in stdout:
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
            if "https://github.com/" in stdout:
                return True, None
            return False, stderr
        elif event_type == "issue_comment":
            # For comments, we need an existing issue or PR.
            # Scenarios using this should have created it in setup_state.
            # We look for the most recent PR/Issue if number isn't provided.
            target_number = data.get("number")
            if not target_number:
                # Try to find the PR created in setup_state
                stdout, _ = self.gh_client.run_gh(
                    ["pr", "list", "--limit", "1", "--json", "number"]
                )
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
                if stderr and "error" in stderr.lower():
                    return False, stderr
                return True, None
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
                    return attr(self.workspace_dir)
        return None

    def _poll_for_completion(self, workflow_filename, start_time, timeout=600):
        """Polls the GitHub API until the workflow run finishes."""
        elapsed = 0
        while elapsed < timeout:
            stdout, _ = self.gh_client.run_gh(
                [
                    "run",
                    "list",
                    "--workflow",
                    workflow_filename,
                    "--json",
                    "databaseId,status,conclusion,createdAt",
                    "--limit",
                    "1",
                ]
            )

            if stdout:
                runs = json.loads(stdout)
                if runs:
                    run = runs[0]
                    if run["status"] == "completed":
                        return run["databaseId"]

            time.sleep(3)
            elapsed += 3

        return None

    def _get_workflow_logs(self, run_id):
        """Retrieves the full logs for a specific workflow run."""
        stdout, stderr = self.gh_client.run_gh(["run", "view", str(run_id), "--log"])
        return stdout, stderr
