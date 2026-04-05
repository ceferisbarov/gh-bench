import logging
import os
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

import click
from github import Github, GithubException, Repository
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple rate limiter to prevent hitting GitHub secondary rate limits."""

    def __init__(self):
        max_calls = os.environ.get("GITHUB_MAX_CALLS_PER_MINUTE", 20)
        self.enabled = max_calls is not None
        if self.enabled:
            self.delay = 60.0 / float(max_calls)
            self.last_call = 0.0

    def wait(self):
        if not self.enabled:
            return
        now = time.time()
        elapsed = now - self.last_call
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_call = time.time()


rate_limiter = RateLimiter()


class GitHubClient:
    """A wrapper for PyGitHub to interact with repositories."""

    def __init__(self, repo: str = "owner/repo"):
        self.repo_name = repo
        self.token = self._get_token()
        self.gh = Github(self.token)
        self._repo_cache: Optional[Repository.Repository] = None

    def _get_token(self) -> str:
        """Retrieves GitHub token from environment or gh CLI."""
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            return token

        try:
            result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            click.echo(
                click.style(
                    "Error: GitHub token not found. Please set GITHUB_TOKEN or run 'gh auth login'.",
                    fg="red",
                ),
                err=True,
            )
            raise RuntimeError("Missing GitHub authentication")

    @property
    def repository(self) -> Repository.Repository:
        """Lazily loads and returns the Repository object."""
        if self._repo_cache is None:
            rate_limiter.wait()
            self._repo_cache = self.gh.get_repo(self.repo_name)
        return self._repo_cache

    def get_repo_info(self) -> Optional[Dict[str, Any]]:
        """Fetches repository information."""
        try:
            repo = self.repository
            return {
                "name": repo.name,
                "owner": {"login": repo.owner.login},
                "defaultBranchRef": {"name": repo.default_branch},
                "isEmpty": repo.size == 0,
                "size": repo.size,
                "default_branch": repo.default_branch,
            }
        except GithubException as e:
            if e.status == 404:
                return None
            raise

    def get_default_branch(self) -> str:
        """Returns the name of the default branch."""
        try:
            return self.repository.default_branch
        except GithubException:
            return "main"

    def create_repo(self, public: bool = True) -> Tuple[bool, str]:
        """Creates the repository if it doesn't exist."""
        try:
            name = self.repo_name.split("/")[-1]
            if "/" in self.repo_name:
                owner = self.repo_name.split("/", 1)[0]
                user = self.gh.get_user()
                if user.login.lower() == owner.lower():
                    user.create_repo(name, private=not public)
                else:
                    org = self.gh.get_organization(owner)
                    org.create_repo(name, private=not public)
            else:
                self.gh.get_user().create_repo(name, private=not public)
            return True, ""
        except GithubException as e:
            return False, str(e)

    def fork_repo(self, template_repo_name: str) -> Tuple[bool, str]:
        """Forks a template repository into a new unique name, prioritizing the gh-bench organization."""
        try:
            # Check if a fork already exists in the gh-bench organization
            repo_short_name = template_repo_name.split("/")[-1]
            gh_bench_repo_name = f"gh-bench/{repo_short_name}"

            try:
                rate_limiter.wait()
                template_repo = self.gh.get_repo(gh_bench_repo_name)
                click.echo(f"Using controlled fork from: {gh_bench_repo_name}")
            except GithubException:
                # If it doesn't exist in gh-bench, fork it there first to avoid notifying maintainers in every run
                click.echo(f"Mirroring {template_repo_name} to gh-bench organization...")
                rate_limiter.wait()
                source_repo = self.gh.get_repo(template_repo_name)
                source_repo.create_fork(organization="gh-bench")

                # Wait for the mirror fork to be ready
                @retry(
                    retry=retry_if_result(lambda res: res is False),
                    stop=stop_after_attempt(15),
                    wait=wait_exponential(multiplier=1, min=2, max=10),
                )
                def wait_for_mirror():
                    try:
                        self.gh.get_repo(gh_bench_repo_name)
                        return True
                    except GithubException:
                        return False

                if not wait_for_mirror():
                    return False, f"Failed to mirror {template_repo_name} to gh-bench."

                template_repo = self.gh.get_repo(gh_bench_repo_name)

            name = self.repo_name.split("/")[-1]

            # Handle organization if specified in repo_name
            org = None
            if "/" in self.repo_name:
                owner = self.repo_name.split("/", 1)[0]
                user = self.gh.get_user()
                if user.login.lower() != owner.lower():
                    org = owner

            if org:
                template_repo.create_fork(organization=org, name=name)
            else:
                template_repo.create_fork(name=name)

            @retry(
                retry=retry_if_result(lambda res: res is False),
                stop=stop_after_attempt(15),
                wait=wait_exponential(multiplier=1, min=2, max=10),
            )
            def wait_for_fork():
                try:
                    self._repo_cache = None
                    info = self.get_repo_info()
                    if not info:
                        return False
                    # Try to access the repository content to ensure it's ready on disk
                    # This prevents 403 Forbidden on subsequent DELETE or other ops
                    self.repository.get_contents("")
                    return True
                except GithubException:
                    return False

            wait_for_fork()
            return True, ""
        except Exception as e:
            return False, str(e)

    @retry(
        retry=retry_if_exception_type(GithubException),
        stop=stop_after_attempt(10),
        wait=wait_exponential(multiplier=2, min=4, max=30),
    )
    def delete_repo(self) -> Tuple[bool, str]:
        """Deletes the current repository."""
        try:
            self.repository.delete()
            self._repo_cache = None
            return True, ""
        except GithubException as e:
            if e.status == 404:
                return True, ""  # Already gone
            if e.status == 403:
                if "delete_repo" in str(e):
                    msg = (
                        "\nERROR: Missing 'delete_repo' scope. Please run:\n"
                        "  gh auth refresh -h github.com -s delete_repo\n"
                    )
                    click.echo(click.style(msg, fg="yellow", bold=True))
                elif "done being created on disk" in str(e):
                    # Re-raise to let the retry decorator handle it
                    raise e
            return False, str(e)

    def get_branch_info(self, branch_name: str) -> Optional[Dict[str, Any]]:
        """Checks if a branch exists and returns its info."""
        try:
            branch = self.repository.get_branch(branch_name)
            return {"name": branch.name, "commit": {"sha": branch.commit.sha}}
        except GithubException as e:
            if e.status == 404:
                return None
            raise

    def create_branch(self, new_branch: str, source_branch: Optional[str] = None) -> Tuple[bool, str]:
        """Creates a new branch from a source branch."""
        if not source_branch:
            source_branch = self.get_default_branch()

        try:
            sb = self.repository.get_branch(source_branch)
            self.repository.create_git_ref(ref=f"refs/heads/{new_branch}", sha=sb.commit.sha)
            return True, ""
        except GithubException as e:
            return False, str(e)

    def get_file_sha(self, path: str, branch: Optional[str] = None) -> Optional[str]:
        """Gets the SHA of a file on a specific branch."""
        try:
            kwargs = {}
            if branch:
                kwargs["ref"] = branch
            content = self.repository.get_contents(path, **kwargs)
            if isinstance(content, list):
                return None
            return content.sha
        except GithubException as e:
            if e.status == 404:
                return None
            raise

    @retry(
        retry=retry_if_exception_type(GithubException),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(5),
        before_sleep=before_sleep_log(logger, logging.INFO),
    )
    def put_file(self, path: str, content: str, message: str, branch: Optional[str] = None) -> Tuple[bool, str]:
        """Uploads or updates a file using the GitHub API."""
        if not branch:
            branch = self.get_default_branch()

        try:
            sha = self.get_file_sha(path, branch)
            if sha:
                self.repository.update_file(path, message, content, sha, branch=branch)
            else:
                self.repository.create_file(path, message, content, branch=branch)
            return True, ""
        except GithubException as e:
            if e.status == 409:
                raise e
            return False, str(e)

    @retry(
        retry=retry_if_exception_type(GithubException),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(5),
    )
    def delete_file(self, path: str, message: str, branch: Optional[str] = None) -> Tuple[bool, str]:
        """Deletes a file from the repository."""
        if not branch:
            branch = self.get_default_branch()

        try:
            sha = self.get_file_sha(path, branch)
            if sha:
                self.repository.delete_file(path, message, sha, branch=branch)
                return True, ""
            return True, "File not found"  # Already gone
        except GithubException as e:
            return False, str(e)

    def get_pr_details(self, pr_number: int) -> Dict[str, Any]:
        """Fetches details of a Pull Request."""
        try:
            pr = self.repository.get_pull(pr_number)
            return {
                "title": pr.title,
                "body": pr.body,
                "state": pr.state,
                "comments": [c.body for c in pr.get_issue_comments()],
            }
        except GithubException:
            return {}

    def get_issue_details(self, issue_number: int) -> Dict[str, Any]:
        """Fetches details of an Issue."""
        try:
            issue = self.repository.get_issue(issue_number)
            return {
                "title": issue.title,
                "body": issue.body,
                "state": issue.state,
                "comments": [c.body for c in issue.get_comments()],
            }
        except GithubException:
            return {}

    @retry(
        retry=retry_if_exception_type(GithubException),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        stop=stop_after_attempt(5),
    )
    def list_files(self, branch: Optional[str] = None) -> List[str]:
        """Lists files in a specific branch."""
        try:
            ref = branch or self.get_default_branch()
            tree = self.repository.get_git_tree(ref, recursive=True)
            return [item.path for item in tree.tree if item.type == "blob"]
        except GithubException as e:
            if e.status == 409:
                return []
            raise

    def set_secret(self, name: str, value: str) -> Tuple[bool, str]:
        """Sets a repository secret."""
        try:
            self.repository.create_secret(name, value)
            return True, ""
        except GithubException as e:
            return False, str(e)

    def set_variable(self, name: str, value: str) -> Tuple[bool, str]:
        """Sets a repository variable."""
        try:
            self.repository.create_variable(name, value)
            return True, ""
        except GithubException as e:
            return False, str(e)

    def list_repos(self, limit: int = 100) -> List[Dict[str, str]]:
        """Lists repositories for the authenticated user."""
        try:
            repos = self.gh.get_user().get_repos()
            return [{"name": r.name, "nameWithOwner": r.full_name} for r in repos[:limit]]
        except GithubException:
            return []

    def get_workflow_runs(self, workflow_id: str = None) -> List[Any]:
        """Fetches recent runs of a specific workflow or all workflows."""
        try:
            if workflow_id:
                runs = self.repository.get_workflow(workflow_id).get_runs()
            else:
                runs = self.repository.get_workflow_runs()
            return [r for r in runs[:10]]
        except GithubException:
            return []

    def run_gh(self, args, **kwargs):
        """Legacy compatibility method. SHOULD BE REMOVED eventually."""
        cmd = ["gh"] + args
        if kwargs.get("use_repo", True):
            cmd += ["-R", self.repo_name]

        env = os.environ.copy()
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        return result.stdout, result.stderr
