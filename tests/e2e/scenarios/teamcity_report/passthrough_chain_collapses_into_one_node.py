import vedro

from e2e.contexts.run_fixture_scenario import run_fixture_scenario


class Scenario(vedro.Scenario):
    subject = "teamcity report: transit call chains collapse into one node"

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
        self.run = run_fixture_scenario(text=self.target_scenario, args=["--tr-teamcity"])

    def then_the_wrapper_and_its_single_call_should_be_shown_as_one_node(self):
        assert "passthrough_wrapper → fetch_user" in self.run.stdout
