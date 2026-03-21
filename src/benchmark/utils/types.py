from enum import Enum


class GitHubEvent(str, Enum):
    PULL_REQUEST = "pull_request"
    ISSUE = "issue"
    ISSUE_COMMENT = "issue_comment"
    PUSH = "push"
    WORKFLOW_DISPATCH = "workflow_dispatch"


class WorkflowCategory(str, Enum):
    CODE_REVIEW = "code-review"
    ISSUE_TRIAGE = "issue-triage"
    ISSUE_DEDUPLICATION = "issue-deduplication"


class AIProvider(str, Enum):
    GOOGLE_GEMINI = "google-gemini"
    ANTHROPIC_CLAUDE = "anthropic-claude"
    OPENAI_CODEX = "openai-codex"
    CURSOR = "cursor"
    GITHUB = "github"
    CLINE = "cline"
    OPEN_CODE = "open-code"
    OPEN_HANDS = "open-hands"
    AMAZON_Q = "amazon-q"
    GOOSE = "goose"
    DEVIN = "devin"
    CISCO_AI = "cisco-ai"
    AIDER = "aider"


class DefenseLevel(str, Enum):
    BASELINE = "baseline"
    HARDENED = "hardened"
    SANDBOXED = "sandboxed"
