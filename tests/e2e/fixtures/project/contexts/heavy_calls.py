"""
Тяжёлые по данным и глубине вызовы — отдельно от contexts/sample_calls.py,
используются только нагрузочными сценариями из ``scenarios/perf/`` (см.
``e2e/scenarios/performance``).
"""

from typing import Any, Dict, List


def _build_record(index: int) -> Dict[str, Any]:
    return {
        "id": index,
        "name": f"item-{index}",
        "tags": [f"tag-{index}-{j}" for j in range(6)],
        "meta": {
            "nested": {
                "deep": {
                    "value": index * 2,
                    "samples": list(range(index, index + 12)),
                },
            },
        },
    }


def build_dataset(size: int) -> List[Dict[str, Any]]:
    return [_build_record(i) for i in range(size)]


def summarize_level_3(dataset: List[Dict[str, Any]]) -> int:
    total = 0
    for record in dataset:
        total += record["meta"]["nested"]["deep"]["value"]
        total += sum(record["meta"]["nested"]["deep"]["samples"])
    return total


def summarize_level_2(dataset: List[Dict[str, Any]]) -> int:
    return summarize_level_3(dataset)


def summarize_level_1(dataset: List[Dict[str, Any]]) -> int:
    return summarize_level_2(dataset)


def heavy_workload(size: int) -> int:
    dataset = build_dataset(size)
    return summarize_level_1(dataset)
