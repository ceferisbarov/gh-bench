import base64
import json

from src.benchmark.utils.gh_client import GitHubClient


def test_gh_client_run_gh_success(mocker):
    # Mock subprocess.run
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "some output"
    mock_run.return_value.stderr = ""

    client = GitHubClient(repo="test/repo")
    stdout, stderr = client.run_gh(["pr", "list"])

    # Verify command construction
    expected_cmd = ["gh", "pr", "list", "-R", "test/repo"]
    mock_run.assert_called_with(expected_cmd, capture_output=True, text=True, env=mocker.ANY)
    assert stdout == "some output"
    assert stderr == ""


def test_gh_client_get_repo_info(mocker):
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 0
    repo_data = {"defaultBranchRef": {"name": "main"}, "isEmpty": False}
    mock_run.return_value.stdout = json.dumps(repo_data)
    mock_run.return_value.stderr = ""

    client = GitHubClient(repo="test/repo")
    info = info = client.get_repo_info()

    assert info == repo_data
    called_args = mock_run.call_args[0][0]
    assert "api" in called_args
    assert any("repos/{owner}/{repo}" in arg for arg in called_args)


def test_gh_client_create_repo(mocker):
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "https://github.com/test/repo"
    mock_run.return_value.stderr = ""

    client = GitHubClient(repo="test/repo")
    success, err = client.create_repo(public=True)

    assert success is True
    called_args = mock_run.call_args[0][0]
    assert "repo" in called_args
    assert "create" in called_args
    assert "test/repo" in called_args
    assert "--public" in called_args
    # Verify use_repo=False (no -R test/repo)
    assert "-R" not in called_args


def test_gh_client_get_branch_info(mocker):
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 0
    branch_data = {"name": "main"}
    mock_run.return_value.stdout = json.dumps(branch_data)
    mock_run.return_value.stderr = ""

    client = GitHubClient(repo="test/repo")
    info = client.get_branch_info("main")

    assert info == branch_data
    called_args = mock_run.call_args[0][0]
    assert "api" in called_args
    assert any("repos/{owner}/{repo}/branches/main" in arg for arg in called_args)


def test_gh_client_create_branch(mocker):
    mock_run = mocker.patch("subprocess.run")

    # Mock sequence: 1. get_default_branch (repo info), 2. get SHA, 3. create branch
    def side_effect(cmd, **kwargs):
        from unittest.mock import MagicMock

        m = MagicMock()
        m.returncode = 0
        m.stderr = ""
        cmd_str = " ".join(cmd)
        if "repo view" in cmd_str:
            m.stdout = json.dumps({"defaultBranchRef": {"name": "main"}})
        elif "git/refs/heads/main" in cmd_str:
            m.stdout = json.dumps({"object": {"sha": "abc123"}})
        elif "POST" in cmd_str and "git/refs" in cmd_str:
            m.stdout = json.dumps({"ref": "refs/heads/new-feature"})
        else:
            m.stdout = ""
        return m

    mock_run.side_effect = side_effect

    client = GitHubClient(repo="test/repo")
    success, err = client.create_branch("new-feature")

    assert success is True
    # Verify the last call was POST to create the ref
    last_call_args = mock_run.call_args_list[-1][0][0]
    last_call_str = " ".join(last_call_args)
    assert "api" in last_call_str
    assert "--method POST" in last_call_str
    assert "git/refs" in last_call_str
    assert "ref=refs/heads/new-feature" in last_call_str
    assert "sha=abc123" in last_call_str


def test_gh_client_put_file(mocker):
    mock_run = mocker.patch("subprocess.run")

    # Mock sequence: 1. get_default_branch, 2. get file SHA (404/empty), 3. PUT file
    def side_effect(cmd, **kwargs):
        from unittest.mock import MagicMock

        m = MagicMock()
        m.returncode = 0
        m.stderr = ""
        cmd_str = " ".join(cmd)
        if "repo view" in cmd_str:
            m.stdout = json.dumps({"defaultBranchRef": {"name": "main"}})
        elif "contents/test.txt" in cmd_str and "PUT" not in cmd_str:
            m.stdout = ""  # File doesn't exist
        elif "PUT" in cmd_str:
            m.stdout = json.dumps({"content": {"name": "test.txt"}})
        else:
            m.stdout = ""
        return m

    mock_run.side_effect = side_effect

    client = GitHubClient(repo="test/repo")
    success, err = client.put_file("test.txt", "hello world", "commit msg", branch="main")

    assert success is True
    last_call_args = mock_run.call_args_list[-1][0][0]
    last_call_str = " ".join(last_call_args)
    assert "api" in last_call_str
    assert "PUT" in last_call_str
    assert "message=commit msg" in last_call_str
    assert "branch=main" in last_call_str
    # content should be base64 of "hello world"
    expected_content = base64.b64encode(b"hello world").decode()
    assert f"content={expected_content}" in last_call_str


def test_gh_client_get_pr_details(mocker):
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = json.dumps({"title": "Fix bug", "body": "Fixed it.", "comments": []})
    mock_run.return_value.stderr = ""

    client = GitHubClient(repo="test/repo")
    details = client.get_pr_details(42)

    assert details["title"] == "Fix bug"
    assert details["body"] == "Fixed it."
    called_args = mock_run.call_args[0][0]
    assert "pr" in called_args
    assert "view" in called_args
    assert "42" in called_args


def test_gh_client_fork_repo(mocker):
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "https://github.com/my-user/new-repo"
    mock_run.return_value.stderr = ""

    client = GitHubClient(repo="my-user/new-repo")
    success, err = client.fork_repo("source/template")

    assert success is True
    called_args = mock_run.call_args[0][0]
    assert "repo" in called_args
    assert "fork" in called_args
    assert "source/template" in called_args
    assert "--fork-name" in called_args
    assert "new-repo" in called_args
    assert "--clone=false" in called_args
    assert "-R" not in called_args


def test_gh_client_delete_repo(mocker):
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "Deleted repository my-user/new-repo"
    mock_run.return_value.stderr = ""

    client = GitHubClient(repo="my-user/new-repo")
    success, err = client.delete_repo()

    assert success is True
    called_args = mock_run.call_args[0][0]
    assert "repo" in called_args
    assert "delete" in called_args
    assert "my-user/new-repo" in called_args
    assert "--yes" in called_args
    assert "-R" not in called_args


def test_gh_client_auth_error(mocker, capsys):
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 1
    mock_run.return_value.stdout = ""
    mock_run.return_value.stderr = "error: not authenticated"

    client = GitHubClient(repo="test/repo")
    client.run_gh(["repo", "view"])

    captured = capsys.readouterr()
    assert "GitHub CLI is not authenticated" in captured.err
