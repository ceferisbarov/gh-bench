# AI-Powered GitHub Workflows: Purpose Taxonomy & Use Cases

This report classifies AI-powered GitHub workflows based on their intended purpose, analyzing examples from both the `src/benchmark/workflows` and `actions/agentics/workflows` datasets.

## 1. Code Maintenance & Quality
These workflows focus on improving the codebase's long-term health through automated investigation, refactoring, and verification.

| Use Case | Description | Examples |
| :--- | :--- | :--- |
| **CI Investigation** | Analyzes failed GitHub Actions runs to identify root causes and suggest fixes. | `ci-doctor.md`, `copilot-ci-doctor` |
| **Test Improvement** | Identifies gaps in test coverage and generates new test cases. | `daily-test-improver.md`, `claude-test-analysis` |
| **Code Simplification** | Refactors complex functions or modules to improve readability and reduce technical debt. | `code-simplifier.md` |
| **Performance Optimization** | Analyzes code for bottlenecks and suggests performance enhancements. | `daily-perf-improver.md` |
| **Formal Verification** | Progressively applies formal verification (e.g., Lean 4) to ensure mathematical correctness. | `lean-squad.md`, `copilot-lean-squad` |
| **Dead Code Detection** | Identifies and removes unused files or functions. | `daily-file-diet.md` |

## 2. Security & Compliance
Workflows that proactively scan for vulnerabilities, malicious activity, or adherence to organizational policies.

| Use Case | Description | Examples |
| :--- | :--- | :--- |
| **Malicious Code Scanning** | Scans recent commits for suspicious patterns (e.g., exfiltration, backdoors). | `daily-malicious-code-scan.md`, `copilot-malicious-scan` |
| **Guideline Enforcement** | Verifies that new PRs or issues follow specific contribution or security guidelines. | `contribution-guidelines-checker.md`, `contribution-check.md` |
| **Vulnerability Analysis** | Generates VEX (Vulnerability Exploitability eXchange) reports or analyzes dependencies. | `vex-generator.md` |
| **Accessibility Review** | Automatically reviews UI changes for accessibility violations. | `daily-accessibility-review.md` |

## 3. Triage & Management
Automated handling of the "inbox" (Issues and Discussions) to reduce maintainer burden.

| Use Case | Description | Examples |
| :--- | :--- | :--- |
| **Issue Triage** | Analyzes new issues, applies labels, and provides initial debugging notes. | `issue-triage.md`, `claude-issue-triage` |
| **Deduplication** | Identifies and labels duplicate issues to consolidate discussions. | `duplicate-code-detector.md`, `claude-issue-deduplication` |
| **Task Mining** | Extracts actionable tasks from high-volume GitHub Discussions. | `discussion-task-miner.md` |
| **Dependabot Bundling** | Aggregates multiple Dependabot PRs/Issues into single manageable units. | `dependabot-pr-bundler.md`, `dependabot-issue-bundler.md` |
| **Issue Summarization** | Provides weekly or daily summaries of active issues and progress. | `weekly-issue-summary.md` |

## 4. Content & Documentation
Workflows that treat documentation as a living entity, ensuring it stays in sync with the code.

| Use Case | Description | Examples |
| :--- | :--- | :--- |
| **Wiki Maintenance** | Automatically writes, updates, and structures GitHub Wiki pages. | `agentic-wiki-writer.md`, `copilot-wiki-writer` |
| **Doc-to-Code Sync** | Updates documentation based on code changes or vice versa. | `daily-doc-updater.md`, `unbloat-docs.md` |
| **Glossary Management** | Maintains a project-wide glossary of technical terms and concepts. | `glossary-maintainer.md` |
| **Editorial Board** | Reviews technical content for style, tone, and clarity. | `tech-content-editorial-board.md` |

## 5. Code Review & PR Automation
AI-driven feedback on Pull Requests to catch bugs, nits, and architectural issues early.

| Use Case | Description | Examples |
| :--- | :--- | :--- |
| **Semantic Code Review** | Provides deep analysis of PR changes beyond simple linting. | `claude-pr-review`, `opencode-pr-review`, `codex-pr-review` |
| **Nitpicking/Style** | Focuses on smaller stylistic issues and best practices. | `pr-nitpick-reviewer.md`, `grumpy-reviewer.md` |
| **PR Self-Healing** | Automatically applies fixes to common PR issues (e.g., linting, small bugs). | `pr-fix.md`, `claude-ci-auto-fix` |
| **Multi-Device Testing** | Coordinates and analyzes results from complex multi-device CI runs. | `daily-multi-device-docs-tester.md` |

## 6. Support & Intelligence
General-purpose assistants that can answer questions and provide context about the repository.

| Use Case | Description | Examples |
| :--- | :--- | :--- |
| **Repo-Specific Q&A** | Answers questions about how the project works or how to contribute. | `repo-ask.md`, `q.md` |
| **General Assistance** | A "Co-pilot" for the repository that can help with various tasks. | `gemini-assistant`, `cline-assistant`, `repo-assist.md` |
| **Research & Planning** | Performs background research on issues or helps plan upcoming features. | `weekly-research.md`, `daily-plan.md` |

## 7. Reporting & Analytics
Generating human-readable insights into the state of the repository and the team.

| Use Case | Description | Examples |
| :--- | :--- | :--- |
| **Repo Chronicle** | Maintains a historical log of all significant changes and decisions. | `daily-repo-chronicle.md` |
| **Team Status** | Summarizes what team members have been working on across the repo. | `daily-team-status.md`, `daily-repo-status.md` |
| **Repository Mapping** | Generates high-level maps of the codebase architecture and dependencies. | `weekly-repo-map.md` |
