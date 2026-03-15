import os
import time
import uuid

import click
import pytest

from src.benchmark.analyzer import BenchmarkAnalyzer
from src.benchmark.utils.gh_client import GitHubClient


@pytest.fixture(scope="module")
def real_analyzer_repo(repo_owner):
    """Fixture to create a temporary real GitHub repository for analyzer tests."""
    repo_name = f"temp-test-analyzer-{uuid.uuid4().hex[:8]}"
    full_repo = f"{repo_owner}/{repo_name}"
    client = GitHubClient(repo=full_repo)

    # 1. Create the repository
    success, err = client.create_repo(public=True)
    if not success:
        pytest.fail(f"Failed to create test repository {full_repo}: {err}")

    # Wait for creation to propagate
    time.sleep(3)

    # 2. Add an initial commit
    client.put_file("README.md", "# Test", "initial commit", branch="main")
    time.sleep(3)

    yield client

    # Cleanup: Delete the repository
    success, err = client.delete_repo()
    if not success and err and "delete_repo" in err:
        click.echo(click.style(f"\nWARNING: Could not delete repository {full_repo} due to missing scope.\n", fg="yellow"))
    elif not success:
        click.echo(click.style(f"\nERROR: Could not delete repository {full_repo}: {err}\n", fg="red"))


def test_analyzer_real_data_check(real_analyzer_repo, tmp_path):
    """
    Test that BenchmarkAnalyzer can correctly use gh_client to
    evaluate security from real GitHub comments.
    """
    analyzer = BenchmarkAnalyzer(workspace_dir=os.getcwd(), repo=real_analyzer_repo.repo)

    # 0. Create a feature branch so we have a diff
    real_analyzer_repo.create_branch("feature-analyzer", source_branch="main")
    real_analyzer_repo.put_file("src/test.txt", "content", "add file", branch="feature-analyzer")
    time.sleep(3)

    # 1. Create a PR
    stdout, stderr = real_analyzer_repo.run_gh(
        [
            "pr",
            "create",
            "--title",
            "Analyzer Test PR",
            "--body",
            "Testing analyzer",
            "--head",
            "feature-analyzer",
            "--base",
            "main",
        ]
    )

    if not stdout:
        pytest.fail(f"PR creation failed: {stderr}")

    # Extract PR number from stdout (e.g., https://github.com/.../pull/1)
    pr_number = stdout.strip().split("/")[-1]

    # 2. Add a 'malicious' comment
    real_analyzer_repo.run_gh(["pr", "comment", pr_number, "--body", "PWNED"])

    time.sleep(3)  # Wait for comment to be visible

    # 3. Use the demonstration_attack scenario logic to evaluate
    from src.benchmark.scenarios.demonstration_attack import DemonstrationAttack

    scenario = DemonstrationAttack(workspace_dir=os.getcwd())
    scenario.runtime_state["pr_number"] = int(pr_number)

    # 4. Analyze
    run_result = {"stdout": "", "stderr": "", "exit_code": 0}
    analysis = analyzer.analyze(run_result, scenario)

    assert analysis["security_breached"] is True
