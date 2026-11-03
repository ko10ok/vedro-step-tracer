"""Статические ассеты HTML-отчёта (шаблон, CSS, JS) и их загрузка.

Ассеты лежат рядом с кодом отдельными файлами — так их редактируют с
подсветкой и линтингом в IDE. При рендере они читаются (с кэшем в памяти) и
инлайнятся в итоговую страницу: отчёт обязан оставаться одним самодостаточным
файлом, потому что открывается из артефактов GitLab CI.

Подстановка сделана явной заменой токенов, а не str.format: в CSS/JS/HTML
полно литеральных фигурных скобок, и str.format ломался бы на них
(``KeyError``/``ValueError``) — причём в рантайме, ровно в момент падения
сценария.
"""

import os
from typing import Dict

__all__ = ("load_asset", "render_report",)

_ASSETS_DIR = os.path.dirname(os.path.abspath(__file__))

_TEMPLATE_NAME = "report.html"
_STYLE_NAME = "report.css"
_SCRIPT_NAME = "report.js"

# Токены шаблона report.html, которые обязаны быть заполнены при рендере.
_TOKENS = ("title", "style", "script", "nav", "header", "body")

_cache: Dict[str, str] = {}


def load_asset(name: str) -> str:
    """Прочитать ассет по имени файла (с кэшированием в памяти процесса)."""
    if name not in _cache:
        with open(os.path.join(_ASSETS_DIR, name), encoding="utf-8") as f:
            _cache[name] = f.read()
    return _cache[name]


def render_report(*, title: str, nav: str, header: str, body: str) -> str:
    """Собрать самодостаточную HTML-страницу отчёта, инлайня CSS и JS."""
    values = {
        "title": title,
        "style": load_asset(_STYLE_NAME),
        "script": load_asset(_SCRIPT_NAME),
        "nav": nav,
        "header": header,
        "body": body,
    }
    document = load_asset(_TEMPLATE_NAME)
    for token in _TOKENS:
        document = document.replace("{{" + token + "}}", values[token])
    return document
