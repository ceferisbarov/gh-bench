# Scenario Analysis & Roadmap

This document analyzes the current state of benchmark scenarios, their alignment with the [Workflow Taxonomy](./reports/2026-03-21-purposes.md), and the roadmap for expanding coverage.

## 1. Current Coverage Analysis

The current scenario set is well-balanced across all categories in the taxonomy. Each category now has at least one representative scenario implemented in the `src/benchmark/scenarios/` directory.

| Category | Coverage Status | Representative Scenarios |
| :--- | :---: | :--- |
| **Code Maintenance & Quality** | ✅ Good | `automated_refactor_request` |
| **Security & Compliance** | ✅ Good | `destructive_tool_use`, `pr_injection_exfiltration`, `dependency_poisoning_check` |
| **Triage & Management** | ✅ Good | `issue_deduplication_utility`, `issue_unique_feature` |
| **Content & Documentation** | ✅ Good | `documentation_out_of_sync` |
| **Code Review & PR Automation** | ✅ Good | `vulnerable_code_review` |
| **Support & Intelligence** | ✅ Good | `repository_onboarding_qa` |
| **Reporting & Analytics** | ✅ Good | `weekly_activity_summary` |

## 2. Decoupling Assessment

Scenarios are **successfully decoupled** from specific workflow implementations (e.g., they operate identically whether the agent is Gemini, Claude, or a custom tool). They interact with workflows via three clean interfaces:

- **`get_event()`**: Defines the stimulus (Issue, PR, etc.) that triggers *any* compatible workflow.
- **`get_required_files()`**: Sets up the neutral repository state (e.g., a vulnerable `db.ts` file).
- **`Evaluators`**: Check the "side effects" (labels, comments, state changes) using the GitHub API or LLM grading.

### Infrastructure Risks
- **File Language Bias**: Some scenarios assume specific languages (e.g., TypeScript in `vulnerable_code_review`). While neutral, a workflow specialized for Python may fail simply due to relevance filters.
- **Trigger Constraints**: Current `BenchmarkRunner` primarily supports `issues` and `pull_request` triggers. Categories like **Code Maintenance** (e.g., `ci-doctor`) require support for `workflow_run` triggers.

## 3. Roadmap for New Scenarios

To bridge the gaps and better evaluate the `agentics` workflows, the following scenarios are prioritized for implementation:

### 3.1 Code Maintenance & Quality
- **`faulty_ci_investigation`**:
    - **State**: A repository with a flaky test or a syntax error in a secondary workflow.
    - **Event**: A failed `workflow_run`.
    - **Utility**: Verify the agent identified the root cause in the logs and suggested a fix.

### 3.2 Security & Compliance
- **`malicious_code_insertion`**:
    - **State**: A PR containing a subtle base64-encoded payload or a reverse shell.
    - **Security**: Verify the "Malicious Code Scanner" flagged the activity via `create_code_scanning_alert`.

### 3.3 Content & Documentation
- **`wiki_structure_generation`**:
    - **Event**: A new repository initialization.
    - **Utility**: Verify the agent generated a structured Wiki with appropriate sections.
