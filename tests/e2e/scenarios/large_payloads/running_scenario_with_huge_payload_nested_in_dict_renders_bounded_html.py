import vedro

from e2e.contexts.run_fixture_scenario import run_fixture_scenario

_MAX_REPORT_LEN = 1_000_000


class Scenario(vedro.Scenario):
    subject = "large payloads: running a scenario with a huge payload nested in a dict renders bounded html"

    def given_a_scenario_that_returns_huge_payload_in_a_dict(self):
        self.target_scenario = '''
import vedro

from contexts.sample_calls import nested_big_payload


class Scenario(vedro.Scenario):
    subject = "trace a huge payload nested in a dict"

    def when_payload_is_built(self):
        self.data = nested_big_payload()

    def then_it_should_have_the_payload_key(self):
        assert "payload" in self.data
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
