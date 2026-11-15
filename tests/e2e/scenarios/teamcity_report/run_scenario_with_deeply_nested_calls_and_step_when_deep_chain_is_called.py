import re

import vedro
from d42 import schema

from e2e.contexts.run_fixture_scenario import run_fixture_scenario
from e2e.contexts.teamcity_messages import unclosed_suites
from e2e.contexts.text_schema import in_order


class Scenario(vedro.Scenario):
    subject = "teamcity report: run scenario with deeply nested calls and step when_deep_chain_is_called"

    def given_the_target_scenario(self):
        self.target_scenario = '''
import vedro

from contexts.sample_calls import deep_chain, fetch_user


class Scenario(vedro.Scenario):
    subject = "deeply nested headers"

    def given_start_value(self):
        self.start = 10

    def and_user_id(self):
        self.user_id = 42

    def when_chain_runs(self):
        self.result = deep_chain(self.start)
        self.payload = fetch_user(self.user_id)

    def then_result_is_expected(self):
        assert self.result == 77

    def and_payload_should_be_active(self):
        assert self.payload["status"] == "active"
'''

    def when_the_scenario_runs_with_tr_teamcity(self):
        self.run = run_fixture_scenario(text=self.target_scenario, args=["--tr-teamcity"])

    def then_it_should_pass(self):
        assert self.run.returncode == 0

    def and_stdout_should_start_with_the_scenario_header(self):
        expected = schema.str.regex(in_order(
            "##teamcity[testSuiteStarted name='🔎 trace: deeply nested headers'",
            "▶ deeply nested headers",
            "##teamcity[testSuiteStarted name='given_start_value'",
            "│▏  ¦   │   given_start_value",
        ))
        assert self.run.stdout == expected % self.run.stdout

    def and_each_step_should_have_a_level_zero_header(self):
        expected = schema.str.regex(in_order(
            "│▏  ¦   │   given_start_value",
            "│▏  ¦   │   ⇒ start: 10",
            "│▏  ¦   │   and_user_id",
            "│▏  ¦   │   ⇒ user_id: 42",
            "│▏  ¦   │   when_chain_runs",
            "│▏  ¦   │   then_result_is_expected",
            "│▏  ¦   │   and_payload_should_be_active",
        ))
        assert self.run.stdout == expected % self.run.stdout

    def and_the_test_name_should_be_followed_by_an_indicator_line(self):
        expected = schema.str.regex(in_order(
            "▶ deeply nested headers",
            "\n\n",
            "\033[1m│▏  ¦   │   given_start_value",
        ))
        assert self.run.stdout == expected % self.run.stdout

    def and_step_returns_should_be_followed_by_an_indicator_line(self):
        expected = schema.str.regex(in_order(
            "s  None\n\n",
            "\033[1m│▏  ¦   │   and_user_id",
            "s  None\n\n",
            "\033[1m│▏  ¦   │   when_chain_runs",
            "s  None\n\n",
            "\033[1m│▏  ¦   │   then_result_is_expected",
            "s  None\n\n",
            "\033[1m│▏  ¦   │   and_payload_should_be_active",
        ))
        assert self.run.stdout == expected % self.run.stdout

    def and_step_headers_should_be_bold(self):
        expected = schema.str.regex(in_order(
            "\033[1m│▏  ¦   │   given_start_value\033[0m",
            "\033[1m│▏  ¦   │   and_user_id\033[0m",
            "\033[1m│▏  ¦   │   when_chain_runs\033[0m",
            "\033[1m│▏  ¦   │   then_result_is_expected\033[0m",
            "\033[1m│▏  ¦   │   and_payload_should_be_active\033[0m",
        ))
        assert self.run.stdout == expected % self.run.stdout

    def and_return_should_be_followed_by_an_indicator_line(self):
        expected = schema.str.regex(in_order(
            "│██▓¦▓▏ │   ↲ ",
            "s  36",
            "\n│██▓¦▏  │   \n",
            "\033[1m│██▓¦▓▏ │   deep_leaf",
            "│██▓¦▏  │   ↲ ",
            "s  74",
            "\n│██▏¦   │   \n",
        ))
        assert self.run.stdout == expected % self.run.stdout

    def and_variables_should_be_followed_by_an_indicator_line_before_a_call(self):
        expected = schema.str.regex(in_order(
            "│█▏ ¦   │   → value: 10\n",
            "\n│█▏ ¦   │   \n",
            "\033[1m│██▏¦   │   deep_middle",
            "│██▏¦   │   → value: 14\n",
            "\n│██▏¦   │   \n",
            "\033[1m│██▓¦▏  │   deep_branch",
            "│▏  ¦   │   ⇒ result: 77\n",
            "\n│▏  ¦   │   \n",
            "\033[1m│█▏ ¦   │   fetch_user",
        ))
        assert self.run.stdout == expected % self.run.stdout

    def and_returns_should_show_duration_before_value(self):
        expected = schema.str.regex(r"(?s)↲ ⏱ \d+\.\d{2}s  38")
        assert self.run.stdout == expected % self.run.stdout

    def and_every_step_should_end_with_a_timed_return_marker(self):
        actual = re.findall(r"↲ ⏱ \d+\.\d{2}s  None", self.run.stdout)
        assert len(actual) == 5

    def and_function_headers_should_be_bold(self):
        expected = schema.str.regex(in_order(
            "\033[1m│█▏ ¦   │   deep_chain (contexts.sample_calls)\033[0m",
            "\033[1m│█▏ ¦   │   fetch_user (contexts.sample_calls)\033[0m",
            "\033[1m│██▏¦   │   _build_payload (contexts.sample_calls)\033[0m",
        ))
        assert self.run.stdout == expected % self.run.stdout

    def and_nested_calls_should_have_depth_headers(self):
        expected = schema.str.regex(in_order(
            "│█▏ ¦   │   deep_chain (contexts.sample_calls)",
            "│█▏ ¦   │   → value: 10",
            "│██▏¦   │   deep_middle (contexts.sample_calls)",
            "│██▏¦   │   → value: 14",
            "│██▓¦▏  │   deep_branch (contexts.sample_calls)",
            "│██▓¦▏  │   → value: 17",
            "│██▓¦▓▏ │   deep_leaf (contexts.sample_calls)",
            "│██▓¦▓▏ │   → value: 18",
            "│██▓¦▓▏ │   deep_leaf (contexts.sample_calls) #2",
            "│██▓¦▓▏ │   → value: 19",
            "│██▓¦▏  │   ↲ ",
            "s  74",
            "│██▏¦   │   ↲ ",
            "s  75",
            "│█▏ ¦   │   ↲ ",
            "s  77",
            "│█▏ ¦   │   fetch_user (contexts.sample_calls)",
            "│██▏¦   │   _build_payload (contexts.sample_calls)",
            "│██▏¦   │   _format_greeting (contexts.sample_calls)",
        ))
        assert self.run.stdout == expected % self.run.stdout

    def and_every_suite_should_be_closed_in_order(self):
        actual = unclosed_suites(self.run.stdout)
        expected = schema.list([])
        assert actual == expected % actual
