# AI-Powered GitHub Workflows Security Benchmark

A modular framework for benchmarking, analyzing, and securing AI-driven automation in GitHub Workflows.

<div style="border-left: 4px solid red; padding: 10px; background:#ffe6e6;">
<strong>WARNING:</strong> We strongly suggest using a burner GitHub account while using this benchmark.
</div>

## Project Structure

- `actions/`: Forks and local versions of AI-powered GitHub Actions (`gemini-cli`, `claude-code-action`).
- `src/benchmark/`: Core Python orchestrator and CLI.
  - `src/benchmark/workflows/`: Dataset of workflow definitions with security metadata.
  - `src/benchmark/scenarios/`: Python-based test cases for evaluating Utility and Security.
  - `src/benchmark/utils/`: Support utilities for GitHub interaction and repo provisioning.

## Getting Started

### Prerequisites
- Python 3.13+
- [uv](https://github.com/astral-sh/uv)
- [GitHub CLI (gh)](https://cli.github.com/) - Authenticated with `repo` and `workflow` scopes.

### Installation
```bash
uv sync
```

## Usage

The benchmark is managed via a CLI. Use `uv run python -m src.benchmark.cli` to interact with it.

### 1. Discover Components
List available workflows and scenarios with their compatibility metadata (Category and Supported Events):
```bash
# List workflows
uv run python -m src.benchmark.cli list workflows

# List scenarios
uv run python -m src.benchmark.cli list scenarios
```

### 2. Run Benchmarks
You can run a specific test case or an entire compatible suite.

#### Run a Single Test
```bash
# Set your API keys
export OPENROUTER_API_KEY=your_key_here

# Run a specific workflow against a scenario
uv run python -m src.benchmark.cli run --workflow codex-pr-review --scenario vulnerable_code_review --unaligned
```

#### Run All Compatible Scenarios for a Workflow
This automatically identifies and runs all scenarios that match the workflow's category and event type:
```bash
uv run python -m src.benchmark.cli run --workflow codex-pr-review --scenario all --unaligned
```

#### Run a Filtered Suite (Dry Run)
Identify compatible pairs based on labels or event types without executing them:
```bash
uv run python -m src.benchmark.cli run-suite --workflow-labels code-review --dry-run
```

### 3. Cleanup & Reporting
```bash
# Aggregated results of previous runs
uv run python -m src.benchmark.cli report

# Bulk delete benchmark repositories from your GitHub account
uv run python -m src.benchmark.cli cleanup --prefix benchmark-run
```

### 3. Adding New Content
- **Workflows:** Add a new folder in `src/benchmark/workflows/` containing a `workflow.yml` and a `metadata.json`.
- **Scenarios:** Add a new `.py` file in `src/benchmark/scenarios/` inheriting from `AbstractScenario`.

## Development
- [System Architecture](./plans/architecture.md)
- [Roadmap & Status](./plans/concerns.md)
- [Contribution guideline](./CONTRIBUTING.md)

Contact: cefer dot isbarov at gmail dot com
