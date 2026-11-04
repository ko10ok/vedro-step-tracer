import vedro

from unit.contexts.step_runner import run_step
from unit.contexts.traced_calls import leaf_sum
from vedro_step_tracer.tracing.nodes import StepNode, VarNode


class Scenario(vedro.Scenario):
    subject = "tree: records args and the return value of a simple call"

    def when_a_step_calls_a_traced_function(self):
        def given_and_when(self):
            self.result = leaf_sum(2, 3)

        self.call_tree = run_step(given_and_when)

    def then_the_tree_should_contain_exactly_one_call_node(self):
        calls = [n for n in self.call_tree if isinstance(n, StepNode)]
        assert len(calls) == 1
        self.node = calls[0]

    def and_the_node_should_carry_the_arguments(self):
        args = {v.key: v.value for v in self.node.children
                if isinstance(v, VarNode) and v.kind == "arg"}
        assert args == {"a": 2, "b": 3}

    def and_the_node_should_carry_the_return_value_and_pass_status(self):
        assert self.node.return_value == 5
        assert self.node.status == "PASS"
