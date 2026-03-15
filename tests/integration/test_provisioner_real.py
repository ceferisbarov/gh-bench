import time
import uuid

import pytest

from src.benchmark.utils.gh_client import GitHubClient
from src.benchmark.utils.provisioner import RepoProvisioner

# Use the correct account for testing
REPO_OWNER = "velvetfairy2000"


@pytest.fixture(scope="module")
def real_gh_client():
    """Fixture to provide a real GitHubClient for a temporary repository."""
    repo_name = f"temp-test-provisioner-{uuid.uuid4().hex[:8]}"
    full_repo = f"{REPO_OWNER}/{repo_name}"
    client = GitHubClient(repo=full_repo)

    yield client

    # Cleanup: Delete the repository
    client.run_gh(["repo", "delete", full_repo, "--yes"], use_repo=False)


def test_provisioner_real_provision(real_gh_client, tmp_path):
    """Real integration test for RepoProvisioner.provision."""
    provisioner = RepoProvisioner(real_gh_client)

    # Create a dummy workflow file
    workflow_dir = tmp_path / "test-workflow"
    workflow_dir.mkdir()
    workflow_file = workflow_dir / "ci.yml"
    workflow_file.write_text("name: Test CI\non: push\njobs: test: runs-on: ubuntu-latest\n  steps: - run: echo hello")

    # Create a dummy scenario file
    scenario_file = tmp_path / "scenario.txt"
    scenario_file.write_text("scenario data")

    required_files = {"src/scenario.txt": str(scenario_file), "data/config.json": '{"test": true}'}

    # Run provision
    provisioner.provision(workflow_path=str(workflow_file), required_files=required_files, branch="bench-branch")

    # Wait for propagation
    time.sleep(5)

    # Verify results
    # 1. Workflow should be in default branch (main)
    files_main = real_gh_client.list_files(branch="main")
    assert ".github/workflows/test-workflow.yml" in files_main
    assert "README.md" in files_main

    # 2. Branch should exist
    branch_info = real_gh_client.get_branch_info("bench-branch")
    assert branch_info.get("name") == "bench-branch"

    # 3. Scenario files should be in bench-branch
    files_bench = real_gh_client.list_files(branch="bench-branch")
    assert "src/scenario.txt" in files_bench
    assert "data/config.json" in files_bench
