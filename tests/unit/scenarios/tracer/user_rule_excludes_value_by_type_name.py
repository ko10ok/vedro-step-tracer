import vedro

from unit.contexts.step_runner import all_var_nodes, run_step
from unit.contexts.traced_calls import holds_a_socket
from vedro_step_tracer.exclude import EXCLUDED_PLACEHOLDER, ValueExcludeRules


class Scenario(vedro.Scenario):
    subject = "tracer: user-level rules exclude values by type name/module, same as the base list"

    def when_a_step_calls_a_function_holding_a_socket_in_a_local(self):
        def when(self):
            self.result = holds_a_socket()

        # Правило задано строкой (имя типа) вместо самого типа — проверяем
        # именно этот вариант, тип уже покрыт отдельным тестом с дефолтами.
        self.call_tree = run_step(when, exclude_value_rules=ValueExcludeRules(["socket"]))

    def then_the_socket_variable_should_be_a_placeholder(self):
        sock_nodes = [n for n in all_var_nodes(self.call_tree) if n.key == "sock"]
        assert len(sock_nodes) == 1
        assert sock_nodes[0].value == EXCLUDED_PLACEHOLDER
