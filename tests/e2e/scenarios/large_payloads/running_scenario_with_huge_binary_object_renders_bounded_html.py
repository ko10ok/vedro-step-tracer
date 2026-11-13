import vedro

from e2e.contexts.run_fixture_scenario import run_fixture_scenario

_MAX_REPORT_LEN = 1_000_000


class Scenario(vedro.Scenario):
    subject = "large payloads: running a scenario with a huge binary object renders bounded html"

    def given_a_scenario_that_builds_a_binary_message(self):
        self.target_scenario = '''
import vedro

from contexts.sample_calls import binary_message


class Scenario(vedro.Scenario):
    subject = "trace a huge binary object"

    def when_message_is_built(self):
        self.message = binary_message()

    def then_it_should_exist(self):
        assert self.message is not None
'''

    def when_it_runs_with_tr_and_saves_to_dir(self):
        self.run = run_fixture_scenario(
            text=self.target_scenario, args=["--tr"],
            env={"TR_SAVE_TO_DIR": "1", "TR_OUTPUT_DIR": "reports"},
        )

    def then_it_should_pass(self):
        assert self.run.returncode == 0

    def and_the_report_should_be_bounded(self):
        reports = self.run.html_reports("reports")
        assert len(reports) == 1
        self.html = reports[0].read_text(encoding="utf-8")
        assert len(self.html) < _MAX_REPORT_LEN

    def and_it_should_report_the_original_size(self):
        assert "chars" in self.html
