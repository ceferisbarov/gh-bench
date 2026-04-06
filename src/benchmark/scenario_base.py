import json
import os
from abc import ABC, abstractmethod

from .evaluators import AlwaysFailEvaluator, Evaluator
from .utils.types import ScenarioType, WorkflowCategory


class AbstractScenario(ABC):
    """
    Abstract Base Class for all benchmark scenarios.
    Each scenario defines its own GitHub event, state preparation, and evaluation logic.
    """

    labels = []
    category: WorkflowCategory = None
    scenario_type: ScenarioType = ScenarioType.BENIGN

    def __init__(self, workspace_dir):
        self.workspace_dir = workspace_dir
        self.scenario_dir = None
        self.runtime_state = {}

    def get_required_files(self) -> dict:
        """
        Returns a dictionary of {repo_path: local_path_or_content}
        for static files needed in the repo.
        Defaults to discovering files in a 'contents/' directory next to the scenario.
        """
        files = {}
        if self.scenario_dir:
            contents_dir = os.path.join(self.scenario_dir, "contents")
            if os.path.isdir(contents_dir):
                for root, _, filenames in os.walk(contents_dir):
                    for filename in filenames:
                        abs_path = os.path.join(root, filename)
                        rel_path = os.path.relpath(abs_path, contents_dir)
                        files[rel_path] = abs_path
        return files

    def get_required_secrets(self) -> list[str]:
        """
        Returns a list of secret names (strings) that must be set in the repository.
        The runner will attempt to fetch these from local environment variables.
        """
        return []

    def get_secrets(self) -> dict[str, str]:
        """
        Returns a dictionary of {name: value} for secrets defined by the scenario.
        These will be set in the repository automatically.
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

    def get_utility_evaluator(self) -> Evaluator:
        """
        Returns an Evaluator instance to assess Utility.
        Defaults to AlwaysFailEvaluator.
        """
        return AlwaysFailEvaluator()

    def get_security_evaluator(self) -> Evaluator:
        """
        Returns an Evaluator instance to assess Security.
        Defaults to AlwaysFailEvaluator (meaning not breached).
        """
        return AlwaysFailEvaluator()

    def to_json(self):
        """Helper to export the event data to JSON format if needed."""
        return json.dumps(self.get_event(), indent=4)
