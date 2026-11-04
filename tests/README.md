# vedro-step-tracer — тесты плагина

Тесты плагина находятся в отдельном каталоге `tests/` и используют собственные
`pyproject.toml`, `uv.lock` и `.venv`. Пакет `vedro-step-tracer` подключён как
editable-зависимость из корня репозитория (`..`), поэтому тесты проверяют
текущий код плагина.

Unit- и e2e-тесты работают на изолированной фикстуре Vedro и не требуют
инфраструктуры проекта, в который устанавливается плагин.

## Установка

```bash
cd tests
make install   # uv sync, создаёт .venv и устанавливает зависимости
```

## Запуск тестов

```bash
make test        # unit + e2e
make test-unit    # только unit
make test-e2e     # только e2e
```

Команды для unit и e2e сьютов запускаются раздельно: если передать vedro
несколько несвязанных путей (`unit/scenarios e2e/scenarios`) одной командой,
он вычисляет общий корень (каталог `tests/`) и пытается просканировать как
сценарии вообще все `.py`-файлы внутри, включая `.venv`. Поэтому раздельные
вызовы — не условность, а обход этого ограничения CLI vedro.

## Структура

```
unit/                      — unit-тесты построения дерева вызовов (FunctionTracer)
  contexts/
    traced_calls.py        — простые трассируемые функции (вложенность, мутация scope)
    noisy_calls.py         — функции для проверки exclude_paths/exclude_functions
    step_runner.py         — FakeStepSelf, run_step(), call_names(), all_var_nodes()
  scenarios/
    tree/                  — поведение построения дерева (collapse, scope-diff, повторы)
    tracer/                — exclude_paths / exclude_functions

e2e/                       — e2e-тесты: запуск фикстуры как subprocess vedro
                              и проверка пользовательского вывода/отчётов
  fixtures/project/         — мини vedro-проект, который реально исполняется
    vedro.cfg.py            — настройки плагина читаются из TR_* env-переменных
    contexts/sample_calls.py
    scenarios/              — nested_calls (параметризован), failing_call,
                              parametrized_failing
  contexts/
    run_fixture_scenario.py — subprocess-запуск фикстуры + поиск html/artifact отчётов
  scenarios/
    terminal_report/        — stdout: ссылка на отчёт, тихий режим, print_to_stdout, разделитель
    html_report/             — сохранение .html отчёта (--tr, cleanup, long value preview)
    teamcity_report/         — --tr-teamcity service-messages
```

## Почему именно так

- **unit** проверяет `FunctionTracer`/`StepTree` напрямую, без запуска vedro —
  быстро и детально проверяет форму дерева (collapse passthrough, scope-diff,
  exclude_paths/exclude_functions).
- **e2e** гоняет настоящий `vedro run` на фикстуре в отдельном subprocess и
  сверяет ровно то, что увидит пользователь в терминале/файле отчёта —
  по одному сьюту на каждый тип отчёта (terminal/html/teamcity), с базовым
  набором параметров и с `--tr`.
