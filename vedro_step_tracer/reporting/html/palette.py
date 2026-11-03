"""Цветовая палитра HTML-отчёта: акценты и фон по глубине вложенности."""

from typing import List, Tuple

__all__ = ("depth_colors", "solid_node_bg",)

# Палитра акцентных цветов для блоков вложенных вызовов — цвет циклически
# назначается по глубине вложенности, чтобы уровни легко различались на глаз
# (аналог "radial indent guides"). Красный/зелёный намеренно не используются,
# т.к. они зарезервированы под семантику статуса (FAIL/PASS).
_DEPTH_PALETTE: List[Tuple[str, str]] = [
    ("#58a6ff", "88,166,255"),    # синий
    ("#d2a8ff", "210,168,255"),   # фиолетовый
    ("#39c5cf", "57,197,207"),    # бирюзовый
    ("#e3b341", "227,179,65"),    # янтарный
    ("#f778ba", "247,120,186"),   # розовый
    ("#ffa657", "255,166,87"),    # оранжевый
]


def depth_colors(level: int) -> Tuple[str, str]:
    """Цвет акцента (hex, rgb) для блока вызова функции по глубине вложенности."""
    idx = max(level - 2, 0) % len(_DEPTH_PALETTE)
    return _DEPTH_PALETTE[idx]


# Базовый цвет фона страницы (из CSS: #0a0d11)
_BG_BASE = (10, 13, 17)
_NODE_BG_ALPHA_MIN = 0.04   # минимальная opacity (верхний уровень)
_NODE_BG_ALPHA_MAX = 0.14   # максимальная opacity (глубокая вложенность)
_NODE_BG_ALPHA_STEP = 0.02  # шаг прироста на каждый уровень


def solid_node_bg(color_rgb_str: str, level: int) -> str:
    """Вычисляет непрозрачный (solid) цвет фона узла с учётом глубины.

    Каждый уровень вложенности чуть ярче предыдущего, но не превышает
    _NODE_BG_ALPHA_MAX — так блоки визуально отличаются друг от друга,
    но даже при глубокой вложенности фон не становится слишком ярким.

    Формула: base * (1 - alpha) + accent * alpha
    """
    depth = max(level - 2, 0)
    alpha = min(_NODE_BG_ALPHA_MIN + depth * _NODE_BG_ALPHA_STEP, _NODE_BG_ALPHA_MAX)
    parts = [int(x.strip()) for x in color_rgb_str.split(",")]
    r = int(_BG_BASE[0] * (1 - alpha) + parts[0] * alpha)
    g = int(_BG_BASE[1] * (1 - alpha) + parts[1] * alpha)
    b = int(_BG_BASE[2] * (1 - alpha) + parts[2] * alpha)
    return f"#{r:02x}{g:02x}{b:02x}"
