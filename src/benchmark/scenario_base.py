import json
from abc import ABC, abstractmethod


class AbstractScenario(ABC):
    """
    Abstract Base Class for all benchmark scenarios.
    Each scenario defines its own GitHub event, state preparation, and evaluation logic.
    """

    def __init__(self, workspace_dir):
        self.workspace_dir = workspace_dir

    def get_required_files(self) -> dict:
        """
        Returns a dictionary of {repo_path: local_path_or_content}
        for static files needed in the repo.
        """
        return {}

    def get_template_repo(self) -> str:
        """
        Returns the full name of a repository to fork (e.g., 'owner/repo').
        If None, a new empty repository is created.
        """
        return None

    @abstractmethod
    def setup_state(self, gh_client):
        """Prepares the repository state before the benchmark run."""
        pass

    @abstractmethod
    def teardown_state(self, gh_client):
        """Cleans up the repository state after the benchmark run."""
        pass

    @abstractmethod
    def get_event(self):
        """
        Returns a dictionary representing the GitHub event.
        Must contain 'event_type' and 'data'.
        """
        pass

    @abstractmethod
    def evaluate_utility(self, run_result, gh_client) -> bool:
        """
        Evaluates the Utility (True if success, False if failure).
        """
        pass

    @abstractmethod
    def evaluate_security(self, run_result, gh_client) -> bool:
        """
        Evaluates Security (True if BREACHED, False if SECURE).
        """
        pass

    def to_json(self):
        """Helper to export the event data to JSON format if needed."""
        return json.dumps(self.get_event(), indent=4)
