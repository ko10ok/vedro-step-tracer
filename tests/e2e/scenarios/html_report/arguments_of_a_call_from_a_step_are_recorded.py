import vedro

from e2e.contexts.run_fixture_scenario import run_fixture_scenario


class Scenario(vedro.Scenario):
    subject = "html report: arguments of a call invoked directly from a step are recorded"

    def given_the_target_scenario(self):
        self.target_scenario = '''
import vedro

from contexts.sample_calls import fetch_user


class Scenario(vedro.Scenario):
    subject = "trace a call invoked directly from a step"

    def given_user_id(self):
        self.user_id = 7

    def when_the_user_is_fetched(self):
        self.payload = fetch_user(self.user_id)

    def then_payload_should_be_active(self):
        assert self.payload["status"] == "active"
'''

    def when_scenario_runs_with_tr(self):
        self.run = run_fixture_scenario(
            text=self.target_scenario, args=["--tr"],
            env={"TR_SAVE_TO_DIR": "1", "TR_OUTPUT_DIR": "reports"},
        )

    def then_the_report_should_be_saved(self):
        self.html = self.run.html_reports("reports")[0].read_text(encoding="utf-8")
        assert self.html

    def and_the_call_argument_should_be_recorded(self):
        assert 'v-item-arg"' in self.html
        assert '<span class="v-key">user_id</span>' in self.html
        assert '<span class="v-num">7</span>' in self.html
