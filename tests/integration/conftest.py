import os

import pytest

from src.benchmark.utils.gh_client import GitHubClient


def resolve_owner():
    if os.environ.get("GITHUB_OWNER"):
        return os.environ.get("GITHUB_OWNER")
    stdout, _ = GitHubClient().run_gh(["api", "user", "-q", ".login"], use_repo=False)
    return stdout.strip() if stdout else "unknown"


@pytest.fixture(scope="session")
def repo_owner():
    return resolve_owner()
