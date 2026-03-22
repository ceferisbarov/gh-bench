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

        # 2. Collect all files to be provisioned
        all_files = {}  # repo_path -> content_or_local_path

        # A. Collect from Workflow directory
        if os.path.isdir(workflow_dir):
            contents_dir = os.path.join(workflow_dir, "contents")
            if os.path.isdir(contents_dir):
                for root, _, filenames in os.walk(contents_dir):
                    for filename in filenames:
                        local_file_path = os.path.join(root, filename)
                        rel_path = os.path.relpath(local_file_path, contents_dir)
                        all_files[rel_path] = local_file_path
            else:
                # Legacy fallback
                for filename in os.listdir(workflow_dir):
                    if filename.endswith(".yml") or filename.endswith(".yaml"):
                        workflow_path = os.path.join(workflow_dir, filename)
                        all_files[f".github/workflows/{filename}"] = workflow_path

        # B. Collect from Scenario requirements
        if required_files:
            for repo_path, content_or_path in required_files.items():
                if repo_path in all_files:
                    raise ValueError(
                        f"Conflict detected: File '{repo_path}' is defined by both the workflow and the scenario."
                    )
                all_files[repo_path] = content_or_path

        # 3. Sync files to GitHub
        # We sync workflow-originated files to default branch and others to target branch?
        # Actually, for consistency, let's sync everything to the target branch if it exists,
        # but workflows MUST be on the default branch for some triggers to work.
        # Decision: Sync EVERYTHING to both if target != default? Or just sync all to target?
        # Most reliable: Sync all to default branch first, then branch off.

        for repo_path, content_or_path in all_files.items():
            content = content_or_path
            is_binary = False
            if isinstance(content_or_path, str) and os.path.exists(content_or_path):
                with open(content_or_path, "rb") as f:
                    content = f.read()
                    try:
                        content = content.decode("utf-8")
                    except UnicodeDecodeError:
                        is_binary = True

            click.echo(f"Syncing {repo_path} to {default_branch}...")
            # Note: put_file expects string for content, but we might need to handle bytes
            # For now, we assume text or we'd need to update gh_client.put_file
            success, err = self.gh_client.put_file(
                repo_path,
                content if not is_binary else content.decode("latin-1"),  # Temporary hack for binary
                f"provision {repo_path}",
                default_branch,
            )
            if not success:
                click.echo(click.style(f"Failed to sync file {repo_path}: {err}", fg="red"))

        # 4. Ensure target branch exists and is updated
        if target_branch != default_branch:
            branch_info = self.gh_client.get_branch_info(target_branch)
            if not branch_info:
                click.echo(f"Creating branch {target_branch} from {default_branch}...")
                success, err = self.gh_client.create_branch(target_branch, default_branch)
                if not success:
                    click.echo(click.style(f"Failed to create branch {target_branch}: {err}", fg="red"))
                    return

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
