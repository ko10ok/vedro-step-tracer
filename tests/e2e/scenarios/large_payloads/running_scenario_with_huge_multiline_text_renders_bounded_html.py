import vedro

from e2e.contexts.run_fixture_scenario import run_fixture_scenario

_MAX_REPORT_LEN = 1_000_000


class Scenario(vedro.Scenario):
    subject = "large payloads: running a scenario with huge multiline text renders bounded html"

    def given_a_scenario_that_returns_huge_multiline_text(self):
        self.target_scenario = '''
import vedro

from contexts.sample_calls import multiline_text


class Scenario(vedro.Scenario):
    subject = "trace huge multiline text"

    def when_text_is_built(self):
        self.text = multiline_text()

    def then_it_should_be_multiline(self):
        assert self.text.count("\\n") == 32767
'''

    def when_it_runs_with_tr_and_saves_to_dir(self):
        self.run = run_fixture_scenario(
            text=self.target_scenario, args=["--tr"],
            env={"TR_SAVE_TO_DIR": "1", "TR_OUTPUT_DIR": "reports"},
        )

    def then_it_should_pass(self):
        assert self.run.returncode == 0

    def and_the_report_should_be_bounded(self):
        self.html = self.run.html_reports("reports")[0].read_text(encoding="utf-8")
        assert len(self.html) < _MAX_REPORT_LEN

    def and_it_should_report_the_original_size(self):
        assert "chars" in self.html
