# VedroStepTracer

Плагин для [vedro](https://vedro.io/), который автоматически трейсит вызовы функций во время выполнения тестов и генерирует детальные HTML-отчёты с деревом вызовов, переменными и трейсбеком ошибок.

## Для чего нужен

При падении e2e-теста сложно понять **что именно произошло** — какие функции вызывались, с какими аргументами, что вернули и где упало. Плагин перехватывает все вызовы из указанных директорий через `sys.settrace()`, строит иерархическое дерево и сохраняет его как интерактивный HTML-файл и/или выводит в stdout.

- 🌳 **Видно весь путь до ошибки** — дерево вложенных вызовов `helpers/contexts/interfaces` с аргументами, локальными переменными и возвращаемыми значениями каждого шага, поэтому не нужно расставлять `print`/`breakpoint` и перезапускать тест, чтобы понять, где и с какими данными всё пошло не так
- 📄 **Отчёт файлом рядом с артефактами сценария** — пишется в `.vedro/artifacts/...` (раскладка `vedro.plugins.artifacted`) при падении сценария, а при `--tr` — и для успешных; в результат сценария добавляется кликабельная ссылка `🔎 Trace report: …`. Блоки с деталями упавшей ветки развёрнуты сразу, остальное свёрнуто, чтобы не тонуть в шуме
- ✂️ **Длинные значения сокращаются, но не теряются** — в HTML хвост скрыт под `…` и раскрывается по клику (и находится поиском по отчёту); в stdout и дереве тестов IDE обрезка жёсткая, полная версия остаётся в артефакте
- 🔗 **Прямая ссылка на артефакты job'а GitLab CI** — не нужно вручную искать нужный запуск и скачивать файл, чтобы посмотреть трейс

---

## CLI-флаги

| Флаг | Тип | По умолчанию | Описание |
|------|-----|-------------|----------|
| `--tr [LEVEL]` | `int` (0–3) | `1` (если указан без значения) | Включает интерактивный трейс в stdout. Уровни детализации: |
| | | | `0` — только return из target_dirs |
| | | | `1` — return + scope |
| | | | `2` — scope + args/return всех уровней |
| | | | `3` — всё (scope + args + locals + return) |
| `--tr-no-color` | `flag` | `false` | Отключить ANSI-раскраску в выводе трейса |
| `--tr-gitlab` | `flag` | auto | Добавить маркеры схлопываемых секций GitLab CI (автоопределяется по `CI_JOB_ID`) |

### Примеры запуска

```bash
# Базовый трейс (return + scope)
python -m vedro run --tr

# Максимальная детализация
python -m vedro run --tr 3

# Без цветов (для логов)
python -m vedro run --tr --tr-no-color
```

---

## Параметры конфигурации

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `enabled` | `bool` | `True` | Включить/выключить плагин |
| `target_dirs` | `list[str]` | `["helpers", "contexts", "interfaces"]` | Директории для трейсинга (относительно workdir) |
| `exclude_paths` | `list[str]` | `[]` | Glob-паттерны файлов внутри `target_dirs`, вызовы из которых не попадают в дерево |
| `exclude_functions` | `list[str]` | `[]` | Имена функций, которые не попадают в дерево |
| `exclude_value_types` | `list[...]` | уже найденные проблемные типы (asyncio-транспорты, event loop, `Process`, `ssl`, `socket`) | Правила, по которым значения переменных (а не вызовы) заменяются заглушкой вместо копирования — см. [`docs/exclude.md`](docs/exclude.md) |
| `extra_exclude_value_types` | `list[...]` | `[]` | То же самое поверх `exclude_value_types`, без переписывания базового списка — см. [`docs/exclude.md`](docs/exclude.md) |
| `attach_artifacts` | `bool` | `True` | Сохранять отчёт в директорию артефактов сценария |
| `report_formats` | `list[str]` | `[ReportType.HTML]` | Формат(ы) файлового отчёта: `ReportType.HTML`/`ReportType.MARKDOWN` или просто текстом `"html"`/`"markdown"` (без учёта регистра); оба сразу — `[ReportType.HTML, ReportType.MARKDOWN]` |
| `save_to_dir` | `list[str]` | `["failed"]` | События для сохранения отчёта в `output_dir`: `"failed"` и/или `"passed"`; при `--tr` файл пишется всегда |
| `output_dir` | `str` | `"logs/traces"` | Папка для файловых отчётов (нужна только при непустом `save_to_dir`) |
| `print_to_stdout` | `bool` | `False` | Печатать полное дерево в stdout (иначе — только ссылка на отчёт) |
| `max_str_len` | `int` | `1000` | Макс. длина строкового значения; применяется к каждой физической строке |
| `max_line_len` | `int` | `1000` | Макс. длина одной физической строки в выводе нестандартного объекта (`__str__`/`repr`/rich) |
| `collapse_passthrough` | `bool` | `True` | Схлопывать транзитные цепочки вызовов в одну хлебную крошку |
| `job_id` | `str` | `""` | ID задачи CI (для ссылок на артефакты) |
| `artifact_url_pattern` | `str` | `""` | Шаблон URL артефакта: `{job_id}`, `{path}` |
| `workdir_subpath` | `str` | `""` | Подпуть рабочей директории в репозитории; задайте, если тесты запускаются из вложенной директории |

---

## Пример конфигурации

```python
# vedro.cfg.py
import os
import vedro

from vedro_step_tracer import ReportType, VedroStepTracer


class Config(vedro.Config):

    class Plugins(vedro.Config.Plugins):

        class StepTracer(VedroStepTracer):
            enabled = True
            target_dirs = ['helpers', 'contexts', 'interfaces']
            exclude_paths = ['interfaces/generated_client.py']

            # Подробности и остальные виды правил — см. docs/exclude.md.
            extra_exclude_value_types = [var('process', function='run_vedro')]

            # Отчёт уходит файлом в артефакты сценария; stdout остаётся читаемым.
            attach_artifacts = True
            print_to_stdout = False
            report_formats = [ReportType.HTML]  # или [ReportType.HTML, ReportType.MARKDOWN]

            output_dir = 'logs/traces'
            save_to_dir = ["failed"]  # или ["failed", "passed"]

            job_id = os.environ.get('CI_JOB_ID')
            artifact_url_pattern = 'https://gitlab.example.com/group/SomeProject/-/jobs/{job_id}/artifacts/file/{path}'
```
