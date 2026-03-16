import json
import os

import click


@click.group()
def cli():
    """AI-Powered GitHub Workflows Security Benchmark CLI."""
    pass


@cli.group()
def list():
    """List benchmark components."""
    pass


@list.command(name="workflows")
def list_workflows():
    """List available workflows."""
    workflows_dir = "src/benchmark/workflows"
    if not os.path.exists(workflows_dir):
        click.echo("Workflows directory not found.")
        return

    workflows = [d for d in os.listdir(workflows_dir) if os.path.isdir(os.path.join(workflows_dir, d))]
    for w in workflows:
        metadata_path = os.path.join(workflows_dir, w, "metadata.json")
        if os.path.exists(metadata_path):
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
                name = metadata.get("name", "No name")
                description = metadata.get("description", "No description")
                click.echo(f"- {w}: {name} ({description})")
        else:
            click.echo(f"- {w}: No metadata found.")


@list.command(name="scenarios")
def list_scenarios():
    """List available scenarios."""
    scenarios_dir = "src/benchmark/scenarios"
    if not os.path.exists(scenarios_dir):
        click.echo("Scenarios directory not found.")
        return

    scenarios = [f for f in os.listdir(scenarios_dir) if f.endswith(".py") and f != "__init__.py"]
    for s in scenarios:
        click.echo(f"- {s}")


@cli.command()
@click.option("--workflow", required=True, help="Workflow ID to run.")
@click.option("--scenario", required=True, help="Scenario ID to run.")
@click.option(
    "--repo-prefix",
    default=lambda: os.environ.get("GITHUB_REPO_PREFIX", "benchmark-run"),
    help="Target GitHub repository prefix (will be expanded with random string).",
)
@click.option(
    "--cleanup/--no-cleanup",
    default=True,
    help="Automatically delete the GitHub repository after the run. Use --no-cleanup for debugging.",
)
def run(workflow, scenario, repo_prefix, cleanup):
    """Run a specific benchmark test."""
    from .runner import BenchmarkRunner

    runner = BenchmarkRunner(os.getcwd(), repo_prefix=repo_prefix)
    click.echo(f"Running benchmark on {runner.repo}: workflow={workflow}, scenario={scenario}")
    result = runner.run(workflow, scenario, cleanup=cleanup)

    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"))
    else:
        click.echo("\n" + click.style("--- Benchmark Evaluation ---", bold=True))
        analysis = result.get("analysis", {})
        click.echo(f"Utility Achieved: {analysis.get('utility_achieved', False)}")
        click.echo(f"Security Breached: {analysis.get('security_breached', False)}")
        click.echo(click.style("----------------------------", bold=True))
        click.echo(f"Message: {result.get('message')}")


@cli.command()
@click.option(
    "--prefix",
    default="benchmark-run",
    help="Prefix of repositories to delete.",
)
@click.option("--force", is_flag=True, help="Skip confirmation prompt.")
def cleanup(prefix, force):
    """Delete all benchmark repositories with a specific prefix."""
    from .utils.gh_client import GitHubClient

    gh = GitHubClient()
    click.echo(f"Searching for repositories with prefix '{prefix}'...")
    repos = gh.list_repos(limit=100)

    # Filter by prefix (checking both name and nameWithOwner)
    to_delete = [r["nameWithOwner"] for r in repos if r["name"].startswith(prefix)]

    if not to_delete:
        click.echo("No matching repositories found.")
        return

    click.echo(f"Found {len(to_delete)} repositories:")
    for repo in to_delete:
        click.echo(f" - {repo}")

    if not force and not click.confirm("\nAre you sure you want to delete these repositories?"):
        click.echo("Aborted.")
        return

    for repo_name in to_delete:
        click.echo(f"Deleting {repo_name}...")
        client = GitHubClient(repo=repo_name)
        success, err = client.delete_repo()
        if not success:
            click.echo(click.style(f"Failed to delete {repo_name}: {err}", fg="red"))
        else:
            click.echo(click.style(f"Successfully deleted {repo_name}", fg="green"))


@cli.command()
def report():
    """Generate a summary of previous runs from the 'runs/' directory."""
    runs_dir = "runs"
    if not os.path.exists(runs_dir):
        click.echo("No runs found.")
        return

    click.echo(click.style(f"{'Timestamp':<25} {'Workflow':<20} {'Scenario':<25} {'Utility':<8} {'Security':<8}", bold=True))
    click.echo("-" * 90)

    # List subdirectories sorted by timestamp (name)
    run_folders = sorted([d for d in os.listdir(runs_dir) if os.path.isdir(os.path.join(runs_dir, d))], reverse=True)

    for folder in run_folders:
        metadata_path = os.path.join(runs_dir, folder, "metadata.json")
        if os.path.exists(metadata_path):
            with open(metadata_path, "r") as f:
                try:
                    data = json.load(f)
                    analysis = data.get("analysis", {})
                    click.echo(
                        f"{data.get('timestamp'):<25} "
                        f"{data.get('workflow'):<20} "
                        f"{data.get('scenario'):<25} "
                        f"{str(analysis.get('utility_achieved')):<8} "
                        f"{str(analysis.get('security_breached')):<8}"
                    )
                except json.JSONDecodeError:
                    pass


if __name__ == "__main__":
    cli()
