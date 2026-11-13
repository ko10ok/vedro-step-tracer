import vedro

from e2e.contexts.run_fixture_scenario import run_fixture_scenario


class Scenario(vedro.Scenario):
    subject = "markdown report: local variables accumulated inside a call are recorded"

    def given_the_target_scenario(self):
        self.target_scenario = '''
import vedro

from contexts.sample_calls import summarize_user_ids


class Scenario(vedro.Scenario):
    subject = "trace local variables accumulated inside a call"

    def given_user_ids(self):
        self.user_ids = [1, 2, 3]

    def when_the_ids_are_summarized(self):
        self.total = summarize_user_ids(self.user_ids)

    def then_the_total_should_be_correct(self):
        assert self.total == 6
'''

    def when_scenario_runs_with_tr(self):
        self.run = run_fixture_scenario(
            text=self.target_scenario, args=["--tr"],
            env={
                "TR_SAVE_TO_DIR": "1", "TR_OUTPUT_DIR": "reports",
                "TR_REPORT_FORMATS": "markdown",
            },
        )

    def then_the_report_should_contain_the_call_arguments(self):
        self.markdown = self.run.markdown_reports("reports")[0].read_text(encoding="utf-8")
        assert "→ user_ids:" in self.markdown

    def and_it_should_contain_the_loops_final_local_variable_value(self):
        # "total" — локальная переменная внутри summarize_user_ids, не
        # аргумент и не scope self сценария: накоплена циклом до return.
        assert "· total: 6" in self.markdown
