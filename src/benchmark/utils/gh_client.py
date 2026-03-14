import subprocess
import json

class GitHubClient:
    """A wrapper for the GitHub CLI (gh) to interact with repos."""
    
    def __init__(self, repo="owner/repo"):
        self.repo = repo

    def run_gh(self, args):
        """Runs a generic gh command and returns the output."""
        cmd = ["gh"] + args + ["-R", self.repo]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0 and "not authenticated" in result.stderr:
            print("Error: GitHub CLI is not authenticated. Please run 'gh auth login' or set GITHUB_TOKEN.")
        return result.stdout, result.stderr

    def get_pr_details(self, pr_number):
        """Fetches details of a Pull Request."""
        stdout, _ = self.run_gh(["pr", "view", str(pr_number), "--json", "title,body,state,comments"])
        return json.loads(stdout) if stdout else {}

    def get_issue_details(self, issue_number):
        """Fetches details of an Issue."""
        stdout, _ = self.run_gh(["issue", "view", str(issue_number), "--json", "title,body,state,comments"])
        return json.loads(stdout) if stdout else {}

    def list_files(self, branch="main"):
        """Lists files in a specific branch."""
        stdout, _ = self.run_gh(["repo", "view", "--json", "files"])
        return json.loads(stdout).get("files", []) if stdout else []

    def get_workflow_runs(self, workflow_id):
        """Fetches recent runs of a specific workflow."""
        stdout, _ = self.run_gh(["run", "list", "--workflow", workflow_id, "--json", "status,conclusion,databaseId"])
        return json.loads(stdout) if stdout else []
