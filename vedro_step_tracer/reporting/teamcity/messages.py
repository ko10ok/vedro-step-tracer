"""Service-сообщения TeamCity, понимаемые тест-раннером PyCharm/IDEA.

Иерархия строится на ``testSuiteStarted``/``testSuiteFinished``: в
протоколе по именам (тот, что использует встроенный репортёр vedro
``-r pycharm``) вложенные ``testStarted`` деревом не становятся — они
попадают в текущий suite соседями. Поэтому узлом-контейнером всегда
выступает suite, а листом — test.

Расширенный протокол с ``nodeId``/``parentNodeId`` умеет произвольную
вложенность, но IDEA включает его только для конфигураций запуска,
объявленных id-based, — на обычном прогоне vedro такие атрибуты просто
игнорируются, поэтому он здесь не используется.
"""

import os
from typing import Any, Dict

__all__ = (
    "escape_value", "service_message", "test_suite_started", "test_suite_finished",
    "test_started", "test_finished", "test_failed", "file_location",
)

# Экранирование по спецификации TeamCity service messages.
_ESCAPE = {
    "'": "|'",
    "\n": "|n",
    "\r": "|r",
    "|": "||",
    "[": "|[",
    "]": "|]",
}
_ESCAPE_TABLE = {ord(k): v for k, v in _ESCAPE.items()}


def escape_value(value: str) -> str:
    """Экранировать значение атрибута service-сообщения."""
    return value.translate(_ESCAPE_TABLE)


def service_message(name: str, attributes: Dict[str, Any]) -> str:
    """Собрать строку service-сообщения (без завершающего перевода строки)."""
    parts = [f"##teamcity[{name}"]
    for key, value in attributes.items():
        parts.append(f" {key}='{escape_value(str(value))}'")
    parts.append("]")
    return "".join(parts)


def file_location(filename: str, lineno: int = 0) -> str:
    """
    Собрать locationHint вида ``file:///abs/path.py:42``.

    Такой протокол IDEA разбирает встроенным локатором по файлу, поэтому
    на узле дерева тестов появляется переход к исходнику (F4). Путь должен
    быть абсолютным и хостовым: тесты идут в контейнере, а открывает файл
    IDE на хосте (см. gitlab.to_host_path).
    """
    if not filename or not os.path.isabs(filename):
        return ""
    location = f"file://{filename}"
    return f"{location}:{lineno}" if lineno > 0 else location


def _with_location(attributes: Dict[str, Any], location: str) -> Dict[str, Any]:
    """Добавить locationHint, если он известен."""
    if location:
        attributes["locationHint"] = location
    return attributes


def test_suite_started(name: str, location: str = "") -> str:
    return service_message("testSuiteStarted", _with_location({"name": name}, location))


def test_suite_finished(name: str) -> str:
    return service_message("testSuiteFinished", {"name": name})


def test_started(name: str, location: str = "") -> str:
    # captureStandardOutput нужен, чтобы обычный вывод между testStarted и
    # testFinished попадал именно в этот узел дерева, а не в общий лог.
    return service_message("testStarted", _with_location(
        {"name": name, "captureStandardOutput": "true"}, location))


def test_finished(name: str, duration: float) -> str:
    """duration в секундах — в сообщении передаётся в миллисекундах."""
    return service_message("testFinished", {"name": name,
                                            "duration": int(max(duration, 0.0) * 1000)})


def test_failed(name: str, message: str, details: str = "") -> str:
    return service_message("testFailed", {"name": name, "message": message,
                                          "details": details})
