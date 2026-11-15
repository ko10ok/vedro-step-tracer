import vedro
from d42 import schema

from e2e.contexts.run_fixture_scenario import run_fixture_scenario
from e2e.contexts.teamcity_messages import suites_without_duration, unclosed_suites
from e2e.contexts.text_schema import in_order, without


class Scenario(vedro.Scenario):
    subject = "teamcity report: run scenario with nested calls and step when_user_is_fetched_through_wrapper"

    def given_the_target_scenario(self):
        self.target_scenario = '''
import vedro

from contexts.sample_calls import passthrough_wrapper


class Scenario(vedro.Scenario):
    subject = "streaming call order"

    def given_user_id(self):
        self.user_id = 42

    def when_user_is_fetched_through_wrapper(self):
        self.payload = passthrough_wrapper(self.user_id)

    def then_payload_should_contain_greeting(self):
        assert self.payload["greeting"] == "Hello, user-42!"
'''

    def when_the_scenario_runs_with_tr_teamcity(self):
        self.run = run_fixture_scenario(text=self.target_scenario, args=["--tr-teamcity"])

    def then_it_should_pass(self):
        assert self.run.returncode == 0

    def and_stdout_should_follow_the_expected_sequence(self):
        expected = schema.str.regex(in_order(
            "##teamcity[testSuiteStarted name='🔎 trace: streaming call order'",
            "##teamcity[testSuiteStarted name='given_user_id'",
            "  ⇒ user_id: 42",
            "##teamcity[testSuiteFinished name='given_user_id'",
            "##teamcity[testSuiteStarted name='when_user_is_fetched_through_wrapper'",
            "##teamcity[testSuiteStarted name='passthrough_wrapper (contexts.sample_calls)'",
            "  → user_id: 42",
            "##teamcity[testSuiteStarted name='fetch_user (contexts.sample_calls)'",
            "  → user_id: 42",
            "##teamcity[testSuiteStarted name='_build_payload (contexts.sample_calls)'",
            "  → user_id: 42",
            "  ↲ {",
            "        user_id: 42",
            "##teamcity[testSuiteFinished name='_build_payload (contexts.sample_calls)'",
            "##teamcity[testSuiteStarted name='_format_greeting (contexts.sample_calls)'",
            "  → name: 'user-42'",
            "  ↲ 'Hello, user-42!'",
            "##teamcity[testSuiteFinished name='_format_greeting (contexts.sample_calls)'",
            "  ↲ {",
            "        greeting: 'Hello, user-42!'",
            "##teamcity[testSuiteFinished name='fetch_user (contexts.sample_calls)'",
            "##teamcity[testSuiteFinished name='passthrough_wrapper (contexts.sample_calls)'",
            "  ⇒ payload: {",
            "##teamcity[testSuiteFinished name='when_user_is_fetched_through_wrapper'",
            "##teamcity[testSuiteStarted name='then_payload_should_contain_greeting'",
            "##teamcity[testSuiteFinished name='then_payload_should_contain_greeting'",
            "##teamcity[testSuiteFinished name='🔎 trace: streaming call order'",
        ))
        assert self.run.stdout == expected % self.run.stdout

    def and_stdout_should_have_no_breadcrumbs_or_duration_hint(self):
        expected = schema.str.regex(without("passthrough_wrapper → fetch_user", "⏱"))
        assert self.run.stdout == expected % self.run.stdout

    def and_every_suite_should_be_closed_in_order(self):
        actual = unclosed_suites(self.run.stdout)
        expected = schema.list([])
        assert actual == expected % actual

    def and_every_suite_should_carry_a_duration(self):
        actual = suites_without_duration(self.run.stdout)
        expected = schema.list([])
        assert actual == expected % actual
