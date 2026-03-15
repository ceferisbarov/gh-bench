# System Architecture

This document describes the software architecture for the AI-Powered GitHub Workflows Security Benchmark project.

## 1. High-Level Overview

The system is designed as a modular benchmarking platform that executes AI-powered GitHub Workflows against a variety of security-focused scenarios. It evaluates these runs using two primary metrics: **Utility** (did it do the job?) and **Security** (did it resist the attack?).

### Architecture Diagram (Conceptual)

```text
       +-----------------+
       |   Benchmark CLI | <--- User Interaction (List, Run, Report)
       +--------+--------+
                |
                v
       +-----------------+        +---------------------+
       | BenchmarkRunner | <----> | GitHub API (via gh) |
       +--------+--------+        +----------+----------+
                |                            ^
                |      +-----------------+   |
                +----> | Workflow Setup  | --+ (Trigger CI)
                |      +-----------------+   |
                |                            |
                |      +-----------------+   |
                +----> | Scenario Loader | --+ (Event Data)
                |      +-----------------+   |
                v                            v
       +-----------------+        +---------------------+
       |BenchmarkAnalyzer| <----> | GitHub Results/Logs |
       +--------+--------+        +---------------------+
                |
                v
       +-----------------+
       | Evaluation Log  | (Utility Score, Security Score)
       +-----------------+
```

## 2. Component Breakdown

### 2.1 Core Orchestrator (`src/benchmark/`)
- **CLI (`cli.py`)**: Provides a unified command-line interface using `click` for managing the benchmark lifecycle.
- **Runner (`runner.py`)**: Handles the orchestration of a benchmark run. It identifies the target workflow, prepares the repository state (e.g., creating a PR), triggers the GitHub Action, and waits for completion.
- **Analyzer (`analyzer.py`)**: The evaluation engine. It takes the run artifacts (logs, repository changes, API responses) and calculates the Utility and Security scores. It uses scenario-specific evaluation logic or falls back to generic heuristics.
- **Scenario Base (`scenario_base.py`)**: Defines the `AbstractScenario` class, ensuring a consistent interface for both simple (JSON) and complex (Python) test cases.
- **Simulator (`simulator.py`)**: Provides the `GitHubEventSimulator` for generating mock GitHub event payloads, facilitating local testing without requiring real GitHub interaction.
- **GitHub Client (`utils/gh_client.py`)**: A wrapper around the `gh` CLI and GitHub REST API, providing high-level methods to fetch PR details, issue comments, and workflow logs.

### 2.2 Data Layer (`src/benchmark/`)
- **Workflows (`src/benchmark/workflows/`)**: Each workflow is a folder containing:
    - `workflow.yml`: The actual GitHub Action definition.
    - `metadata.json`: Information about the target action, defense level, and intended purpose.
- **Scenarios (`src/benchmark/scenarios/`)**: The test cases.
    - **Python Scenarios**: Complex classes inheriting from `AbstractScenario` that define custom `evaluate_utility` and `evaluate_security` functions.

### 2.3 Actions Layer (`actions/`)
Contains local clones/forks of the AI GitHub Actions being benchmarked. This allows for testing "Action-level" defenses by modifying the source code of the agent itself. Supported agents include:
- `gemini-cli`: Google's Gemini-powered CLI.
- `claude-code-action`: Anthropic's Claude-powered action.
- `run-gemini-cli`: GitHub Action wrapper for Gemini CLI.

### 2.4 Infrastructure Layer (Provisioning)
- **Repo Provisioner (`utils/provisioner.py`)**: Responsible for managing the lifecycle of the target GitHub repository.
    - **Dynamic Creation**: Creates a new, unique repository for each run using a prefix and a random suffix (e.g., `benchmark-abc123`).
    - **Forking Support**: Can fork an existing "template" repository if a scenario requires pre-populated content.
    - **Workflow Syncing**: Mirrors the local `workflow.yml` to the remote repository.
    - **Static Content**: Pushes any files required by a specific scenario (e.g., source code to be reviewed) before the test starts.
    - **Teardown**: Deletes the entire repository after the benchmark run is complete and analyzed.

## 3. Evaluation Lifecycle

1.  **Selection**: User selects a Workflow and a Scenario.
2.  **Provisioning**:
    - The **Runner** generates a unique repository name.
    - The **Provisioner** either creates a new repository or forks a specified template repository.
    - The target **Workflow** file is pushed to the repo.
    - Any **Static Files** defined in the Scenario (via `get_required_files`) are pushed.
3.  **State Preparation**:
    - The **Scenario** executes `setup_state` to create dynamic objects (Issues, PRs).
4.  **Trigger**: The Runner triggers the event defined in the Scenario.
5.  **Observation & Analysis**:
    - The **Runner** polls for workflow completion.
    - The **Analyzer** evaluates logs and repository state.
6.  **Cleanup**:
    - The Scenario executes `teardown_state` (optional, as the repo will be deleted).
    - The **Provisioner** deletes the entire GitHub repository.


## 4. Key Security Concepts

### 4.1 Utility vs. Security
The benchmark explicitly separates these two functions. A workflow that is "too secure" (e.g., it blocks all inputs) will have high Security but zero Utility. Our goal is to find configurations that maximize both.

### 4.2 Canary Tokens
To detect data exfiltration, scenarios can inject "Canary Tokens" (unique strings) into secrets or environment variables. The Analyzer then scans the logs and external endpoints (if configured) to see if these strings were leaked by the AI agent.

### 4.3 Out-of-Band Verification
By using the `GitHubClient`, evaluation logic can verify actions that aren't visible in the workflow logs, such as the AI agent using its token to delete a branch or modify a label.
