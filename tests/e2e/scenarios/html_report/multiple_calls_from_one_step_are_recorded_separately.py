import vedro

from e2e.contexts.run_fixture_scenario import run_fixture_scenario


class Scenario(vedro.Scenario):
    subject = "html report: multiple calls made directly from one step appear as separate nodes"

    def given_the_target_scenario(self):
        self.target_scenario = '''
import vedro

from contexts.sample_calls import fetch_user, long_value


class Scenario(vedro.Scenario):
    subject = "trace two distinct calls made directly from one step"

    def when_two_calls_are_made_directly_from_the_step(self):
        self.payload = fetch_user(1)
        self.blob = long_value()

    def then_both_results_should_be_correct(self):
        assert self.payload["user_id"] == 1
        assert len(self.blob) == 5000
'''

    def when_scenario_runs_with_tr(self):
        self.run = run_fixture_scenario(
            text=self.target_scenario, args=["--tr"],
            env={"TR_SAVE_TO_DIR": "1", "TR_OUTPUT_DIR": "reports"},
        )

    def then_both_calls_should_appear_as_their_own_nodes(self):
        self.html = self.run.html_reports("reports")[0].read_text(encoding="utf-8")
        assert self.html.count('<span class="step-name">fetch_user</span>') == 1
        assert self.html.count('<span class="step-name">long_value</span>') == 1

    def and_neither_call_should_be_nested_inside_the_other(self):
        # fetch_user вызывает свои собственные вложенные хелперы, но
        # long_value — ничего: если бы оба оказались в одном узле,
        # long_value не появился бы отдельным <details class="node ...">.
        fetch_user_start = self.html.index('<span class="step-name">fetch_user</span>')
        long_value_start = self.html.index('<span class="step-name">long_value</span>')
        assert fetch_user_start != long_value_start
