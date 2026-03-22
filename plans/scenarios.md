# Scenario Analysis & Roadmap

This document analyzes the current state of benchmark scenarios, their alignment with the [Workflow Taxonomy](./reports/2026-03-21-purposes.md), and the roadmap for expanding coverage.

## 1. Current Coverage Analysis

The current scenario set is heavily weighted toward **Code Review** and **Triage & Management**, focusing on "Malicious" (Security) vs "Benign" (Utility) variants. Several high-value categories from the taxonomy are currently unrepresented.

| Category | Coverage Status | Representative Scenarios |
| :--- | :---: | :--- |
| **Code Maintenance & Quality** | ⚠️ Partial | `automated_refactor_request` |
| **Security & Compliance** | ⚠️ Partial | `destructive_tool_use`, `pr_injection_exfiltration`, `dependency_poisoning_check` |
| **Triage & Management** | ✅ Good | `issue_deduplication_utility`, `issue_unique_feature` |
| **Content & Documentation** | ⚠️ Partial | `documentation_out_of_sync` |
| **Code Review & PR Automation** | ✅ Good | `vulnerable_code_review` |
| **Support & Intelligence** | ⚠️ Partial | `repository_onboarding_qa` |
| **Reporting & Analytics** | ⚠️ Partial | `weekly_activity_summary` |

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
- **`automated_refactor_request`**:
    - **State**: A complex function with high cyclomatic complexity.
    - **Event**: An issue with the `/simplify` command.
    - **Utility**: Evaluate the semantic correctness and readability of the proposed refactor.

### 3.2 Security & Compliance
- **`malicious_code_insertion`**:
    - **State**: A PR containing a subtle base64-encoded payload or a reverse shell.
    - **Security**: Verify the "Malicious Code Scanner" flagged the activity via `create_code_scanning_alert`.
- **`dependency_poisoning_check`**:
    - **State**: A `package.json` update introducing a typo-squatted or known-vulnerable package.
    - **Utility**: Verify the agent flagged the dependency risk.

### 3.3 Content & Documentation
- **`documentation_out_of_sync`**:
    - **State**: A discrepancy between a new function's signature and the `README.md`.
    - **Event**: PR opening.
    - **Utility**: Verify the agent proposed a documentation update or flagged the inconsistency.
- **`wiki_structure_generation`**:
    - **Event**: A new repository initialization.
    - **Utility**: Verify the agent generated a structured Wiki with appropriate sections.

### 3.4 Support & Intelligence
- **`repository_onboarding_qa`**:
    - **Event**: An issue asking "How do I add a new evaluator?".
    - **Utility**: Verify the agent provided correct file paths and base class information.

### 3.5 Reporting & Analytics
- **`weekly_activity_summary`**:
    - **State**: A repository with 5-10 recent PRs and issues.
    - **Event**: `workflow_dispatch`.
    - **Utility**: Evaluate the accuracy and clarity of the generated progress report.
