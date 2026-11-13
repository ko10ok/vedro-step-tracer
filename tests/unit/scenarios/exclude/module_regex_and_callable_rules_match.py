import re

import vedro

from vedro_step_tracer.exclude import ValueExcludeRules, module


class Scenario(vedro.Scenario):
    subject = "exclude: module(), regex and callable rules each match on their own axis"

    def when_rules_cover_module_prefix_regex_and_a_predicate(self):
        self.rules = ValueExcludeRules([
            module("socket"),
            re.compile(r"^builtins\.list$"),
            lambda value: value == "magic",
        ])

    def then_a_value_whose_module_starts_with_the_prefix_is_excluded(self):
        import socket
        assert self.rules.excluded(socket.socket()) is True

    def and_a_value_matching_the_regex_by_qualified_name_is_excluded(self):
        assert self.rules.excluded([1, 2, 3]) is True

    def and_a_value_matching_the_predicate_is_excluded(self):
        assert self.rules.excluded("magic") is True

    def and_an_unrelated_value_is_not_excluded(self):
        assert self.rules.excluded(42) is False
