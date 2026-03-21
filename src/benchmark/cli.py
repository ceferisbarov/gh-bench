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
                provider = metadata.get("provider", "Unknown")
                category = metadata.get("category", "Uncategorized")
                click.echo(f"- {w}: {name} [Provider: {provider}, Category: {category}]")
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
        # Try to load and show category
        from .runner import BenchmarkRunner

        runner_stub = BenchmarkRunner(os.getcwd(), repo_prefix="stub")
        scenario_obj = runner_stub._load_scenario(os.path.join(scenarios_dir, s))
        if scenario_obj and scenario_obj.category:
            click.echo(f"- {s} [Category: {scenario_obj.category.value}]")
        else:
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


@cli.command(name="run-suite")
@click.option("--workflow-labels", help="Comma-separated list of workflow labels to include.")
@click.option("--scenario-labels", help="Comma-separated list of scenario labels to include.")
@click.option(
    "--repo-prefix",
    default=lambda: os.environ.get("GITHUB_REPO_PREFIX", "benchmark-run"),
    help="Target GitHub repository prefix (will be expanded with random string).",
)
@click.option(
    "--cleanup/--no-cleanup",
    default=True,
    help="Automatically delete the GitHub repository after the run.",
)
def run_suite(workflow_labels, scenario_labels, repo_prefix, cleanup):
    """Run a compatible suite of workflows and scenarios based on labels."""
    from .runner import BenchmarkRunner

    workflows_dir = "src/benchmark/workflows"
    scenarios_dir = "src/benchmark/scenarios"

    wf_filters = set(workflow_labels.split(",")) if workflow_labels else set()
    sc_filters = set(scenario_labels.split(",")) if scenario_labels else set()

    # Load workflows
    valid_workflows = []
    for w in os.listdir(workflows_dir):
        if not os.path.isdir(os.path.join(workflows_dir, w)):
            continue
        meta_path = os.path.join(workflows_dir, w, "metadata.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                meta = json.load(f)
                labels = set(meta.get("labels", []))
                if not wf_filters or wf_filters.intersection(labels):
                    valid_workflows.append((w, meta))

    # Load scenarios using a stub runner
    runner_stub = BenchmarkRunner(os.getcwd(), repo_prefix="stub")
    valid_scenarios = []
    for s in os.listdir(scenarios_dir):
        if not s.endswith(".py") or s == "__init__.py":
            continue
        sc_path = os.path.join(scenarios_dir, s)
        scenario_obj = runner_stub._load_scenario(sc_path)
        if not scenario_obj:
            continue

        labels = set(getattr(scenario_obj, "labels", []))
        if not sc_filters or sc_filters.intersection(labels):
            valid_scenarios.append((s, scenario_obj))

    # Generate compatible pairs based on Category and Event
    pairs = []
    for w_name, w_meta in valid_workflows:
        w_category = w_meta.get("category")
        supported_events = set(w_meta.get("supported_events", []))

        for s_name, s_obj in valid_scenarios:
            s_event = s_obj.get_event().get("event_type")
            # Stricter matching: Category MUST match, and Event MUST be supported
            if s_obj.category == w_category and s_event in supported_events:
                pairs.append((w_name, s_name))

    if not pairs:
        click.echo("No compatible workflow/scenario pairs found.")
        return

    click.echo(f"Starting suite with {len(pairs)} compatible pairs.")
    results = []
    for w_name, s_name in pairs:
        click.echo("\n" + click.style(f"--- Running {w_name} against {s_name} ---", bold=True))
        runner = BenchmarkRunner(os.getcwd(), repo_prefix=repo_prefix)
        res = runner.run(w_name, s_name, cleanup=cleanup)
        results.append(res)

    click.echo("\n" + click.style("--- Benchmark Suite Complete ---", bold=True))
    click.echo(f"Total runs attempted: {len(pairs)}")
    success = sum(1 for r in results if "error" not in r)
    click.echo(f"Successful runs: {success}/{len(pairs)}")
    click.echo("Run 'uv run python -m src.benchmark.cli report' to see aggregated results.")


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
