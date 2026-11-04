import vedro

from unit.contexts.step_runner import run_step
from unit.contexts.noisy_calls import noisy_wrapper
from vedro_step_tracer.tracing.nodes import StepNode


class Scenario(vedro.Scenario):
    subject = "tracer: an excluded file disappears, calls from other files still remain"

    def when_a_step_calls_a_function_from_an_excluded_file(self):
        def when(self):
            self.result = noisy_wrapper(4, 5)

        self.call_tree = run_step(when, exclude_paths=["*noisy_calls.py"])

    def then_only_leaf_sum_should_remain_in_the_tree(self):
        names = [n.name for n in self.call_tree if isinstance(n, StepNode)]
        assert names == ["leaf_sum"]
