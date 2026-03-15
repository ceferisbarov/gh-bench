# AI-Powered GitHub Workflows Security Benchmark

A modular framework for benchmarking, analyzing, and securing AI-driven automation in GitHub Workflows.

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
- [Gemini CLI](https://github.com/google-gemini/gemini-cli) (for running Gemini-based benchmarks)
- [Claude Code Action](https://github.com/anthropics/claude-code-action) (for running Claude-based benchmarks)

### Installation
```bash
uv sync
```

## Usage

The benchmark is managed via a CLI. Use `uv run python -m src.benchmark.cli` to interact with it.

### 1. List Available Components
View the available workflows and their defense levels:
```bash
uv run python -m src.benchmark.cli list workflows
```

View the available test scenarios:
```bash
uv run python -m src.benchmark.cli list scenarios
```

### 2. Run a Benchmark
To run a specific workflow against a scenario:
```bash
# Set your API keys (as needed by the workflow)
export GEMINI_API_KEY=your_api_key_here
export ANTHROPIC_API_KEY=your_api_key_here

# Run a baseline workflow with a malicious scenario
uv run python -m src.benchmark.cli run --workflow pr-reviewer --scenario demonstration_attack.py

# Run a Claude-powered workflow
uv run python -m src.benchmark.cli run --workflow claude-issue-deduplication --scenario issue_duplicate_bug.py
```

### 3. Adding New Content
- **Workflows:** Add a new folder in `src/benchmark/workflows/` containing a `workflow.yml` and a `metadata.json`.
- **Scenarios:** Add a new `.py` file in `src/benchmark/scenarios/` inheriting from `AbstractScenario`.

## Documentation
- [System Architecture](./plans/architecture.md)
- [Roadmap & Status](./plans/general.md)
