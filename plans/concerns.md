# Project Concerns & Technical Debt

- Suboptimal fixed-interval polling in `BenchmarkRunner` for workflow completion.
- Potential command injection risk in `GitHubClient.run_gh` from unsanitized scenario data.
- Inconsistent mix of `gh` CLI and `gh api` calls in `GitHubClient`.
    - 1. Replace with PyGitHub
    - 2. Or replace all `gh` subprocess calls with direct REST API calls
- Non-standard error handling (returning dictionaries instead of raising exceptions).
- Sparse unit test coverage for core logic-heavy components like `Analyzer` and `Runner`.
- Use `AbstractScenario` to store (fork id if exists) OR use `contents` subfolder to contain the temporary repo contents
  (contents should be tied to the scenario, not the workflow)
- Excessive reliance on `time.sleep()` for GitHub consistency; needs robust polling with backoff.
- Limited attack signatures in `BenchmarkAnalyzer` (misses data exfiltration and unauthorized API calls).
