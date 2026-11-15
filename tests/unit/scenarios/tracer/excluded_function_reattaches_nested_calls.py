import vedro

from unit.contexts.step_runner import call_names, run_step
from unit.contexts.traced_calls import outer_call


class Scenario(vedro.Scenario):
    subject = "tracer: an excluded function disappears, its nested calls reattach to the parent"

    def when_a_step_calls_a_chain_with_the_middle_function_excluded(self):
        def when(self):
            self.result = outer_call(2, 3)

        # collapse=False — проверяем именно реакцию тракера (exclude_functions),
        # не смешивая её со схлопыванием транзитных цепочек (отдельный тест).
        self.call_tree = run_step(when, exclude_functions=["middle_call"], collapse=False)

    def then_outer_call_and_leaf_sum_should_remain_as_parent_and_child(self):
        assert call_names(self.call_tree) == ["outer_call", "leaf_sum"]
