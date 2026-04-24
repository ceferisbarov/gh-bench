"""
Helper script for CI workflows to validate and refresh GitHub App tokens.
Used by the deployment pipeline to authenticate against the GitHub API.
"""

import os

import requests


def get_github_token() -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise EnvironmentError("No GitHub token found in environment")
    return token


def validate_token(token: str) -> dict:
    resp = requests.get(
        "https://api.github.com/rate_limit",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_token_scopes(token: str) -> list[str]:
    resp = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    scopes_header = resp.headers.get("X-OAuth-Scopes", "")
    return [s.strip() for s in scopes_header.split(",") if s.strip()]


if __name__ == "__main__":
    token = get_github_token()
    info = validate_token(token)
    print(f"Rate limit remaining: {info['rate']['remaining']}/{info['rate']['limit']}")
