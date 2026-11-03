import vedro

from unit.contexts.step_runner import FakeStepSelf, all_var_nodes, run_step
from unit.contexts.traced_calls import mutate_history


class Scenario(vedro.Scenario):
    """
    Фидбек Даши: ``mocked_response.Handler._history`` — тот же список,
    который наполняется позже, уже после того как трейсер снял первый
    снимок. Сравнение по ``id()`` такую мутацию не видит; тест закрывает
    фикс через fingerprint (id + размер контейнера).
    """

    subject = "tree: a container mutated in place is detected as a changed scope variable"

    def given_a_scope_variable_holding_an_empty_list(self):
        self.scenario = FakeStepSelf()
        self.scenario.history = []

    def when_a_step_mutates_it_through_a_traced_call(self):
        def when(self):
            mutate_history(self.history, 42)

        self.call_tree = run_step(when, scenario=self.scenario)

    def then_the_tree_should_record_a_changed_scope_variable(self):
        scope_vars = [v for v in all_var_nodes(self.call_tree) if v.kind == "scope_changed"]
        assert any(v.key == "history" and v.value == [42] for v in scope_vars)
