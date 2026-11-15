import vedro

from e2e.contexts.run_fixture_scenario import run_fixture_scenario


class Scenario(vedro.Scenario):
    subject = "terminal report: print_to_stdout dumps the full call tree on failure"

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

    def when_the_failing_scenario_runs_with_print_to_stdout(self):
        self.run = run_fixture_scenario(text=self.target_scenario,
                                        env={"TR_PRINT_TO_STDOUT": "1"})

    def then_it_should_fail(self):
        assert self.run.returncode != 0

    def and_stdout_should_contain_every_traced_call(self):
        assert "fetch_user" in self.run.stdout
        assert "_build_payload" in self.run.stdout
        assert "_format_greeting" in self.run.stdout

    def and_stdout_should_contain_the_returned_value(self):
        assert "'active'" in self.run.stdout
