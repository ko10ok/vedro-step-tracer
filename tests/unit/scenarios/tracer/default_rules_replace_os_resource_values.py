import vedro

from unit.contexts.step_runner import all_var_nodes, run_step
from unit.contexts.traced_calls import holds_a_socket
from vedro_step_tracer.exclude import (
    DEFAULT_EXCLUDED_VALUE_TYPES,
    EXCLUDED_PLACEHOLDER,
    ValueExcludeRules,
)


class Scenario(vedro.Scenario):
    subject = "tracer: a default-excluded value type (socket) is replaced with a placeholder"

    def when_a_step_calls_a_function_holding_a_socket_in_a_local(self):
        def when(self):
            self.result = holds_a_socket()

        # Те же правила, что плагин собирает по умолчанию из
        # VedroStepTracer.exclude_value_types (см. config.py) — без них
        # сокет попал бы в дерево как живая ссылка на оригинал (safe_copy
        # не умеет его копировать и отдаёт исходный объект).
        rules = ValueExcludeRules(DEFAULT_EXCLUDED_VALUE_TYPES)
        self.call_tree = run_step(when, exclude_value_rules=rules)

    def then_the_socket_variable_should_be_a_placeholder_not_the_real_object(self):
        sock_nodes = [n for n in all_var_nodes(self.call_tree) if n.key == "sock"]
        assert len(sock_nodes) == 1
        assert sock_nodes[0].value == EXCLUDED_PLACEHOLDER
