import vedro

from e2e.contexts.run_fixture_scenario import run_fixture_scenario


class Scenario(vedro.Scenario):
    subject = "report_format: by default only an html report is produced"

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

    def when_the_failing_scenario_runs_without_explicit_format(self):
        # TR_REPORT_FORMATS не задан — фикстура использует default "html"
        # (см. tests/e2e/fixtures/project/vedro.cfg.py).
        self.run = run_fixture_scenario(
            text=self.target_scenario,
            env={"TR_SAVE_TO_DIR": "1", "TR_OUTPUT_DIR": "reports"},
        )

    def then_only_an_html_report_should_be_saved(self):
        assert len(self.run.html_reports("reports")) == 1
        assert self.run.markdown_reports("reports") == []

    def and_the_report_link_line_should_keep_its_original_format(self):
        # Единственный активный формат — строка без суффикса формата в
        # скобках, как и до появления report_formats (обратная
        # совместимость).
        assert "🔎 Trace report: file://" in self.run.stdout
        assert "🔎 Trace report (html):" not in self.run.stdout
