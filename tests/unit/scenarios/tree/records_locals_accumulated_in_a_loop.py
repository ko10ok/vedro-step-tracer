import vedro

from unit.contexts.step_runner import run_step
from unit.contexts.traced_calls import sum_with_locals
from vedro_step_tracer.tracing.nodes import StepNode


class Scenario(vedro.Scenario):
    subject = "tree: locals accumulated inside a function are captured"

    def when_a_step_calls_a_function_with_internal_locals(self):
        def when(self):
            self.result = sum_with_locals(3)

        self.call_tree = run_step(when)

    def then_the_call_node_should_return_the_computed_value(self):
        calls = [n for n in self.call_tree if isinstance(n, StepNode)]
        assert len(calls) == 1
        self.node = calls[0]
        assert self.node.return_value == 3  # 0 + 1 + 2

    def and_it_should_expose_the_final_local_variables(self):
        assert self.node.local_vars.get("total") == 3
        assert self.node.local_vars.get("i") == 2
