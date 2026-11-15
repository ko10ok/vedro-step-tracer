import vedro

from unit.contexts.step_runner import run_step
from unit.contexts.traced_calls import void_twice
from vedro_step_tracer.tracing.nodes import StepNode


class Scenario(vedro.Scenario):
    subject = "tree: separate calls returning None are not merged into one"

    def when_a_step_calls_a_none_returning_function_twice(self):
        def when(self):
            void_twice(10)

        self.call_tree = run_step(when)

    def then_the_outer_call_should_contain_two_separate_calls(self):
        outer = [n for n in self.call_tree if isinstance(n, StepNode)][0]
        inner_calls = [n for n in outer.children if isinstance(n, StepNode)]
        assert len(inner_calls) == 2
