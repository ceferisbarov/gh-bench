# Project Concerns & Technical Debt

- **Reliability:** Excessive reliance on `time.sleep()` for GitHub consistency; needs robust polling with backoff.
- **Performance:** Suboptimal fixed-interval polling in `BenchmarkRunner` for workflow completion.
- **Security:** Limited attack signatures in `BenchmarkAnalyzer` (misses data exfiltration and unauthorized API calls).
- **Security:** Potential command injection risk in `GitHubClient.run_gh` from unsanitized scenario data.
- **Architecture:** Inconsistent mix of `gh` CLI and `gh api` calls in `GitHubClient`.
- **Architecture:** Non-standard error handling (returning dictionaries instead of raising exceptions).
- **Maintenance:** Lack of cleanup/reset logic in `RepoProvisioner` leads to repository state pollution between runs.
- **Testing:** Sparse unit test coverage for core logic-heavy components like `Analyzer` and `Runner`.
