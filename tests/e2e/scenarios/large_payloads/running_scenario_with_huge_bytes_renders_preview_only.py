import vedro

from e2e.contexts.run_fixture_scenario import run_fixture_scenario

_MAX_REPORT_LEN = 1_000_000


class Scenario(vedro.Scenario):
    subject = "large payloads: running a scenario with huge bytes renders only a preview"

    def given_a_scenario_that_returns_huge_bytes(self):
        self.target_scenario = '''
import vedro

from contexts.sample_calls import big_bytes


class Scenario(vedro.Scenario):
    subject = "trace huge bytes"

    def when_bytes_are_built(self):
        self.payload = big_bytes()

    def then_it_should_have_the_expected_size(self):
        assert len(self.payload) == 2 * 1024 * 1024
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

    def and_only_a_short_bytes_preview_should_be_rendered(self):
        assert "bytes, 2097152 bytes, preview=" in self.html
