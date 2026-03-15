# Contributing to AI-Powered GitHub Workflows Security Benchmark

Thank you for your interest in contributing to this project! We welcome contributions in the form of new benchmark workflows, security scenarios, bug fixes, or documentation improvements.

## How to Contribute

### 1. Adding a New Workflow
Workflows are located in `src/benchmark/workflows/`. To add a new one:
1. Create a new directory named after your workflow.
2. Add a `workflow.yml` which is the actual GitHub Action definition.
3. Add a `metadata.json` with the following structure:
   ```json
   {
     "name": "Friendly Name",
     "description": "What this workflow does",
     "defense_level": "baseline | hardened"
   }
   ```

### 2. Adding a New Scenario
Scenarios are located in `src/benchmark/scenarios/`. To add a new one:
1. Create a new `.py` file.
2. Inherit from `AbstractScenario` (from `src.benchmark.scenario_base`).
3. Implement the required methods: `setup_state`, `teardown_state`, `get_event`, `evaluate_utility`, and `evaluate_security`.

### 3. Development Setup
We use `uv` for dependency management and `pytest` for testing.
```bash
uv sync
uv run pytest
```

### 4. Code Style
We use `ruff` for linting and formatting. Please run it before submitting a PR:
```bash
uv run ruff check .
uv run ruff format .
```

## Security Disclosure
If you find a security vulnerability in the benchmark suite itself, please report it to isbarov at vt dot edu.

## License
By contributing, you agree that your contributions will be licensed under the project's existing license.
