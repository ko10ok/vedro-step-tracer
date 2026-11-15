import vedro
from d42 import schema

from e2e.contexts.run_fixture_scenario import run_fixture_scenario
from e2e.contexts.teamcity_messages import unclosed_suites
from e2e.contexts.text_schema import in_order, without


class Scenario(vedro.Scenario):
    subject = "teamcity report: run scenario with a passthrough chain and streaming disabled and step when_user_is_fetched_through_wrapper"

    def given_the_target_scenario(self):
        self.target_scenario = '''
import vedro
from vedro import params

from contexts.sample_calls import long_value, mutate_in_place, passthrough_wrapper


class Scenario(vedro.Scenario):
    subject = "trace nested calls with variables ({user_id})"

    @params(42)
    @params(43)
    def __init__(self, user_id):
        self.user_id = user_id

    def given_empty_history(self):
        self.history: list = []

    def when_user_is_fetched_through_wrapper(self):
        self.payload = passthrough_wrapper(self.user_id)

    def then_payload_should_contain_greeting(self):
        assert self.payload["greeting"] == f"Hello, user-{self.user_id}!"

    def and_a_long_value_should_be_produced(self):
        self.blob = long_value()
        assert len(self.blob) == 5000

    def and_history_should_be_mutated_in_place(self):
        mutate_in_place(self.history, self.user_id)
        assert self.history == [self.user_id]
'''

    def when_scenario_runs_with_tr_teamcity(self):
        self.run = run_fixture_scenario(
            text=self.target_scenario,
            args=["--tr-teamcity"],
            env={"TR_TEAMCITY_STREAM": "0"},
        )

    def then_it_should_pass(self):
        assert self.run.returncode == 0

    def and_stdout_should_follow_the_expected_sequence(self):
        expected = schema.str.regex(in_order(
            "##teamcity[testSuiteStarted name='🔎 trace: trace nested calls with variables (42) |[1|]'",
            "##teamcity[testSuiteStarted name='✔ when_user_is_fetched_through_wrapper",
            "##teamcity[testSuiteStarted name='✔ passthrough_wrapper → fetch_user (contexts.sample_calls)'",
            "  → user_id: 42",
            "##teamcity[testSuiteFinished name='✔ passthrough_wrapper → fetch_user (contexts.sample_calls)']",
            "##teamcity[testSuiteFinished name='✔ when_user_is_fetched_through_wrapper",
        ))
        assert self.run.stdout == expected % self.run.stdout

    def and_stdout_should_have_no_separate_fetch_user_suite(self):
        expected = schema.str.regex(without(
            "##teamcity[testSuiteStarted name='✔ fetch_user (contexts.sample_calls)'",
        ))
        assert self.run.stdout == expected % self.run.stdout

    def and_the_document_suites_should_be_closed(self):
        actual = unclosed_suites(self.run.stdout)
        expected = schema.list([])
        assert actual == expected % actual
