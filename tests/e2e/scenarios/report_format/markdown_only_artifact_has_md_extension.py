import vedro

from e2e.contexts.run_fixture_scenario import run_fixture_scenario


class Scenario(vedro.Scenario):
    subject = "report_format: markdown-only mode attaches a .md artifact, not .html"

    def given_the_target_scenario(self):
        self.target_scenario = '''
import vedro

from contexts.sample_calls import fetch_user


class Scenario(vedro.Scenario):
    subject = "trace a failing call for artifact check"

    def given_user_id(self):
        self.user_id = 7

    def when_user_is_fetched(self):
        self.payload = fetch_user(self.user_id)

    def then_it_should_be_banned(self):
        assert self.payload["status"] == "banned"
'''

    def when_the_failing_scenario_runs_with_markdown_only(self):
        self.run = run_fixture_scenario(
            text=self.target_scenario,
            env={"TR_REPORT_FORMATS": "markdown"},
        )

    def then_a_markdown_artifact_should_be_attached(self):
        assert len(self.run.artifact_reports("vedro-step-tracer.md")) == 1

    def and_no_html_artifact_should_be_attached(self):
        assert self.run.artifact_reports("vedro-step-tracer.html") == []
