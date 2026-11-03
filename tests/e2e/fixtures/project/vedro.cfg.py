"""
Конфиг минимального vedro-проекта, который используется как подопытный
(subject under test) в e2e-тестах плагина vedro_step_tracer.

Настройки плагина читаются из переменных окружения, чтобы один и тот же
проект-фикстура мог прогоняться с разными комбинациями
attach_artifacts/save_to_dir/print_to_stdout из разных тестовых сьютов
(terminal/html/teamcity) без копирования проекта под каждый сьют.
"""

import os

import vedro
from vedro_step_tracer import VedroStepTracer


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value == "1"


class Config(vedro.Config):

    class Plugins(vedro.Config.Plugins):

        class StepTracer(VedroStepTracer):
            enabled = True
            target_dirs = ["contexts"]
            attach_artifacts = _env_bool("TR_ATTACH_ARTIFACTS", True)
            save_to_dir = _env_bool("TR_SAVE_TO_DIR", False)
            output_dir = os.environ.get("TR_OUTPUT_DIR", "reports")
            print_to_stdout = _env_bool("TR_PRINT_TO_STDOUT", False)
            cleanup_before = True
            # Детерминированный job_id/pattern — не нужны локально, тест не
            # имитирует GitLab CI.
            job_id = ""
