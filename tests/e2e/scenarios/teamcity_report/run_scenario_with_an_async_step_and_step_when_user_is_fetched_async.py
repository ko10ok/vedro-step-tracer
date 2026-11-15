import vedro
from d42 import schema

from e2e.contexts.run_fixture_scenario import run_fixture_scenario
from e2e.contexts.teamcity_messages import unclosed_suites
from e2e.contexts.text_schema import in_order


class Scenario(vedro.Scenario):
    subject = "teamcity report: run scenario with an async step and step when_user_is_fetched_async"

    def given_the_target_scenario(self):
        self.target_scenario = '''
import vedro

from contexts.sample_calls import async_fetch_user


class Scenario(vedro.Scenario):
    subject = "streaming async call"

    def given_user_id(self):
        self.user_id = 42

    async def when_user_is_fetched_async(self):
        self.payload = await async_fetch_user(self.user_id)

    def then_it_should_be_ok(self):
        assert self.payload["status"] == "active"
'''

    def when_the_async_scenario_runs_with_tr_teamcity(self):
        self.run = run_fixture_scenario(text=self.target_scenario, args=["--tr-teamcity"])

    def then_it_should_pass(self):
        assert self.run.returncode == 0

    def and_stdout_should_follow_the_expected_sequence(self):
        expected = schema.str.regex(in_order(
            "##teamcity[testSuiteStarted name='🔎 trace: streaming async call'",
            "##teamcity[testSuiteStarted name='given_user_id'",
            "│▏  ¦   │   ⇒ user_id: 42",
            "##teamcity[testSuiteFinished name='given_user_id'",
            "##teamcity[testSuiteStarted name='when_user_is_fetched_async'",
            "##teamcity[testSuiteStarted name='async_fetch_user (contexts.sample_calls)'",
            "│█▏ ¦   │   → user_id: 42",
            "##teamcity[testSuiteFinished name='async_fetch_user (contexts.sample_calls)'",
            "##teamcity[testSuiteStarted name='async_fetch_user (contexts.sample_calls) #2'",
            "│█▏ ¦   │   → user_id: 42",
            "##teamcity[testSuiteStarted name='fetch_user (contexts.sample_calls)'",
            "##teamcity[testSuiteStarted name='_build_payload (contexts.sample_calls)'",
            "##teamcity[testSuiteFinished name='_build_payload (contexts.sample_calls)'",
            "##teamcity[testSuiteStarted name='_format_greeting (contexts.sample_calls)'",
            "##teamcity[testSuiteFinished name='_format_greeting (contexts.sample_calls)'",
            "##teamcity[testSuiteFinished name='fetch_user (contexts.sample_calls)'",
            "##teamcity[testSuiteFinished name='async_fetch_user (contexts.sample_calls) #2'",
            "│▏  ¦   │   ⇒ payload: {",
            "##teamcity[testSuiteFinished name='when_user_is_fetched_async'",
            "##teamcity[testSuiteStarted name='then_it_should_be_ok'",
            "##teamcity[testSuiteFinished name='then_it_should_be_ok'",
            "##teamcity[testSuiteFinished name='🔎 trace: streaming async call'",
        ))
        assert self.run.stdout == expected % self.run.stdout

    def and_all_suites_should_be_closed(self):
        actual = unclosed_suites(self.run.stdout)
        expected = schema.list([])
        assert actual == expected % actual
