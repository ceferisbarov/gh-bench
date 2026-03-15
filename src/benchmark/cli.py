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
def run(workflow, scenario, repo_prefix):
    """Run a specific benchmark test."""
    from .runner import BenchmarkRunner

    runner = BenchmarkRunner(os.getcwd(), repo_prefix=repo_prefix)
    click.echo(f"Running benchmark on {runner.repo}: workflow={workflow}, scenario={scenario}")
    result = runner.run(workflow, scenario)

    if "error" in result:
        click.echo(f"Error: {result['error']}")
    else:
        click.echo("\n--- Benchmark Evaluation ---")
        analysis = result.get("analysis", {})
        click.echo(f"Utility Achieved: {analysis.get('utility_achieved', False)}")
        click.echo(f"Security Breached: {analysis.get('security_breached', False)}")
        click.echo("----------------------------")
        click.echo(f"Message: {result.get('message')}")


@cli.command()
def report():
    """Generate a summary of previous runs."""
    click.echo("Generating report...")
    # TODO: Implement reporting logic


if __name__ == "__main__":
    cli()
