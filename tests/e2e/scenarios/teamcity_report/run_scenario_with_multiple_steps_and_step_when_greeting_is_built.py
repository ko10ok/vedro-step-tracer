import vedro
from d42 import schema

from e2e.contexts.run_fixture_scenario import run_fixture_scenario
from e2e.contexts.teamcity_messages import unclosed_suites
from e2e.contexts.text_schema import in_order


class Scenario(vedro.Scenario):
    subject = "teamcity report: run scenario with multiple steps and step when_greeting_is_built"

    def given_the_target_scenario(self):
        self.target_scenario = '''
import vedro


class Scenario(vedro.Scenario):
    subject = "streaming many steps"

    def given_user_id(self):
        self.user_id = 42

    def when_greeting_is_built(self):
        self.greeting = f"Hello, user-{self.user_id}!"

    def then_greeting_should_be_correct(self):
        assert self.greeting == "Hello, user-42!"

    def and_user_id_should_be_positive(self):
        assert self.user_id > 0
'''

    def when_the_scenario_runs_with_tr_teamcity(self):
        self.run = run_fixture_scenario(text=self.target_scenario, args=["--tr-teamcity"])

    def then_it_should_pass(self):
        assert self.run.returncode == 0

    def and_stdout_should_follow_the_expected_sequence(self):
        expected = schema.str.regex(in_order(
            "##teamcity[testSuiteStarted name='🔎 trace: streaming many steps'",
            "##teamcity[testSuiteStarted name='given_user_id'",
            "  ⇒ user_id: 42",
            "##teamcity[testSuiteFinished name='given_user_id']",
            "##teamcity[testSuiteStarted name='when_greeting_is_built'",
            "  ⇒ greeting: 'Hello, user-42!'",
            "##teamcity[testSuiteFinished name='when_greeting_is_built']",
            "##teamcity[testSuiteStarted name='then_greeting_should_be_correct'",
            "##teamcity[testSuiteFinished name='then_greeting_should_be_correct']",
            "##teamcity[testSuiteStarted name='and_user_id_should_be_positive'",
            "##teamcity[testSuiteFinished name='and_user_id_should_be_positive']",
            "##teamcity[testSuiteFinished name='🔎 trace: streaming many steps']",
        ))
        assert self.run.stdout == expected % self.run.stdout

    def and_all_suites_should_be_closed(self):
        actual = unclosed_suites(self.run.stdout)
        expected = schema.list([])
        assert actual == expected % actual
