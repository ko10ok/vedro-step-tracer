import vedro

from unit.contexts.step_runner import call_names, run_step
from unit.contexts.traced_calls import passthrough_wrapper
from vedro_step_tracer.tracing.nodes import StepNode


class Scenario(vedro.Scenario):
    subject = "tree: a transit wrapper collapses into one node without losing its name"

    def when_a_step_calls_a_passthrough_wrapper(self):
        def when(self):
            self.result = passthrough_wrapper(42)

        self.call_tree = run_step(when)

    def then_the_tree_should_contain_exactly_one_top_level_call(self):
        calls = [n for n in self.call_tree if isinstance(n, StepNode)]
        assert len(calls) == 1
        self.node = calls[0]

    def and_its_name_should_chain_both_functions_of_the_wrapper(self):
        assert self.node.name == "passthrough_wrapper → fetch_user"

    def and_the_inner_build_payload_call_should_still_be_a_child(self):
        assert call_names([self.node]) == [
            "passthrough_wrapper → fetch_user", "_build_payload",
        ]
