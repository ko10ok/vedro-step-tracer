import vedro

from e2e.contexts.run_fixture_scenario import run_fixture_scenario


class Scenario(vedro.Scenario):
    subject = "report generation: running a passed scenario without --tr produces no report"

    def given_a_passing_scenario(self):
        self.target_scenario = '''
import vedro

from contexts.sample_calls import fetch_user


class Scenario(vedro.Scenario):
    subject = "trace a passing call"

    def given_user_id(self):
        self.user_id = 7

    def when_user_is_fetched(self):
        self.payload = fetch_user(self.user_id)

    def then_it_should_be_active(self):
        assert self.payload["status"] == "active"
'''

    def when_the_passed_scenario_runs_without_tr(self):
        self.run = run_fixture_scenario(text=self.target_scenario)

    def then_it_should_pass(self):
        assert self.run.returncode == 0

    def and_no_plugin_report_should_be_produced(self):
        assert self.run.artifact_reports("vedro-step-tracer.html") == []
        assert "🔎 Trace report" not in self.run.stdout
