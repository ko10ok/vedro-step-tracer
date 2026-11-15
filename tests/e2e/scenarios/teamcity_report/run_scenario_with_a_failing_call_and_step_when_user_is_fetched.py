import vedro
from d42 import schema

from e2e.contexts.run_fixture_scenario import run_fixture_scenario
from e2e.contexts.teamcity_messages import unclosed_suites
from e2e.contexts.text_schema import in_order


class Scenario(vedro.Scenario):
    subject = "teamcity report: run scenario with a failing call and step when_user_is_fetched"

    def given_the_target_scenario(self):
        self.target_scenario = '''
import vedro

from contexts.sample_calls import fetch_user


class Scenario(vedro.Scenario):
    subject = "trace a failing call"

    def given_user_id(self):
        self.user_id = 7

    def when_user_is_fetched(self):
        self.payload = fetch_user(self.user_id)

    def then_it_should_be_banned(self):
        assert self.payload["status"] == "banned"
'''

    def when_the_failing_scenario_runs_with_tr_teamcity(self):
        self.run = run_fixture_scenario(text=self.target_scenario, args=["--tr-teamcity"])

    def then_it_should_fail(self):
        assert self.run.returncode != 0

    def and_stdout_should_follow_the_expected_sequence(self):
        expected = schema.str.regex(in_order(
            "##teamcity[testSuiteStarted name='🔎 trace: trace a failing call'",
            "##teamcity[testSuiteStarted name='given_user_id'",
            "│▏  ¦   │   ⇒ user_id: 7",
            "##teamcity[testSuiteFinished name='given_user_id'",
            "##teamcity[testSuiteStarted name='when_user_is_fetched'",
            "##teamcity[testSuiteStarted name='fetch_user (contexts.sample_calls)'",
            "##teamcity[testSuiteStarted name='_build_payload (contexts.sample_calls)'",
            "##teamcity[testSuiteFinished name='_build_payload (contexts.sample_calls)'",
            "##teamcity[testSuiteStarted name='_format_greeting (contexts.sample_calls)'",
            "##teamcity[testSuiteFinished name='_format_greeting (contexts.sample_calls)'",
            "##teamcity[testSuiteFinished name='fetch_user (contexts.sample_calls)'",
            "│▏  ¦   │   ⇒ payload: {",
            "##teamcity[testSuiteFinished name='when_user_is_fetched'",
            "##teamcity[testSuiteStarted name='then_it_should_be_banned'",
            "##teamcity[testStarted name='💥 failure'",
            "##teamcity[testFailed name='💥 failure' message='AssertionError'",
            "##teamcity[testFinished name='💥 failure'",
            "##teamcity[testSuiteFinished name='then_it_should_be_banned'",
            "##teamcity[testSuiteFinished name='🔎 trace: trace a failing call'",
        ))
        assert self.run.stdout == expected % self.run.stdout

    def and_all_suites_should_be_closed(self):
        actual = unclosed_suites(self.run.stdout)
        expected = schema.list([])
        assert actual == expected % actual
