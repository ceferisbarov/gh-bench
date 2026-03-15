import os
import uuid

import pytest

from src.benchmark.runner import BenchmarkRunner
from src.benchmark.scenario_base import AbstractScenario


class DummyScenario(AbstractScenario):
    """
    Dummy scenario for testing the BenchmarkRunner.
    It triggers a simple pull_request event.
    """

    def get_required_files(self) -> dict:
        return {"src/test.txt": "dummy test content"}

    def setup_state(self, gh_client):
        """No extra state needed."""
        pass

    def teardown_state(self, gh_client):
        """No extra cleanup needed."""
        pass

    def get_event(self):
        return {
            "event_type": "pull_request",
            "data": {
                "action": "opened",
                "title": "Dummy PR for integration test",
                "body": "This is a dummy PR body.",
                "head": "main",
                "base": "main",
            },
        }

    def evaluate_utility(self, run_result, gh_client) -> bool:
        # Simple utility check for testing
        return "completed" in run_result.get("stdout", "").lower() or run_result.get("exit_code") == 0

    def evaluate_security(self, run_result, gh_client) -> bool:
        return False


@pytest.fixture(scope="module")
def real_runner(repo_owner):
    """Fixture to provide a real BenchmarkRunner with a unique prefix."""
    workspace_dir = os.getcwd()
    prefix = f"{repo_owner}/test-runner-{uuid.uuid4().hex[:6]}"
    runner = BenchmarkRunner(workspace_dir=workspace_dir, repo_prefix=prefix)
    return runner


def test_runner_real_run(real_runner, tmp_path):
    """
    This test executes the full lifecycle of a benchmark run.
    It will create a repo, push a workflow, trigger an event,
    wait for completion, fetch logs, analyze, and delete the repo.
    """
    # 1. Use a simple workflow that doesn't need external APIs if possible
    # We'll create a temporary workflow for this test to avoid external dependencies
    test_workflow_dir = os.path.join(os.getcwd(), "src/benchmark/workflows/runner-test")
    os.makedirs(test_workflow_dir, exist_ok=True)

    workflow_content = """
name: Runner Test
on:
  pull_request:
    types: [opened]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo "Integration test run success"
"""
    workflow_file = os.path.join(test_workflow_dir, "workflow.yml")
    with open(workflow_file, "w") as f:
        f.write(workflow_content)

    metadata_content = '{"name": "Runner Test", "description": "Used for integration testing"}'
    with open(os.path.join(test_workflow_dir, "metadata.json"), "w") as f:
        f.write(metadata_content)

    # 2. Create a dummy scenario file in a temp directory
    scenario_content = """
from src.benchmark.scenario_base import AbstractScenario

class TestRunnerScenario(AbstractScenario):
    def __init__(self, workspace_dir):
        super().__init__(workspace_dir)
        self.branch = "feature-test"

    def get_required_files(self): return {"src/code.py": "print('hello')"}
    
    def setup_state(self, gh_client):
        pass

    def teardown_state(self, gh_client): pass
    
    def get_event(self):
        return {
            "event_type": "pull_request",
            "data": {
                "title": "Integration Test PR",
                "body": "Test body",
                "head": self.branch,
                "base": "main"
            }
        }
    def evaluate_utility(self, run_result, gh_client): return True
    def evaluate_security(self, run_result, gh_client): return False
"""
    scenario_file = os.path.join(os.getcwd(), "src/benchmark/scenarios/test_runner_scenario.py")
    with open(scenario_file, "w") as f:
        f.write(scenario_content)

    try:
        # 3. Run the benchmark
        # We need to use the folder name 'runner-test' as workflow_id
        # and 'test_runner_scenario.py' as scenario_id
        result = real_runner.run("runner-test", "test_runner_scenario.py")

        # 4. Assertions
        assert "error" not in result
        assert "analysis" in result
        assert result["analysis"]["utility_achieved"] is True
        assert result["analysis"]["security_breached"] is False
        assert "run_id" in result

    finally:
        # Cleanup local temporary files
        import shutil

        if os.path.exists(test_workflow_dir):
            shutil.rmtree(test_workflow_dir)
        if os.path.exists(scenario_file):
            os.remove(scenario_file)
