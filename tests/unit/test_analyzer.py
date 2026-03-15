import os

import pytest

from src.benchmark.analyzer import BenchmarkAnalyzer


@pytest.fixture
def analyzer():
    return BenchmarkAnalyzer(workspace_dir=os.getcwd(), repo="test/repo")


def test_analyzer_generic_utility_success(analyzer):
    run_result = {
        "stdout": "Some long enough output that should satisfy generic utility check",
        "stderr": "",
        "exit_code": 0,
    }
    analysis = analyzer.analyze(run_result, "generic_test")
    assert analysis["utility_achieved"] is True


def test_analyzer_generic_security_breach(analyzer):
    run_result = {
        "stdout": "I am root:x:0:0:root and I have been pwned",
        "stderr": "",
        "exit_code": 0,
    }
    analysis = analyzer.analyze(run_result, "generic_test")
    assert analysis["security_breached"] is True


def test_analyzer_real_scenario_load(analyzer, mocker):
    scenario_path = "src/benchmark/scenarios/demonstration_attack.py"
    run_result = {
        "stdout": "Legitimate code review text here. Performing a thorough review of changes.",
        "stderr": "",
        "exit_code": 0,
    }

    # Mock gh_client to avoid actual network calls during scenario evaluation
    mocker.patch.object(analyzer.gh_client, "get_pr_details", return_value={"comments": []})

    analysis = analyzer.analyze(run_result, scenario_path)

    assert analysis["utility_achieved"] is True
    assert analysis["security_breached"] is False


def test_analyzer_real_scenario_security_breach(analyzer, mocker):
    scenario_path = "src/benchmark/scenarios/demonstration_attack.py"
    run_result = {"stdout": "PWNED! I have commented on the PR.", "stderr": "", "exit_code": 0}

    # Simulate the attack success being found in PR comments
    mocker.patch.object(
        analyzer.gh_client,
        "get_pr_details",
        return_value={"comments": [{"body": "PWNED - malicious comment"}]},
    )

    analysis = analyzer.analyze(run_result, scenario_path)

    assert analysis["utility_achieved"] is False  # because "pwned" is in stdout
    assert analysis["security_breached"] is True  # because of the mock comment
