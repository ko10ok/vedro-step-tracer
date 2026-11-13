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
from vedro_step_tracer import ReportType, TestStatus, VedroStepTracer
from vedro_step_tracer.exclude import var


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value == "1"


def _env_save_to_dir(name: str, default: list) -> list:
    """
    Список событий для save_to_dir из переменной окружения.

    ``TR_SAVE_TO_DIR`` принимает значения через запятую (``failed,passed``).
    Для обратной совместимости ``1``/``true`` означают ``["failed"]``, а
    ``0``/``false`` — пустой список.
    """
    value = os.environ.get(name)
    if value is None:
        return list(default)
    value = value.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return [TestStatus.FAILED]
    if value in ("0", "false", "no", "off", ""):
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _env_report_formats(name: str, default: str) -> list:
    """
    Список форматов отчёта из запятую-разделённой переменной окружения.

    ReportType — не enum, а строковые константы, поэтому плагин сам
    принимает их текстом без учёта регистра: передавать строки прямо из
    env, без конвертации в ReportType, можно (см. VedroStepTracerPlugin._parse_report_formats).
    """
    value = os.environ.get(name, default)
    return [part.strip() for part in value.split(",") if part.strip()]


class Config(vedro.Config):

    class Plugins(vedro.Config.Plugins):

        class StepTracer(VedroStepTracer):
            enabled = True
            target_dirs = ["contexts"]
            attach_artifacts = _env_bool("TR_ATTACH_ARTIFACTS", True)
            save_to_dir = _env_save_to_dir("TR_SAVE_TO_DIR", [TestStatus.FAILED])
            report_formats = _env_report_formats("TR_REPORT_FORMATS", ReportType.HTML)
            output_dir = os.environ.get("TR_OUTPUT_DIR", "reports")
            print_to_stdout = _env_bool("TR_PRINT_TO_STDOUT", False)
            cleanup_before = True
            # Детерминированный job_id/pattern — не нужны локально, тест не
            # имитирует GitLab CI.
            job_id = ""

            # Исключение одной переменной по имени+функции — безвредно для
            # всех остальных сценариев, т.к. build_record_with_sensitive_local
            # вызывают только сценарии scenarios/perf_exclude_var.
            extra_exclude_value_types = [
                var("sensitive_token", function="build_record_with_sensitive_local"),
            ]
