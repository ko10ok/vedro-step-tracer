import vedro

from e2e.contexts.run_fixture_scenario import run_fixture_scenario


class Scenario(vedro.Scenario):
    subject = "report generation: running a failing scenario with --tr produces a plugin report"

    def given_a_failing_scenario(self):
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

    def when_the_failing_scenario_runs_with_tr(self):
        self.run = run_fixture_scenario(text=self.target_scenario, args=["--tr"])

    def then_it_should_fail(self):
        assert self.run.returncode != 0

    def and_a_plugin_report_should_be_produced(self):
        reports = self.run.artifact_reports("vedro-step-tracer.html")
        assert len(reports) == 1
        assert "trace a failing call" in reports[0].read_text(encoding="utf-8")
