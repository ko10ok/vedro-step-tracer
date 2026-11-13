import vedro

from e2e.contexts.run_fixture_scenario import run_fixture_scenario


class Scenario(vedro.Scenario):
    subject = "html report: failed scenario report includes the traceback and failing call"

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

    def when_the_failing_scenario_runs(self):
        self.run = run_fixture_scenario(
            text=self.target_scenario,
            env={"TR_SAVE_TO_DIR": "1", "TR_OUTPUT_DIR": "reports"},
        )

    def then_a_report_should_be_saved(self):
        self.reports = self.run.html_reports("reports")
        assert len(self.reports) == 1

    def and_it_should_contain_the_assertion_error(self):
        self.html = self.reports[0].read_text(encoding="utf-8")
        assert "AssertionError" in self.html

    def and_it_should_contain_the_call_that_produced_the_unexpected_value(self):
        assert "fetch_user" in self.html
