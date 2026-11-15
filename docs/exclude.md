# Исключение значений из трейса (`exclude_value_types`)

`exclude_value_types`/`extra_exclude_value_types` — исключения трейсинга
по типу значения, имени типа, модулю, regex, предикату или по конкретной
переменной в функции/модуле (а не по файлу/функции целиком, как
`exclude_paths`/`exclude_functions`).

## Зачем это нужно

Трейсер снимает снимок каждой переменной через `deepcopy`/`copy`. Объекты,
держащие ОС-ресурсы (пайпы, сокеты, транспорты и event loop `asyncio`,
`ssl`), либо падают при копировании, либо копируются как сам оригинал —
трейс держит на него ссылку дольше обычного, из-за чего он финализируется
уже при выходе из интерпретатора с шумом в stderr вида
`Exception ignored in: <function BaseSubprocessTransport.__del__ ...>`.

Правило заменяет такое значение заглушкой (`"<excluded from trace>"`)
**до** попытки копирования.

## Конфиг

```python
class StepTracer(VedroStepTracer):
    exclude_value_types = [...]        # базовый список (по умолчанию — см. ниже)
    extra_exclude_value_types = [...]  # добавляется поверх базового
```

## Виды правил

| Правило | Пример | Сравнение |
|---|---|---|
| Тип(ы) | `asyncio.BaseTransport` | `isinstance(value, rule)` — самое быстрое, им заданы дефолты |
| Имя типа | `"SSLSocket"` | `type(value).__name__ == rule` |
| Модуль | `module("asyncio")` | `type(value).__module__.startswith(prefix)` |
| Regex | `re.compile(r"_Unix.*Transport$")` | `.search()` по `module.qualname` |
| Callable | `lambda v: v is sentinel` | `rule(value)` |
| Переменная | `var("process", function="run_vedro")` | имя переменной (+ опционально функция/модуль) |

```python
from vedro_step_tracer.exclude import module, var

extra_exclude_value_types = [
    asyncio.StreamWriter,
    "MyCustomSocketWrapper",
    module("my_project.internal.transports"),
    re.compile(r"^my_project\..*Connection$"),
    lambda v: getattr(v, "_is_unsafe", False),
    var("process", function="run_vedro"),
]
```

Неиспользуемые виды правил (нет ни одного regex/callable/var) не
участвуют в проверке вообще — остаётся только `isinstance()`.

`var()` в отличие от `exclude_paths`/`exclude_functions` не убирает вызов
из дерева: заменяется только значение одной переменной, остальные
аргументы, вложенные вызовы и возврат трейсятся как обычно.
`function`/`module` сравниваются с `co_name` и относительным путём модуля
(`StepNode.module`) соответственно.

## Дефолты

```python
DEFAULT_EXCLUDED_VALUE_TYPES = (
    asyncio.BaseTransport,       # включая приватные подклассы (_UnixReadPipeTransport, ...)
    asyncio.AbstractEventLoop,   # включая _UnixSelectorEventLoop и т.п.
    asyncio.subprocess.Process,
    ssl.SSLSocket,
    ssl.SSLObject,
    socket.socket,
)
```

## Куда применяется

Заглушка подставляется для аргументов, локальных переменных, новых/изменённых
атрибутов `self` и возвращаемого значения — но возврат заменяется только если
подпадает под правило: без замены сохраняется сравнение по идентичности, на
котором держится схлопывание транзитных цепочек (`collapse_passthrough`).
