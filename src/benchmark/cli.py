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
    """List available workflows with their categories and supported events."""
    workflows_dir = "src/benchmark/workflows"
    if not os.path.exists(workflows_dir):
        click.echo("Workflows directory not found.")
        return

    workflows = sorted([d for d in os.listdir(workflows_dir) if os.path.isdir(os.path.join(workflows_dir, d))])
    for w in workflows:
        metadata_path = os.path.join(workflows_dir, w, "metadata.json")
        if os.path.exists(metadata_path):
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
                category = metadata.get("category", "uncategorized")
                events = ", ".join(metadata.get("supported_events", []))
                click.echo(f"- {w:25} | Category: {category:20} | Events: {events}")
        else:
            click.echo(f"- {w:25} | No metadata found.")


def _discover_scenarios(scenarios_dir, runner_stub):
    """Recursively finds and loads all scenarios."""
    valid_scenarios = []
    for root, dirs, files in os.walk(scenarios_dir):
        potential_paths = []
        if "scenario.py" in files:
            potential_paths.append(root)
        else:
            for f in files:
                if f.endswith(".py") and f not in ["__init__.py", "scenario.py"]:
                    potential_paths.append(os.path.join(root, f))

        for sc_path in potential_paths:
            scenario_obj = runner_stub._load_scenario(sc_path)
            if scenario_obj:
                sc_name = os.path.basename(sc_path).replace(".py", "")
                valid_scenarios.append((sc_name, scenario_obj))
    return sorted(valid_scenarios, key=lambda x: x[0])


@list.command(name="scenarios")
def list_scenarios():
    """List available scenarios with their categories and event types."""
    scenarios_dir = "src/benchmark/scenarios"
    if not os.path.exists(scenarios_dir):
        click.echo("Scenarios directory not found.")
        return

    from .runner import BenchmarkRunner

    runner_stub = BenchmarkRunner(os.getcwd(), repo_prefix="stub")
    scenarios = _discover_scenarios(scenarios_dir, runner_stub)

    for s_name, s_obj in scenarios:
        category = s_obj.category.value if s_obj.category else "none"
        event = s_obj.get_event().get("event_type", "unknown")
        s_type = s_obj.scenario_type.value if hasattr(s_obj, "scenario_type") else "benign"
        click.echo(f"- {s_name:25} | Type: {s_type:10} | Category: {category:20} | Event: {event}")


@cli.command()
@click.option("--workflow", required=True, help="Workflow ID to run.")
@click.option("--scenario", required=True, help="Scenario ID to run (or 'all' for all compatible scenarios).")
@click.option(
    "--repo-prefix",
    default=lambda: os.environ.get("GITHUB_REPO_PREFIX", "benchmark-run"),
    help="Target GitHub repository prefix.",
)
@click.option(
    "--cleanup/--no-cleanup",
    default=True,
    help="Automatically delete the GitHub repository after the run.",
)
@click.option(
    "--unaligned",
    help="Use unaligned model for red-teaming.",
    is_flag=True,
)
@click.option(
    "--log-llm-input",
    is_flag=True,
    help="Reconstruct and print the effective LLM prompt before triggering the run, and save it to runs/*/llm_input.txt.",
)
@click.option(
    "--attack",
    "attack_id",
    default=None,
    help="Attack type to apply (autoinject, static). Omit to use the scenario's hardcoded payload.",
)
@click.option(
    "--attack-payload",
    default=None,
    help="Inline payload string or path to a payload file. Used with --attack static.",
)
def run(workflow, scenario, repo_prefix, cleanup, unaligned, log_llm_input, attack_id, attack_payload):
    """Run benchmark tests."""
    from .runner import BenchmarkRunner

    workflows_dir = "src/benchmark/workflows"
    scenarios_dir = "src/benchmark/scenarios"

    workflow_path = os.path.join(workflows_dir, workflow)
    if not os.path.isdir(workflow_path):
        click.echo(click.style(f"Error: Workflow '{workflow}' not found.", fg="red"))
        return

    meta_path = os.path.join(workflow_path, "metadata.json")
    workflow_meta = {}
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            workflow_meta = json.load(f)

    w_category = workflow_meta.get("category")
    supported_events = set(workflow_meta.get("supported_events", []))

    if scenario.lower() == "all":
        runner_stub = BenchmarkRunner(os.getcwd(), repo_prefix="stub")
        click.echo(f"Identifying compatible scenarios for workflow '{workflow}'...")

        valid_scenarios = _discover_scenarios(scenarios_dir, runner_stub)
        scenarios_to_run = []
        for s_name, s_obj in valid_scenarios:
            s_event = s_obj.get_event().get("event_type")
            if s_obj.category == w_category and s_event in supported_events:
                scenarios_to_run.append(s_name)

        if not scenarios_to_run:
            click.echo(click.style(f"No compatible scenarios found for workflow '{workflow}'.", fg="yellow"))
            return

        click.echo(f"Found {len(scenarios_to_run)} compatible scenarios: {', '.join(scenarios_to_run)}")

        for s_name in scenarios_to_run:
            click.echo("\n" + click.style(f"--- Running {workflow} against {s_name} ---", bold=True))
            runner = BenchmarkRunner(os.getcwd(), repo_prefix=repo_prefix)
            result = runner.run(
                workflow,
                s_name,
                attack_id=attack_id,
                attack_payload=attack_payload,
                cleanup=cleanup,
                unaligned=unaligned,
                log_llm_input=log_llm_input,
            )
            _display_run_result(result)
    else:
        runner = BenchmarkRunner(os.getcwd(), repo_prefix=repo_prefix)
        click.echo(f"Running benchmark on {runner.repo_name}: workflow={workflow}, scenario={scenario}")
        result = runner.run(
            workflow,
            scenario,
            attack_id=attack_id,
            attack_payload=attack_payload,
            cleanup=cleanup,
            unaligned=unaligned,
            log_llm_input=log_llm_input,
        )
        _display_run_result(result)


def _display_run_result(result):
    """Helper to display the result of a single benchmark run."""
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
@click.option("--workflow-labels", help="Comma-separated list of workflow labels to filter by.")
@click.option("--scenario-labels", help="Comma-separated list of scenario labels to filter by.")
@click.option("--scenario-type", help="Filter by scenario type (benign/malicious).")
@click.option("--event", help="Filter by event type.")
@click.option(
    "--repo-prefix",
    default=lambda: os.environ.get("GITHUB_REPO_PREFIX", "benchmark-run"),
    help="Target GitHub repository prefix.",
)
@click.option(
    "--cleanup/--no-cleanup",
    default=True,
    help="Automatically delete the GitHub repository after the run.",
)
@click.option(
    "--unaligned",
    help="Use unaligned model for red-teaming.",
    is_flag=True,
)
@click.option(
    "--dry-run",
    help="List compatible pairs without executing them.",
    is_flag=True,
)
@click.option(
    "--log-llm-input",
    is_flag=True,
    help="Reconstruct and print the effective LLM prompt before each run.",
)
def run_suite(
    workflow_labels, scenario_labels, scenario_type, event, repo_prefix, cleanup, unaligned, dry_run, log_llm_input
):
    """Run a suite of compatible workflows and scenarios."""
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
                supported_events = set(meta.get("supported_events", []))

                if wf_filters and not wf_filters.intersection(labels):
                    continue
                if event and event not in supported_events:
                    continue
                valid_workflows.append((w, meta))

    # Load scenarios
    runner_stub = BenchmarkRunner(os.getcwd(), repo_prefix="stub")
    all_scenarios = _discover_scenarios(scenarios_dir, runner_stub)
    valid_scenarios = []
    for s_name, s_obj in all_scenarios:
        labels = set(getattr(s_obj, "labels", []))
        s_event = s_obj.get_event().get("event_type")
        s_type = s_obj.scenario_type.value if hasattr(s_obj, "scenario_type") else "benign"

        if sc_filters and not sc_filters.intersection(labels):
            continue
        if scenario_type and scenario_type.lower() != s_type.lower():
            continue
        if event and event != s_event:
            continue
        valid_scenarios.append((s_name, s_obj))

    # Generate compatible pairs
    pairs = []
    for w_name, w_meta in valid_workflows:
        w_category = w_meta.get("category")
        supported_events = set(w_meta.get("supported_events", []))

        for s_name, s_obj in valid_scenarios:
            s_event = s_obj.get_event().get("event_type")
            if s_obj.category == w_category and s_event in supported_events:
                pairs.append((w_name, s_name))

    if not pairs:
        click.echo("No compatible workflow/scenario pairs found.")
        return

    if dry_run:
        click.echo(click.style(f"DRY RUN: Found {len(pairs)} compatible pairs:", bold=True))
        for w_name, s_name in pairs:
            click.echo(f" - Workflow: {w_name:20} | Scenario: {s_name}")
        return

    click.echo(f"Starting suite with {len(pairs)} compatible pairs.")
    results = []
    for w_name, s_name in pairs:
        click.echo("\n" + click.style(f"--- Running {w_name} against {s_name} ---", bold=True))
        runner = BenchmarkRunner(os.getcwd(), repo_prefix=repo_prefix)
        res = runner.run(w_name, s_name, cleanup=cleanup, unaligned=unaligned, log_llm_input=log_llm_input)
        if "error" in res:
            click.echo(click.style(f"Error: {res['error']}", fg="red"))
        results.append(res)

    click.echo("\n" + click.style("--- Benchmark Suite Complete ---", bold=True))
    success = sum(1 for r in results if "error" not in r)
    click.echo(f"Runs: {success}/{len(pairs)} successful.")


@cli.command()
@click.option("--workflow", required=True, help="Workflow ID.")
@click.option("--scenario", required=True, help="Scenario ID.")
@click.option("--attack", "attack_id", required=True, help="Attack type (autoinject, static).")
@click.option(
    "--victim-model",
    default=None,
    help="OpenRouter model string for the victim (e.g. openai/gpt-5.4-2026-03-05). "
    "Defaults to ATTACK_VICTIM_MODEL env var.",
)
def preflight(workflow, scenario, attack_id, victim_model):
    """
    Single offline shot: generate a payload, send the injected prompt directly to the
    victim model, and report whether the attack succeeded. No GitHub repo needed.
    """
    from .runner import BenchmarkRunner

    runner = BenchmarkRunner(os.getcwd(), repo_prefix="preflight")
    result = runner.offline_optimize(workflow, scenario, attack_id, iterations=1, victim_model=victim_model)

    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"))
        return

    score = result["asr_curve"][0] if result["asr_curve"] else 0
    label = (
        click.style("PASS — attack worked offline", fg="green")
        if score
        else click.style("FAIL — attack did not work offline", fg="red")
    )
    click.echo(f"\nPreflight result: {label}")
    click.echo(f"Payload at: {result['runs_dir']}/best_payload.txt")
    click.echo(
        "\nNote: offline uses a plain chat call. The agentic Codex context may differ. "
        "A PASS here is a strong indicator but not a guarantee."
    )


@cli.command()
@click.option("--workflow", required=True, help="Workflow ID to run.")
@click.option("--scenario", required=True, help="Scenario ID to optimize against.")
@click.option("--attack", "attack_id", required=True, help="Attack type (autoinject, static).")
@click.option("--iterations", default=5, show_default=True, help="Number of optimization iterations.")
@click.option(
    "--offline",
    is_flag=True,
    help="Optimize using direct model calls instead of GitHub workflow runs. "
    "Fast, no repo provisioning. Requires scenario.get_preflight_evaluator().",
)
@click.option(
    "--victim-model",
    default=None,
    help="Override victim model for offline mode (OpenRouter string). " "Defaults to ATTACK_VICTIM_MODEL env var.",
)
@click.option(
    "--repo-prefix",
    default=lambda: os.environ.get("GITHUB_REPO_PREFIX", "benchmark-run"),
    help="Target GitHub repository prefix (online mode only).",
)
@click.option("--cleanup/--no-cleanup", default=True, help="Delete the repository after the run (online mode only).")
def optimize(workflow, scenario, attack_id, iterations, offline, victim_model, repo_prefix, cleanup):
    """Iteratively optimize an attack payload, writing the best result to runs/*/best_payload.txt."""
    from .runner import BenchmarkRunner

    runner = BenchmarkRunner(os.getcwd(), repo_prefix=repo_prefix)

    if offline:
        click.echo(
            f"Offline optimization: workflow={workflow}, scenario={scenario}, "
            f"attack={attack_id}, iterations={iterations}"
        )
        result = runner.offline_optimize(workflow, scenario, attack_id, iterations, victim_model=victim_model)
    else:
        click.echo(
            f"Optimizing on {runner.repo_name}: workflow={workflow}, scenario={scenario}, "
            f"attack={attack_id}, iterations={iterations}"
        )
        result = runner.optimize(workflow, scenario, attack_id, iterations, cleanup=cleanup)

    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"))
        return

    click.echo("\n" + click.style("--- Optimization Result ---", bold=True))
    click.echo(f"Final ASR : {result['final_asr']:.2f} ({sum(result['asr_curve'])}/{len(result['asr_curve'])})")
    click.echo(f"ASR curve : {result['asr_curve']}")
    click.echo(f"Runs dir  : {result['runs_dir']}")
    if result.get("best_payload"):
        click.echo(click.style("Best payload saved to runs_dir/best_payload.txt", fg="green"))


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
