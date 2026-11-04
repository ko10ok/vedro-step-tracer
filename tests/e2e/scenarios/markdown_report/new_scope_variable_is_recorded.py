import vedro

from e2e.contexts.run_fixture_scenario import run_fixture_scenario


class Scenario(vedro.Scenario):
    subject = "markdown report: a new scope variable set in a step is recorded"

    def given_the_target_scenario(self):
        self.target_scenario = '''
import vedro


class Scenario(vedro.Scenario):
    subject = "trace a step that sets a new scope variable"

    def when_the_step_sets_a_scope_variable(self):
        self.user_id = 42

    def then_it_should_be_set(self):
        assert self.user_id == 42
'''

    def when_scenario_runs_with_tr(self):
        self.run = run_fixture_scenario(
            text=self.target_scenario, args=["--tr"],
            env={
                "TR_SAVE_TO_DIR": "1", "TR_OUTPUT_DIR": "reports",
                "TR_REPORT_FORMATS": "markdown",
            },
        )

    def then_the_report_should_be_a_markdown_file(self):
        self.reports = self.run.markdown_reports("reports")
        assert len(self.reports) == 1

    def and_no_html_report_should_be_written(self):
        assert self.run.html_reports("reports") == []

    def and_it_should_show_the_variable_name_and_value_as_a_scope_change(self):
        self.markdown = self.reports[0].read_text(encoding="utf-8")
        assert "⇒ user_id: 42" in self.markdown
