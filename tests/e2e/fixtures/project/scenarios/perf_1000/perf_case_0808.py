import vedro

from contexts.heavy_calls import build_dataset, heavy_workload, summarize_level_1


class Scenario(vedro.Scenario):
    """Нагрузочный сценарий #0808 для перфоманс-теста трейсера на 1000 сценариях (см. e2e/scenarios/performance)."""

    subject = "perf case 0808: heavy nested calls over a complex dataset"

    def given_a_dataset_size(self):
        self.size = 35

    def when_the_heavy_workload_runs(self):
        self.total = heavy_workload(self.size)

    def then_the_total_should_be_positive(self):
        assert self.total > 0

    def and_a_second_dataset_is_built_and_summarized_directly(self):
        self.dataset = build_dataset(self.size)
        self.extra_total = summarize_level_1(self.dataset)
        assert self.extra_total == self.total
