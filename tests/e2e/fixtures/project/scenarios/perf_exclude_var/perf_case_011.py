import vedro

from contexts.heavy_calls import heavy_workload_with_var_exclusion


class Scenario(vedro.Scenario):
    """Нагрузочный сценарий #011 для перфоманс-теста исключения значений (var()-scoped exclusion (function + variable name))."""

    subject = "perf case 011: var()-scoped exclusion (function + variable name) (size=25)"

    def given_a_dataset_size(self):
        self.size = 25

    def when_the_heavy_workload_runs(self):
        self.total = heavy_workload_with_var_exclusion(self.size)

    def then_the_total_should_be_positive(self):
        assert self.total > 0
