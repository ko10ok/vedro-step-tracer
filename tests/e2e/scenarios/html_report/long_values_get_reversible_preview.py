import vedro

from e2e.contexts.run_fixture_scenario import run_fixture_scenario


class Scenario(vedro.Scenario):
    subject = "html report: long values are shortened with a reversible preview"

    def given_the_target_scenario(self):
        self.target_scenario = '''
import vedro
from vedro import params

from contexts.sample_calls import long_value, mutate_in_place, passthrough_wrapper


class Scenario(vedro.Scenario):
    subject = "trace nested calls with variables ({user_id})"

    @params(42)
    @params(43)
    def __init__(self, user_id):
        self.user_id = user_id

    def given_empty_history(self):
        self.history: list = []

    def when_user_is_fetched_through_wrapper(self):
        self.payload = passthrough_wrapper(self.user_id)

    def then_payload_should_contain_greeting(self):
        assert self.payload["greeting"] == f"Hello, user-{self.user_id}!"

    def and_a_long_value_should_be_produced(self):
        self.blob = long_value()
        assert len(self.blob) == 5000

    def and_history_should_be_mutated_in_place(self):
        mutate_in_place(self.history, self.user_id)
        assert self.history == [self.user_id]
'''

    def when_scenario_runs_with_tr(self):
        self.run = run_fixture_scenario(
            text=self.target_scenario, args=["--tr"],
            env={"TR_SAVE_TO_DIR": "1", "TR_OUTPUT_DIR": "reports"},
        )

    def then_the_report_should_contain_a_shortened_preview(self):
        self.html = self.run.html_reports("reports")[0].read_text(encoding="utf-8")
        assert "str, 5000 chars" in self.html

    def and_the_hidden_tail_should_stay_reachable_in_the_markup(self):
        # Хвост не удалён, а свёрнут в DOM: по клику "…" раскрывается, его
        # находит поиск по отчёту и забирает кнопка копирования.
        assert "v-cut-dots" in self.html
        assert "v-cut-rest" in self.html
