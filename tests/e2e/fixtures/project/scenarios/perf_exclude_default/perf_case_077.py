import vedro

from contexts.heavy_calls import heavy_workload_with_default_exclusion


class Scenario(vedro.Scenario):
    """Нагрузочный сценарий #077 для перфоманс-теста исключения значений (default exclude_value_types (socket in a local))."""

    subject = "perf case 077: default exclude_value_types (socket in a local) (size=30)"

    def given_a_dataset_size(self):
        self.size = 30

    def when_the_heavy_workload_runs(self):
        self.total = heavy_workload_with_default_exclusion(self.size)

    def then_the_total_should_be_positive(self):
        assert self.total > 0
