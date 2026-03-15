import base64
import json
import os
import subprocess
import time

import click


class GitHubClient:
    """A wrapper for the GitHub CLI (gh) to interact with repos."""

    def __init__(self, repo="owner/repo"):
        self.repo = repo

    def run_gh(self, args, retries=3, delay=3, use_repo=True, retry_404=True):
        """Runs a generic gh command and returns the output with retries for sync issues."""
        cmd = ["gh"] + args

        is_api = args and args[0] == "api"
        env = os.environ.copy()

        if use_repo:
            if is_api:
                # Setting GH_REPO allows using {owner}, {repo}, {branch} placeholders
                env["GH_REPO"] = self.repo
            else:
                cmd += ["-R", self.repo]

        last_stdout, last_stderr = "", ""

        for i in range(retries + 1):
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            last_stdout, last_stderr = result.stdout, result.stderr

            if result.returncode == 0:
                return last_stdout, last_stderr

            low_stderr = last_stderr.lower()
            if "not authenticated" in low_stderr:
                click.echo(
                    click.style(
                        "Error: GitHub CLI is not authenticated. Please run 'gh auth login' " "or set GITHUB_TOKEN.",
                        fg="red",
                    ),
                    err=True,
                )
                return None, last_stderr

            # Common sync issues
            retryable_errors = [
                "could not resolve to a repository",
                "repository not found",
                "not found",
                "failed to get",
                "empty identifier",
            ]
            if retry_404:
                retryable_errors.append("404")

            if any(err in low_stderr for err in retryable_errors) and i < retries:
                time.sleep(delay)
                continue

            break

        return None, last_stderr

    def get_repo_info(self):
        """Fetches repository information using the GitHub API."""
        # Using API placeholders {owner}/{repo}
        stdout, _ = self.run_gh(["api", "repos/{owner}/{repo}"], retry_404=False)
        if not stdout:
            # Fallback to repo view just in case
            stdout, _ = self.run_gh(["repo", "view", "--json", "defaultBranchRef,isEmpty,name,owner"], retry_404=False)

        if not stdout:
            return None

        try:
            data = json.loads(stdout)
            # Normalize fields between API and 'gh repo view' if needed
            if "default_branch" in data and "defaultBranchRef" not in data:
                data["defaultBranchRef"] = {"name": data["default_branch"]}
            if "size" in data and "isEmpty" not in data:
                data["isEmpty"] = data["size"] == 0
            return data
        except json.JSONDecodeError:
            return None

    def get_default_branch(self):
        """Returns the name of the default branch."""
        info = self.get_repo_info()
        if not info:
            return "main"
        if "defaultBranchRef" in info:
            return info["defaultBranchRef"].get("name") or "main"
        return info.get("default_branch") or "main"

    def create_repo(self, public=True):
        """Creates the repository if it doesn't exist."""
        args = ["repo", "create", self.repo, "--confirm"]
        if public:
            args.append("--public")
        else:
            args.append("--private")

        stdout, stderr = self.run_gh(args, use_repo=False)
        return stdout is not None and ("https://github.com/" in stdout or "Created repository" in stdout), stderr

    def fork_repo(self, template_repo):
        """Forks a template repository into a new unique name."""
        # template_repo is the full path e.g. "owner/repo"
        # self.repo is the new name e.g. "my-user/new-repo"
        new_name = self.repo.split("/")[-1]
        args = ["repo", "fork", template_repo, "--fork-name", new_name, "--clone=false"]
        stdout, stderr = self.run_gh(args, use_repo=False)
        return stdout is not None and ("https://github.com/" in stdout or "Created fork" in stdout), stderr

    def delete_repo(self):
        """Deletes the current repository."""
        args = ["repo", "delete", self.repo, "--yes"]
        stdout, stderr = self.run_gh(args, use_repo=False)

        if stderr and "delete_repo" in stderr:
            click.echo(
                click.style(
                    "\nERROR: Missing 'delete_repo' scope. Please run:\n"
                    "  gh auth refresh -h github.com -s delete_repo\n",
                    fg="yellow",
                    bold=True,
                )
            )

        return stdout is not None, stderr

    def get_branch_info(self, branch_name):
        """Checks if a branch exists and returns its info."""
        stdout, _ = self.run_gh(["api", f"repos/{{owner}}/{{repo}}/branches/{branch_name}"])
        if not stdout:
            return None
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return None

    def create_branch(self, new_branch, source_branch=None):
        """Creates a new branch from a source branch (defaults to repository default branch)."""
        if not source_branch:
            source_branch = self.get_default_branch()

        # 1. Get SHA of source branch
        stdout, _ = self.run_gh(["api", f"repos/{{owner}}/{{repo}}/git/refs/heads/{source_branch}"])
        if not stdout:
            return False, f"Failed to get SHA for source branch {source_branch}"
        try:
            source_sha = json.loads(stdout).get("object", {}).get("sha")
            if not source_sha:
                return False, f"Could not find SHA for source branch {source_branch}"
        except json.JSONDecodeError:
            return False, f"Failed to parse source branch info for {source_branch}"

        # 2. Create the new branch
        stdout, stderr = self.run_gh(
            [
                "api",
                "--method",
                "POST",
                "repos/{owner}/{repo}/git/refs",
                "-f",
                f"ref=refs/heads/{new_branch}",
                "-f",
                f"sha={source_sha}",
            ]
        )

        return stdout is not None and "ref" in stdout, stderr

    def get_file_sha(self, path, branch=None):
        """Gets the SHA of a file on a specific branch."""
        endpoint = f"repos/{{owner}}/{{repo}}/contents/{path}"
        args = ["api", endpoint]
        if branch:
            args += ["-F", f"ref={branch}", "--method", "GET"]

        stdout, _ = self.run_gh(args)
        if not stdout:
            return None
        try:
            data = json.loads(stdout)
            if isinstance(data, list):  # It's a directory
                return None
            return data.get("sha")
        except (json.JSONDecodeError, AttributeError):
            return None

    def put_file(self, path, content, message, branch=None):
        """Uploads or updates a file using the GitHub API."""
        if not branch:
            branch = self.get_default_branch()

        encoded_content = base64.b64encode(content.encode()).decode()
        sha = self.get_file_sha(path, branch)

        args = [
            "api",
            "--method",
            "PUT",
            f"repos/{{owner}}/{{repo}}/contents/{path}",
            "-f",
            f"message={message}",
            "-f",
            f"content={encoded_content}",
            "-f",
            f"branch={branch}",
        ]
        if sha:
            args += ["-f", f"sha={sha}"]

        stdout, stderr = self.run_gh(args)
        return stdout is not None and "content" in stdout, stderr

    def get_pr_details(self, pr_number):
        """Fetches details of a Pull Request."""
        stdout, _ = self.run_gh(["pr", "view", str(pr_number), "--json", "title,body,state,comments"])
        if not stdout:
            return {}
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return {}

    def get_issue_details(self, issue_number):
        """Fetches details of an Issue."""
        stdout, _ = self.run_gh(["issue", "view", str(issue_number), "--json", "title,body,state,comments"])
        if not stdout:
            return {}
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return {}

    def list_files(self, branch=None, retries=5, delay=3):
        """Lists files in a specific branch with retries for eventual consistency."""
        if branch:
            for i in range(retries):
                stdout, stderr = self.run_gh(
                    [
                        "api",
                        f"repos/{{owner}}/{{repo}}/git/trees/{branch}",
                        "-F",
                        "recursive=1",
                        "--method",
                        "GET",
                    ]
                )

                # If it's a 409 (empty repo), it might just be syncing the first commit
                if "Git Repository is empty" in stderr or "409" in stderr:
                    if i < retries - 1:
                        time.sleep(delay)
                        continue
                    return []

                if stdout:
                    try:
                        data = json.loads(stdout)
                        if "tree" in data:
                            tree = data.get("tree", [])
                            return [item["path"] for item in tree if item["type"] == "blob"]
                    except json.JSONDecodeError:
                        pass

                if i < retries - 1:
                    time.sleep(delay)
            return []

        stdout, _ = self.run_gh(["repo", "view", "--json", "files"])
        if not stdout:
            return []
        try:
            return json.loads(stdout).get("files", [])
        except json.JSONDecodeError:
            return []

    def get_workflow_runs(self, workflow_id):
        """Fetches recent runs of a specific workflow."""
        stdout, _ = self.run_gh(
            [
                "run",
                "list",
                "--workflow",
                workflow_id,
                "--json",
                "status,conclusion,databaseId",
            ]
        )
        if not stdout:
            return []
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return []
