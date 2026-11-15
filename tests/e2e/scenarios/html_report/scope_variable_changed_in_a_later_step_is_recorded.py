import vedro

from e2e.contexts.run_fixture_scenario import run_fixture_scenario


class Scenario(vedro.Scenario):
    subject = "html report: a scope variable mutated through a traced call is recorded as changed"

    def given_the_target_scenario(self):
        self.target_scenario = '''
import vedro

from contexts.sample_calls import mutate_in_place


class Scenario(vedro.Scenario):
    subject = "trace a scope variable mutated in a later step"

    def given_an_empty_history(self):
        self.history: list = []

    def when_history_is_mutated_through_a_traced_call(self):
        mutate_in_place(self.history, 42)

    def then_history_should_contain_the_mutated_value(self):
        assert self.history == [42]
'''

    def when_scenario_runs_with_tr(self):
        self.run = run_fixture_scenario(
            text=self.target_scenario, args=["--tr"],
            env={"TR_SAVE_TO_DIR": "1", "TR_OUTPUT_DIR": "reports"},
        )

    def then_the_report_should_contain_the_initial_scope_variable(self):
        self.html = self.run.html_reports("reports")[0].read_text(encoding="utf-8")
        assert 'v-item-scope"' in self.html

    def and_it_should_mark_the_later_mutation_as_a_changed_scope_variable(self):
        # Присвоения не было — history изменился "в фоне", внутри вызова
        # mutate_in_place, куда он попал потому, что шаг сам передал его
        # туда (сослался на переменную). Трейсер должен увидеть это как
        # scope_changed, а не пропустить (сравнение не по id(), а по
        # fingerprint содержимого — см. FunctionTracer._fingerprint).
        assert 'v-item-scope-changed"' in self.html
        assert '<span class="v-key">history</span>' in self.html
        assert '<span class="v-num">42</span>' in self.html
