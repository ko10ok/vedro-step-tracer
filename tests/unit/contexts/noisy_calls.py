"""
Отдельный файл — имитирует "шумного" клиента (например обёртку над docker
SDK), который целиком исключается из дерева через ``exclude_paths``, а не
через ``exclude_functions``.
"""

from .traced_calls import leaf_sum


def noisy_wrapper(a: int, b: int) -> int:
    return leaf_sum(a, b)
