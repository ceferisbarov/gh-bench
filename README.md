# AI-Powered GitHub Workflows Security Benchmark

A modular framework for benchmarking, analyzing, and securing AI-driven automation in GitHub Workflows.

## Project Structure

- `actions/`: Forks and local versions of AI-powered GitHub Actions (Gemini, Claude).
- `data/workflows/`: Dataset of workflow definitions with security metadata.
- `data/scenarios/`: Test cases including benign usage and malicious attacks (Prompt Injection, etc.).
- `src/benchmark/`: Core Python orchestrator and CLI.

## Getting Started

### Prerequisites
- Python 3.13+
- [uv](https://github.com/astral-sh/uv)
- [Gemini CLI](https://github.com/google-gemini/gemini-cli) (for running Gemini-based benchmarks)

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
# Set your API key
export GEMINI_API_KEY=your_api_key_here

# Run a baseline workflow with a malicious scenario
uv run python -m src.benchmark.cli run --workflow pr-reviewer --scenario pr-malicious-prompt-injection.json

# Run a hardened workflow with the same scenario
uv run python -m src.benchmark.cli run --workflow pr-reviewer-hardened --scenario pr-malicious-prompt-injection.json
```

### 3. Adding New Content
- **Workflows:** Add a new folder in `data/workflows/` containing a `workflow.yml` and a `metadata.json`.
- **Scenarios:** Add a new `.json` file in `data/scenarios/` following the established schema.
