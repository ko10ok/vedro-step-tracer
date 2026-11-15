"""Разбор service-сообщений TeamCity из stdout фикстур-прогона."""

import re
from typing import List, Tuple

__all__ = ("messages", "suite_events", "all_suite_names", "unclosed_suites",
           "suites_without_duration")

_NAME = re.compile(r"name='((?:[^'|]|\|.)*)'")
_MESSAGE = re.compile(r"##teamcity\[(\w+)(.*?)\]")

_UNESCAPE = {
    "|'": "'",
    "|n": "\n",
    "|r": "\r",
    "||": "|",
    "|[": "[",
    "|]": "]",
}


def _unescape(value: str) -> str:
    result: List[str] = []
    i = 0
    while i < len(value):
        pair = value[i:i + 2]
        if pair in _UNESCAPE:
            result.append(_UNESCAPE[pair])
            i += 2
        else:
            result.append(value[i])
            i += 1
    return "".join(result)


def _name(body: str) -> str:
    match = _NAME.search(body)
    return _unescape(match.group(1)) if match else ""


def messages(stdout: str) -> List[Tuple[str, str]]:
    """Все service-сообщения в порядке появления: ``(тип, имя)``."""
    return [(_message.group(1), _name(_message.group(2)))
            for _message in _MESSAGE.finditer(stdout)]


def suite_events(stdout: str) -> List[Tuple[str, str]]:
    """События suite: ``("started"|"finished", имя)``."""
    kinds = {"testSuiteStarted": "started", "testSuiteFinished": "finished"}
    return [(kinds[message], name) for message, name in messages(stdout)
            if message in kinds]


def all_suite_names(stdout: str) -> List[str]:
    """Имена открытых suite в порядке открытия."""
    return [name for kind, name in suite_events(stdout) if kind == "started"]


def unclosed_suites(stdout: str) -> List[str]:
    """Имена suite, которые остались открытыми или закрылись не по порядку."""
    stack: List[str] = []
    problems: List[str] = []
    for kind, name in suite_events(stdout):
        if kind == "started":
            stack.append(name)
        elif not stack:
            problems.append(name)
        elif stack[-1] == name:
            stack.pop()
        else:
            problems.append(name)
            if name in stack:
                while stack and stack[-1] != name:
                    stack.pop()
                stack.pop()
    return problems + stack


def suites_without_duration(stdout: str) -> List[str]:
    """Имена завершённых suite, у которых нет атрибута duration."""
    return [_name(_message.group(2)) for _message in _MESSAGE.finditer(stdout)
            if _message.group(1) == "testSuiteFinished"
            and " duration='" not in _message.group(2)]
