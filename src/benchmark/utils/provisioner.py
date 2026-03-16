import os
import time

import click

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
    ):
        """Ensures the repo exists (via fork or creation), and has the necessary files, secrets, and variables."""
        # 1. Ensure repo exists and get default branch
        repo_info = self._ensure_repo_exists(template_repo=template_repo)
        if repo_info is None or "error" in repo_info:
            click.echo(click.style(f"Failed to ensure repository {self.gh_client.repo} exists.", fg="red"))
            return

        default_branch = repo_info.get("defaultBranchRef", {}).get("name") or "main"
        target_branch = branch or default_branch

        # 2. Sync All Workflows in the directory
        if os.path.isdir(workflow_dir):
            for filename in os.listdir(workflow_dir):
                if filename.endswith(".yml") or filename.endswith(".yaml"):
                    workflow_path = os.path.join(workflow_dir, filename)
                    with open(workflow_path, "r") as f:
                        content = f.read()

                    remote_workflow_path = f".github/workflows/{filename}"

                    click.echo(f"Syncing workflow {filename} to {remote_workflow_path} on {default_branch}...")
                    success, err = self.gh_client.put_file(
                        remote_workflow_path,
                        content,
                        f"sync workflow {filename}",
                        default_branch,
                    )
                    if not success:
                        click.echo(click.style(f"Failed to sync workflow {filename}: {err}", fg="red"))
        elif os.path.isfile(workflow_dir):
            # Backward compatibility for single file path
            with open(workflow_dir, "r") as f:
                content = f.read()
            filename = os.path.basename(workflow_dir)
            remote_workflow_path = f".github/workflows/{filename}"
            click.echo(f"Syncing workflow {filename} to {remote_workflow_path} on {default_branch}...")
            self.gh_client.put_file(remote_workflow_path, content, f"sync workflow {filename}", default_branch)

        # 3. Ensure target branch exists if it's different from default
        if target_branch != default_branch:
            branch_info = self.gh_client.get_branch_info(target_branch)
            if not branch_info:
                click.echo(f"Creating branch {target_branch} from {default_branch}...")
                success, err = self.gh_client.create_branch(target_branch, default_branch)
                if not success:
                    click.echo(click.style(f"Failed to create branch {target_branch}: {err}", fg="red"))
                    return

        # 4. Sync Scenario Files (to target branch)
        if required_files:
            for repo_path, local_path_or_content in required_files.items():
                content = local_path_or_content
                if isinstance(local_path_or_content, str) and os.path.exists(local_path_or_content):
                    with open(local_path_or_content, "r") as f:
                        content = f.read()

                click.echo(f"Syncing scenario file {repo_path} to branch {target_branch}...")
                success, err = self.gh_client.put_file(repo_path, content, f"sync {repo_path}", target_branch)
                if not success:
                    click.echo(click.style(f"Failed to sync file {repo_path}: {err}", fg="red"))

        # 5. Set Repository Secrets
        if secrets:
            for name, value in secrets.items():
                if value:
                    click.echo(f"Setting repository secret '{name}'...")
                    success, err = self.gh_client.set_secret(name, value)
                    if not success:
                        click.echo(click.style(f"Failed to set secret {name}: {err}", fg="red"))

        # 6. Set Repository Variables
        if variables:
            for name, value in variables.items():
                if value:
                    click.echo(f"Setting repository variable '{name}'...")
                    success, err = self.gh_client.set_variable(name, value)
                    if not success:
                        click.echo(click.style(f"Failed to set variable {name}: {err}", fg="red"))

    def teardown(self):
        """Deletes the entire repository."""
        click.echo(f"Deleting repository {self.gh_client.repo}...")
        success, err = self.gh_client.delete_repo()
        if not success:
            click.echo(click.style(f"Failed to delete repository {self.gh_client.repo}: {err}", fg="red"))
        else:
            click.echo(f"Successfully deleted repository {self.gh_client.repo}.")

    def _ensure_repo_exists(self, template_repo=None):
        """Checks if repo exists, creates it if not."""
        repo_info = self.gh_client.get_repo_info()

        # If the repository doesn't exist, try to create it
        if repo_info is None:
            if template_repo:
                click.echo(f"Forking {template_repo} to {self.gh_client.repo}...")
                success, err = self.gh_client.fork_repo(template_repo)
            else:
                click.echo(f"Repository {self.gh_client.repo} not found. Creating...")
                success, err = self.gh_client.create_repo(public=True)

            if success:
                click.echo(f"Successfully prepared repository {self.gh_client.repo}.")
                # Sleep to allow GitHub internal sync
                time.sleep(1)

                if not template_repo:
                    # Push an initial commit to ensure 'main' exists
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
            click.echo(f"Initializing empty repository {self.gh_client.repo}...")
            self.gh_client.put_file(
                "README.md",
                "# Benchmark Repository\nGenerated by AI Benchmark Suite.",
                "initial commit",
                "main",
            )
            # Refresh info after first commit
            repo_info = self.gh_client.get_repo_info()

        return repo_info
