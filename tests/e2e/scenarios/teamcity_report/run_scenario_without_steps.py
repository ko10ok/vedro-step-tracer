import vedro
from d42 import schema

from e2e.contexts.run_fixture_scenario import run_fixture_scenario
from e2e.contexts.teamcity_messages import all_suite_names, unclosed_suites
from e2e.contexts.text_schema import in_order


class Scenario(vedro.Scenario):
    subject = "teamcity report: run scenario without steps"

    def given_the_target_scenario(self):
        self.target_scenario = '''
import vedro


class Scenario(vedro.Scenario):
    subject = "streaming no steps"

    def __init__(self):
        self.some_value = 1
'''

    def when_the_scenario_runs_with_tr_teamcity(self):
        self.run = run_fixture_scenario(text=self.target_scenario, args=["--tr-teamcity"])

    def then_it_should_pass(self):
        assert self.run.returncode == 0

    def and_stdout_should_follow_the_expected_sequence(self):
        expected = schema.str.regex(in_order(
            "##teamcity[testSuiteStarted name='🔎 trace: streaming no steps'",
            "##teamcity[testSuiteFinished name='🔎 trace: streaming no steps']",
        ))
        assert self.run.stdout == expected % self.run.stdout

    def and_only_the_scenario_suite_should_be_reported(self):
        expected = schema.list([schema.str.contains("🔎 trace: streaming no steps")])
        assert all_suite_names(self.run.stdout) == expected % all_suite_names(self.run.stdout)

    def and_the_scenario_suite_should_be_closed(self):
        actual = unclosed_suites(self.run.stdout)
        expected = schema.list([])
        assert actual == expected % actual
