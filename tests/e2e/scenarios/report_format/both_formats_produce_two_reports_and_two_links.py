import vedro

from e2e.contexts.run_fixture_scenario import run_fixture_scenario


class Scenario(vedro.Scenario):
    subject = "report_format: both formats together produce one report of each and two labelled links"

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

    def when_the_failing_scenario_runs_with_both_formats(self):
        self.run = run_fixture_scenario(
            text=self.target_scenario,
            env={
                "TR_SAVE_TO_DIR": "1", "TR_OUTPUT_DIR": "reports",
                "TR_REPORT_FORMATS": "html,markdown",
            },
        )

    def then_one_report_of_each_format_should_be_saved(self):
        assert len(self.run.html_reports("reports")) == 1
        assert len(self.run.markdown_reports("reports")) == 1

    def and_stdout_should_contain_a_labelled_link_for_each_format(self):
        assert "🔎 Trace report (html): file://" in self.run.stdout
        assert "🔎 Trace report (markdown): file://" in self.run.stdout
