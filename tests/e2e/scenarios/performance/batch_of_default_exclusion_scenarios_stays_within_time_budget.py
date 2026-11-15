import time

import vedro

from e2e.contexts.run_fixture_scenario import run_fixture_path


class Scenario(vedro.Scenario):
    subject = (
        "performance: a batch of 100 default-value-exclusion scenarios stays within the time budget"
    )

    def given_a_batch_of_default_exclusion_scenarios_and_a_repeat_count(self):
        self.scenarios_path = "scenarios/perf_exclude_default"
        self.repeats = 5
        self.max_avg_total_subprocess_seconds = 5.0

    def given_no_recorded_run_durations_yet(self):
        self.total_durations = []

    def when_the_batch_runs_several_times_in_a_row(self):
        for _ in range(self.repeats):
            started_at = time.perf_counter()
            self.run = run_fixture_path(self.scenarios_path)
            self.total_durations.append(time.perf_counter() - started_at)

    def then_every_repeat_should_pass_all_scenarios(self):
        assert self.run.returncode == 0

    def and_the_average_total_subprocess_time_should_stay_within_budget(self):
        average_total = sum(self.total_durations) / len(self.total_durations)
        assert average_total < self.max_avg_total_subprocess_seconds, (
            f"{average_total=:.2f}s, {self.total_durations=}"
        )
