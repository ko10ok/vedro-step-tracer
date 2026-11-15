import vedro

from unit.contexts.step_runner import all_var_nodes, call_names, run_step
from unit.contexts.traced_calls import run_with_pipe_var
from vedro_step_tracer.exclude import EXCLUDED_PLACEHOLDER, ValueExcludeRules, var


class Scenario(vedro.Scenario):
    subject = "tracer: var()-scoped exclusion hides one variable without excluding the whole call"

    def when_a_step_calls_a_function_with_an_excluded_local_variable(self):
        def when(self):
            self.result = run_with_pipe_var(10)

        rules = ValueExcludeRules([var("process", function="run_with_pipe_var")])
        self.call_tree = run_step(when, exclude_value_rules=rules, collapse=False)

    def then_the_process_variable_should_be_a_placeholder(self):
        process_nodes = [n for n in all_var_nodes(self.call_tree) if n.key == "process"]
        assert len(process_nodes) == 1
        assert process_nodes[0].value == EXCLUDED_PLACEHOLDER

    def then_the_argument_and_the_nested_call_should_still_be_traced_normally(self):
        arg_nodes = [n for n in all_var_nodes(self.call_tree) if n.key == "x"]
        assert len(arg_nodes) == 1
        assert arg_nodes[0].value == 10
        assert call_names(self.call_tree) == ["run_with_pipe_var", "leaf_sum"]
