import os

import click
from tenacity import retry, retry_if_result, stop_after_attempt, wait_fixed

from .gh_client import GitHubClient


class RepoProvisioner:
    """Handles the physical setup of a GitHub repository for benchmarking."""

    def __init__(self, gh_client: GitHubClient):
        self.gh_client = gh_client

    def provision(
        self,
        workflow_dir: str,
        required_files: dict = None,
        branch: str = None,
        template_repo: str = None,
        secrets: dict = None,
        variables: dict = None,
        substitution_map: dict = None,
    ):
        """Ensures the repo exists (via fork or creation), and has the necessary files, secrets, and variables."""
        repo_info = self._ensure_repo_exists(template_repo=template_repo)
        if repo_info is None or "error" in repo_info:
            click.echo(click.style(f"Failed to ensure repository {self.gh_client.repo_name} exists.", fg="red"))
            return

        default_branch = repo_info.get("defaultBranchRef", {}).get("name") or "main"
        target_branch = branch or default_branch

        # 1. Ensure target branch exists BEFORE syncing files
        if target_branch != default_branch:
            branch_info = self.gh_client.get_branch_info(target_branch)
            if not branch_info:
                click.echo(f"Creating branch {target_branch} from {default_branch}...")
                success, err = self.gh_client.create_branch(target_branch, default_branch)
                if not success:
                    click.echo(click.style(f"Failed to create branch {target_branch}: {err}", fg="red"))
                    return

        # 2. Collect all files to be provisioned
        all_files = {}  # repo_path -> content_or_local_path

        if os.path.isdir(workflow_dir):
            contents_dir = os.path.join(workflow_dir, "contents")
            if os.path.isdir(contents_dir):
                for root, _, filenames in os.walk(contents_dir):
                    for filename in filenames:
                        local_file_path = os.path.join(root, filename)
                        rel_path = os.path.relpath(local_file_path, contents_dir)
                        all_files[rel_path] = local_file_path
            else:
                for filename in os.listdir(workflow_dir):
                    if filename.endswith(".yml") or filename.endswith(".yaml"):
                        workflow_path = os.path.join(workflow_dir, filename)
                        all_files[f".github/workflows/{filename}"] = workflow_path

        if required_files:
            for repo_path, content_or_path in required_files.items():
                if repo_path in all_files:
                    raise ValueError(
                        f"Conflict detected: File '{repo_path}' is defined by both the workflow and the scenario."
                    )
                all_files[repo_path] = content_or_path

        # 3. Sync files to GitHub (using target_branch)
        for repo_path, content_or_path in all_files.items():
            content = content_or_path
            is_binary = False
            if isinstance(content_or_path, str) and os.path.exists(content_or_path):
                with open(content_or_path, "rb") as f:
                    content = f.read()
                    try:
                        content = content.decode("utf-8")
                        if substitution_map and (repo_path.endswith(".yml") or repo_path.endswith(".yaml")):
                            content = self._patch_yaml(content, substitution_map)
                    except UnicodeDecodeError:
                        is_binary = True

            click.echo(f"Syncing {repo_path} to {target_branch}...")
            success, err = self.gh_client.put_file(
                repo_path,
                content if not is_binary else content.decode("latin-1"),
                f"provision {repo_path}",
                target_branch,
            )
            if not success:
                click.echo(click.style(f"Failed to sync file {repo_path}: {err}", fg="red"))

        # 4. Set Repository Secrets
        if secrets:
            for name, value in secrets.items():
                if value:
                    click.echo(f"Setting repository secret '{name}'...")
                    success, err = self.gh_client.set_secret(name, value)
                    if not success:
                        click.echo(click.style(f"Failed to set secret {name}: {err}", fg="red"))

        # 5. Set Repository Variables
        if variables:
            for name, value in variables.items():
                if value:
                    click.echo(f"Setting repository variable '{name}'...")
                    success, err = self.gh_client.set_variable(name, value)
                    if not success:
                        click.echo(click.style(f"Failed to set variable {name}: {err}", fg="red"))

    def _patch_yaml(self, content: str, substitution_map: dict) -> str:
        """Replaces official action references with adversarial forks/tags."""
        import re

        patched_content = content
        for original, replacement in substitution_map.items():
            pattern = rf"uses:\s*['\"]?{re.escape(original)}['\"]?"
            replacement_str = f"uses: {replacement}"
            if re.search(pattern, patched_content):
                click.echo(click.style(f"  PATCHED: Swapping '{original}' -> '{replacement}'", fg="cyan"))
                patched_content = re.sub(pattern, replacement_str, patched_content)

        return patched_content

    def teardown(self):
        """Deletes the entire repository."""
        click.echo(f"Deleting repository {self.gh_client.repo_name}...")
        success, err = self.gh_client.delete_repo()
        if not success:
            click.echo(click.style(f"Failed to delete repository {self.gh_client.repo_name}: {err}", fg="red"))
        else:
            click.echo(f"Successfully deleted repository {self.gh_client.repo_name}.")

    @retry(retry=retry_if_result(lambda res: res is None or "error" in res), stop=stop_after_attempt(5), wait=wait_fixed(2))
    def _ensure_repo_exists(self, template_repo=None):
        """Checks if repo exists, creates it if not."""
        repo_info = self.gh_client.get_repo_info()

        if repo_info is None:
            if template_repo:
                click.echo(f"Forking {template_repo} to {self.gh_client.repo_name}...")
                success, err = self.gh_client.fork_repo(template_repo)
            else:
                click.echo(f"Repository {self.gh_client.repo_name} not found. Creating...")
                success, err = self.gh_client.create_repo(public=True)

            if success:
                click.echo(f"Successfully prepared repository {self.gh_client.repo_name}.")

                if not template_repo:
                    success, err = self.gh_client.put_file(
                        "README.md",
                        "# Benchmark Repository\nGenerated by AI Benchmark Suite.",
                        "initial commit",
                        "main",
                    )
                    if not success:
                        click.echo(click.style(f"Failed to push initial commit: {err}", fg="red"))

                repo_info = self.gh_client.get_repo_info()
            else:
                click.echo(click.style(f"Failed to prepare repository: {err}", fg="red"))
                return {"error": "Provisioning failed"}

        if repo_info and repo_info.get("isEmpty"):
            click.echo(f"Initializing empty repository {self.gh_client.repo_name}...")
            self.gh_client.put_file(
                "README.md",
                "# Benchmark Repository\nGenerated by AI Benchmark Suite.",
                "initial commit",
                "main",
            )
            repo_info = self.gh_client.get_repo_info()

        return repo_info
