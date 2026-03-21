# Project Concerns & Technical Debt

- [ ] Suboptimal fixed-interval polling in `BenchmarkRunner` for workflow completion.
- [ ] Potential command injection risk in `GitHubClient.run_gh` from unsanitized scenario data.
- [ ] Inconsistent mix of `gh` CLI and `gh api` calls in `GitHubClient`.
    - 1. Replace with PyGitHub
    - 2. Or replace all `gh` subprocess calls with direct REST API calls
- [ ] Non-standard error handling (returning dictionaries instead of raising exceptions).
- [ ] Sparse unit test coverage for core logic-heavy components like `Analyzer` and `Runner`.
- [ ] Sparse integration test coverage
- [ ] Use `AbstractScenario` to store (fork id if exists) OR use `contents` subfolder to contain the temporary repo contents
  (contents should be tied to the scenario, not the workflow)
- [ ] Excessive reliance on `time.sleep()` for GitHub consistency; needs robust polling with backoff.
- [ ] Limited attack signatures in `BenchmarkAnalyzer` (misses data exfiltration and unauthorized API calls).
- [ ] run multiple cases at once, aggregate metrics
- [ ] if temporary repo exists, it should throw error, not modify the repo
- [ ] simulate issues/prs/comments created by owner/member/external 
- [ ] cant use keywors on utility and security functions
- [ ] need to log everything before deleting the repo
- [ ] multiple workflows: for now, we poll for ANY workflow. this may require a better solution 
  (maybe an unintended workflow was triggered, which would result in unpredictable behavior)
- [ ] we should comply with githubs terms:
  - secondary rate limits (10–20 repositories in rapid succession or more than 500 per hour.)
  - move to self-hosted runners for large-scale runs
- [x] fix metadata format & update metadata for existing workflows
- [ ] MUST BE model agnostic
- [x] create labels: coding vs. triage, pr vs. issue, analysis, create prs (Implemented via Workflow Taxonomy)
- [ ] for some labels (e.g., not issue triage): collect enough scenarios to quantify utility vs. security trade-off
- [ ] collect at least ~5 meaningfully distinct coding workflows
- [ ] how to prevent actually leaking api keys
- [ ] remove teardown since repos are temporary anyway
- [ ] create a library
- [ ] compatibility check between workflows and scenarios
- [ ] bulk runs

## New Technical Challenges
- **Trigger Limitations**: `BenchmarkRunner` currently lacks support for `workflow_run` events, which are required for scenarios like CI failure investigation.
- **Scenario Coverage Gap**: Missing scenarios for 4 out of 7 taxonomy categories (Content/Docs, Support/Intelligence, Reporting/Analytics, Code Maintenance).
- **Environment Leakage**: Need a more robust way to ensure `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` are not inadvertently leaked during malicious runs (canary detection in logs is a start).
