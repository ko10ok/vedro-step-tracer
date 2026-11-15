import vedro

from unit.contexts.step_runner import run_step
from unit.contexts.traced_calls import leaf_sum
from vedro_step_tracer.tracing.nodes import StepNode, VarNode


class Scenario(vedro.Scenario):
    subject = "tree: repeated calls with different arguments stay separate"

    def when_a_step_calls_the_same_function_twice_with_different_args(self):
        def when(self):
            self.first = leaf_sum(1, 1)
            self.second = leaf_sum(2, 2)

        self.call_tree = run_step(when)

    def then_the_tree_should_contain_two_separate_call_nodes(self):
        calls = [n for n in self.call_tree if isinstance(n, StepNode)]
        assert [n.return_value for n in calls] == [2, 4]

    def and_both_nodes_should_keep_their_own_arguments(self):
        calls = [n for n in self.call_tree if isinstance(n, StepNode)]
        args_by_call = [
            {v.key: v.value for v in n.children if isinstance(v, VarNode) and v.kind == "arg"}
            for n in calls
        ]
        assert args_by_call == [{"a": 1, "b": 1}, {"a": 2, "b": 2}]
