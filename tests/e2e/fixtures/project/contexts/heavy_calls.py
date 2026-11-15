"""
Тяжёлые по данным и глубине вызовы — отдельно от contexts/sample_calls.py,
используются только нагрузочными сценариями из ``scenarios/perf/``,
``scenarios/perf_1000/``, ``scenarios/perf_exclude_default/`` и
``scenarios/perf_exclude_var/`` (см. ``e2e/scenarios/performance``).
"""

import socket
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


def build_record_holding_a_socket(index: int) -> Dict[str, Any]:
    sock = socket.socket()
    try:
        record = _build_record(index)
        record["has_socket"] = True
        return record
    finally:
        sock.close()


def heavy_workload_with_default_exclusion(size: int) -> int:
    dataset = [build_record_holding_a_socket(i) for i in range(size)]
    return summarize_level_1(dataset)


def build_record_with_sensitive_local(index: int) -> Dict[str, Any]:
    sensitive_token = {"secret": "x" * 64, "index": index}
    record = _build_record(index)
    record["token_len"] = len(sensitive_token["secret"])
    return record


def heavy_workload_with_var_exclusion(size: int) -> int:
    dataset = [build_record_with_sensitive_local(i) for i in range(size)]
    return summarize_level_1(dataset)
