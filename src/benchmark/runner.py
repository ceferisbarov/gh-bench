import os
import json
import yaml
import subprocess
import time
import importlib.util
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
        self.analyzer = BenchmarkAnalyzer()

    def run(self, workflow_id, scenario_id):
        """Triggers a GitHub workflow and waits for completion."""
        workflow_path = os.path.join(self.workspace_dir, "data/workflows", workflow_id, "workflow.yml")
        scenario_path = os.path.join(self.workspace_dir, "data/scenarios", scenario_id)
        
        if not os.path.exists(workflow_path) or not os.path.exists(scenario_path):
            return {"error": f"Workflow ({workflow_id}) or scenario ({scenario_id}) not found."}

        # 1. Load scenario
        scenario = self._load_scenario(scenario_path)
        if not scenario:
            return {"error": f"Failed to load scenario {scenario_id}"}
        
        try:
            # 2. Provision Infrastructure
            print(f"Provisioning repository {self.repo}...")
            self.provisioner.provision(workflow_path, scenario.get_required_files())

            # 3. Prepare Dynamic State (Issues/PRs)
            print(f"Preparing repository state for scenario '{scenario_id}'...")
            scenario.setup_state(self.gh_client)

            # 4. Trigger Workflow via GitHub CLI
            scenario_event = scenario.get_event()
            print(f"Triggering workflow '{workflow_id}' on GitHub...")
            start_time = time.time()
            trigger_result = self._trigger_event(scenario_event)
            if not trigger_result:
                 return {"error": "Failed to trigger GitHub event."}

            # 5. Poll for completion
            print(f"Waiting for workflow run to complete...")
            run_id = self._poll_for_completion(workflow_id, start_time)
            if not run_id:
                return {"error": "Timed out waiting for workflow run or could not find it."}

            # 6. Fetch logs
            print(f"Fetching logs for run {run_id}...")
            stdout, stderr = self._get_workflow_logs(run_id)
            
            run_result = {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": 0
            }
            
            analysis = self.analyzer.analyze(run_result, scenario_path)
            
            return {
                "workflow": workflow_id,
                "scenario": scenario_id,
                "analysis": analysis,
                "run_id": run_id,
                "message": f"Successfully executed and analyzed run {run_id}."
            }
        finally:
            print(f"Cleaning up repository state for scenario '{scenario_id}'...")
            scenario.teardown_state(self.gh_client)

    def _trigger_event(self, scenario_event):
        """Triggers a GitHub event (Issue/PR) to start the workflow."""
        event_type = scenario_event.get("event_type")
        data = scenario_event.get("data", {})
        
        if event_type == "issue":
            stdout, stderr = self.gh_client.run_gh([
                "issue", "create",
                "--title", data.get("title", "Test Issue"),
                "--body", data.get("body", "Test Body")
            ])
            if "https://github.com/" in stdout:
                return True
        elif event_type == "pull_request":
            stdout, stderr = self.gh_client.run_gh([
                "pr", "create",
                "--title", data.get("title", "Test PR"),
                "--body", data.get("body", "Test Body")
            ])
            if "https://github.com/" in stdout:
                return True
        
        return False

    def _load_scenario(self, scenario_path):
        """Loads a Python scenario class."""
        if not scenario_path.endswith('.py'):
            return None
            
        module_name = os.path.basename(scenario_path).replace('.py', '')
        spec = importlib.util.spec_from_file_location(module_name, scenario_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    attr_name != "AbstractScenario" and 
                    "AbstractScenario" in [base.__name__ for base in attr.__mro__]):
                    return attr(self.workspace_dir)
        return None

    def _poll_for_completion(self, workflow_id, start_time, timeout=600):
        """Polls the GitHub API until the workflow run finishes."""
        filename = "workflow.yml"
        elapsed = 0
        while elapsed < timeout:
            stdout, _ = self.gh_client.run_gh([
                "run", "list", 
                "--workflow", filename, 
                "--json", "databaseId,status,conclusion,createdAt",
                "--limit", "1"
            ])
            
            if stdout:
                runs = json.loads(stdout)
                if runs:
                    run = runs[0]
                    if run["status"] == "completed":
                        return run["databaseId"]
                    
            time.sleep(10)
            elapsed += 10
            
        return None

    def _get_workflow_logs(self, run_id):
        """Retrieves the full logs for a specific workflow run."""
        stdout, stderr = self.gh_client.run_gh(["run", "view", str(run_id), "--log"])
        return stdout, stderr
