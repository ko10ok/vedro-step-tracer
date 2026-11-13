"""Конфиг vedro для прогона тестов самого плагина (unit + e2e)."""

import vedro

from vedro_step_tracer import VedroStepTracer


class Config(vedro.Config):

    class Registry(vedro.Config.Registry):
        pass

    class Plugins(vedro.Config.Plugins):

        # Трейсим сам прогон тестов: отчёты упавших сценариев кладутся в
        # tests/traces/ — видно, что e2e-время уходит на subprocess в
        # run_fixture_scenario.
        class StepTracer(VedroStepTracer):
            target_dirs = ["e2e/contexts"]
            output_dir = "traces"
