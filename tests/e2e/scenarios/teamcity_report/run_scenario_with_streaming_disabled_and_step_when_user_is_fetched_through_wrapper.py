import vedro
from d42 import schema

from e2e.contexts.run_fixture_scenario import run_fixture_scenario
from e2e.contexts.teamcity_messages import unclosed_suites
from e2e.contexts.text_schema import in_order, without


class Scenario(vedro.Scenario):
    subject = "teamcity report: run scenario with streaming disabled and step when_user_is_fetched_through_wrapper"

    def given_the_target_scenario(self):
        self.target_scenario = '''
import vedro

from contexts.sample_calls import passthrough_wrapper


class Scenario(vedro.Scenario):
    subject = "legacy document mode"

    def given_user_id(self):
        self.user_id = 42

    def when_user_is_fetched_through_wrapper(self):
        self.payload = passthrough_wrapper(self.user_id)

    def then_payload_should_contain_greeting(self):
        assert self.payload["greeting"] == "Hello, user-42!"
'''

    def when_the_scenario_runs_with_streaming_disabled(self):
        self.run = run_fixture_scenario(
            text=self.target_scenario,
            args=["--tr-teamcity"],
            env={"TR_TEAMCITY_STREAM": "0"},
        )

    def then_it_should_pass(self):
        assert self.run.returncode == 0

    def and_stdout_should_follow_the_expected_sequence(self):
        expected = schema.str.regex(in_order(
            "##teamcity[testSuiteStarted name='🔎 trace: legacy document mode'",
            "##teamcity[testStarted name='✔ given_user_id'",
            "  ⇒ user_id: 42",
            "##teamcity[testFinished name='✔ given_user_id'",
            "##teamcity[testSuiteStarted name='✔ when_user_is_fetched_through_wrapper",
            "##teamcity[testSuiteStarted name='✔ passthrough_wrapper → fetch_user (contexts.sample_calls)'",
            "  → user_id: 42",
            "##teamcity[testStarted name='✔ _build_payload (contexts.sample_calls)'",
            "##teamcity[testFinished name='✔ _build_payload (contexts.sample_calls)'",
            "##teamcity[testStarted name='✔ _format_greeting (contexts.sample_calls)'",
            "##teamcity[testFinished name='✔ _format_greeting (contexts.sample_calls)'",
            "##teamcity[testSuiteFinished name='✔ passthrough_wrapper → fetch_user (contexts.sample_calls)'",
            "##teamcity[testSuiteFinished name='✔ when_user_is_fetched_through_wrapper",
            "##teamcity[testStarted name='✔ then_payload_should_contain_greeting'",
            "##teamcity[testFinished name='✔ then_payload_should_contain_greeting'",
            "##teamcity[testSuiteFinished name='🔎 trace: legacy document mode'",
        ))
        assert self.run.stdout == expected % self.run.stdout

    def and_stdout_should_have_no_separate_fetch_user_suite(self):
        expected = schema.str.regex(without(
            "##teamcity[testSuiteStarted name='fetch_user (contexts.sample_calls)'",
        ))
        assert self.run.stdout == expected % self.run.stdout

    def and_the_document_suites_should_be_closed(self):
        actual = unclosed_suites(self.run.stdout)
        expected = schema.list([])
        assert actual == expected % actual
