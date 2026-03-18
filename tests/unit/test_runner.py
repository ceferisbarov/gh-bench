import json
from unittest.mock import patch

import pytest

from src.benchmark.runner import BenchmarkRunner


@pytest.fixture
def runner():
    with patch("src.benchmark.runner.GitHubClient") as mock_client:
        # Mock current user for _generate_repo_name
        mock_client.return_value.run_gh.return_value = ("testuser", "")
        return BenchmarkRunner(workspace_dir="/tmp", repo_prefix="test-repo")


def test_generate_repo_name_with_owner(runner):
    name = runner._generate_repo_name("owner/prefix")
    assert name.startswith("owner/prefix-")
    assert len(name.split("-")[-1]) == 6


def test_generate_repo_name_without_owner(runner):
    # Already initialized with prefix "test-repo" which called _generate_repo_name
    # Let's test it directly
    with patch("src.benchmark.runner.GitHubClient") as mock_client:
        mock_client.return_value.run_gh.return_value = ("resolved-user", "")
        r = BenchmarkRunner(workspace_dir="/tmp", repo_prefix="my-bench")
        assert r.repo.startswith("resolved-user/my-bench-")


def test_poll_for_completion_success(runner):
    # Mock gh_client.run_gh to return a completed run
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    recent_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    mock_run_list = [{"databaseId": "12345", "status": "completed", "conclusion": "success", "createdAt": recent_time}]
    mock_run_view = {"status": "completed", "conclusion": "success"}

    def mock_run_gh(args, **kwargs):
        if "list" in args:
            return json.dumps(mock_run_list), ""
        elif "view" in args:
            return json.dumps(mock_run_view), ""
        return "", ""

    runner.gh_client.run_gh.side_effect = mock_run_gh

    # start_time is timestamp
    run_id = runner._wait_for_run(now.timestamp() - 5)
    assert run_id == "12345"


def test_poll_for_completion_ignores_old_runs(runner):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    old_time = (now - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

    mock_run = {"databaseId": "old_id", "status": "completed", "conclusion": "success", "createdAt": old_time}

    def mock_run_gh(args, **kwargs):
        if "list" in args:
            return json.dumps([mock_run]), ""
        return "", ""

    runner.gh_client.run_gh.side_effect = mock_run_gh

    # Should timeout because it ignores old runs
    with patch("time.sleep"):  # Speed up test
        run_id = runner._wait_for_run(now.timestamp(), timeout=20)
    assert run_id is None
