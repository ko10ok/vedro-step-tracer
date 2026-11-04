"""
Запуск фикстур-проекта (``fixtures/project``) как настоящего vedro-прогона в
отдельном процессе.

Это не вызов внутренних функций плагина, а ровно то, что видит пользователь:
аргументы командной строки на входе, stdout и файлы отчётов на выходе.
Поэтому прогон идёт тем же интерпретатором/venv, что и тесты (``uv sync``
установил туда и ``vedro``, и сам тестируемый плагин editable-зависимостью).

Текст проверяемого сценария — часть самого теста (передаётся строкой через
``text``), а не отдельный файл где-то в ``fixtures/``: так из теста сразу
видно, что именно трассируется и какие шаги/переменные приводят к
проверяемому выводу. ``run_fixture_scenario`` сам кладёт этот текст в файл
фикстур-проекта (путь можно задать явно через ``path``, иначе он
генерируется) и подчищает его после прогона.
"""

import glob
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

__all__ = ("FixtureRun", "run_fixture_scenario",)

_FIXTURE_PROJECT = Path(__file__).resolve().parents[1] / "fixtures" / "project"
_GENERATED_PREFIX = "_case_"


@dataclass
class FixtureRun:
    """Результат прогона фикстур-проекта: то, что получил бы пользователь."""

    returncode: int
    stdout: str
    scenario_path: str

    def html_reports(self, output_dir: str) -> List[Path]:
        """HTML-отчёты, сохранённые напрямую в ``output_dir`` (save_to_dir=1)."""
        pattern = str(_FIXTURE_PROJECT / output_dir / "*.html")
        return sorted(Path(p) for p in glob.glob(pattern))

    def markdown_reports(self, output_dir: str) -> List[Path]:
        """Markdown-отчёты, сохранённые напрямую в ``output_dir`` (save_to_dir=1)."""
        pattern = str(_FIXTURE_PROJECT / output_dir / "*.md")
        return sorted(Path(p) for p in glob.glob(pattern))

    def artifact_reports(self, name: str = "vedro-step-tracer.html") -> List[Path]:
        """Отчёты, записанные как артефакт сценария (attach_artifacts=1)."""
        pattern = str(_FIXTURE_PROJECT / ".vedro" / "artifacts" / "**" / name)
        return sorted(Path(p) for p in glob.glob(pattern, recursive=True))


def run_fixture_scenario(text: str, path: Optional[str] = None,
                         args: Optional[List[str]] = None,
                         env: Optional[Dict[str, str]] = None) -> FixtureRun:
    """
    Записать ``text`` как сценарий фикстур-проекта и прогнать его.

    :param text: исходный код сценария (вместе с ``import vedro`` и т.д.) —
        обычно это многострочная строка, объявленная тут же в тесте.
    :param path: путь сценария относительно фикстур-проекта, например
        ``"scenarios/my_case.py"``. Если не задан — генерируется случайное
        имя в ``scenarios/``, т.к. самому содержимому файла это имя не
        важно (сценарий не импортируется другими файлами).

    Состояние прошлого прогона (``.vedro/artifacts`` и ``reports/``, а
    также сгенерированные на прошлых прогонах файлы сценариев) стирается
    заранее, чтобы файлы отчётов можно было находить однозначным глобом.
    """
    scenario_path = path or f"scenarios/{_GENERATED_PREFIX}{uuid.uuid4().hex[:12]}.py"
    full_path = _FIXTURE_PROJECT / scenario_path

    _reset_fixture_state()
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(text, encoding="utf-8")
    try:
        full_env = dict(os.environ)
        full_env.update(env or {})
        result = subprocess.run(
            [sys.executable, "-m", "vedro", "run", scenario_path, *(args or [])],
            cwd=str(_FIXTURE_PROJECT),
            env=full_env,
            capture_output=True,
            text=True,
            timeout=60,
        )
    finally:
        full_path.unlink(missing_ok=True)

    return FixtureRun(returncode=result.returncode, stdout=result.stdout + result.stderr,
                      scenario_path=scenario_path)


def _reset_fixture_state() -> None:
    shutil.rmtree(_FIXTURE_PROJECT / ".vedro", ignore_errors=True)
    for reports_dir in _FIXTURE_PROJECT.glob("reports*"):
        shutil.rmtree(reports_dir, ignore_errors=True)
    # На случай, если предыдущий прогон был прерван до cleanup в finally.
    for leftover in _FIXTURE_PROJECT.glob(f"scenarios/{_GENERATED_PREFIX}*.py"):
        leftover.unlink(missing_ok=True)
