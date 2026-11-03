import vedro

from e2e.contexts.run_fixture_scenario import run_fixture_scenario


class Scenario(vedro.Scenario):
    subject = "terminal report: parametrized runs are visually separated in the dump"

    def given_the_target_scenario(self):
        self.target_scenario = '''
import vedro
from vedro import params


class Scenario(vedro.Scenario):
    """
    Параметризованный падающий сценарий без трассируемых вызовов — нужен
    только для проверки, что в полном дампе дерева (``print_to_stdout``)
    отдельные запуски одного шаблона визуально разделены (фидбек Влады №2:
    "для параметризованных сценариев в мейлере хотелось бы более явного
    разделения между отдельными запусками").
    """

    subject = "trace a parametrized failing call ({user_id})"

    @params(1)
    @params(2)
    def __init__(self, user_id):
        self.user_id = user_id

    def given_nothing(self):
        pass

    def then_it_should_fail_on_purpose(self):
        assert self.user_id == 999
'''

    def when_both_parametrized_runs_fail_with_print_to_stdout(self):
        self.run = run_fixture_scenario(text=self.target_scenario,
                                        env={"TR_PRINT_TO_STDOUT": "1"})

    def then_both_runs_should_fail(self):
        assert self.run.returncode != 0

    def and_stdout_should_label_each_run_by_its_parametrization_index(self):
        assert "[1]" in self.run.stdout
        assert "[2]" in self.run.stdout

    def and_a_separator_line_should_precede_each_run(self):
        assert self.run.stdout.count("═" * 78) == 2
