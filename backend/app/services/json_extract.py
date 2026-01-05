from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class JsonRecordsResult:
    records: list[dict[str, Any]]
    path: str


def _is_record(obj: Any) -> bool:
    return isinstance(obj, dict)


def _is_list_of_records(obj: Any) -> bool:
    return isinstance(obj, list) and obj and all(_is_record(x) for x in obj)


def extract_records_from_json(payload: Any) -> Optional[JsonRecordsResult]:
    # Direct list-of-objects
    if _is_list_of_records(payload):
        return JsonRecordsResult(records=payload, path="$")

    # Common: {"items": [..]} or nested containers.
    # BFS to find the largest list-of-records within a bounded search.
    if not isinstance(payload, (dict, list)):
        return None

    best: Optional[JsonRecordsResult] = None
    queue = deque([(payload, "$")])
    visited = 0

    while queue and visited < 500:
        node, path = queue.popleft()
        visited += 1

        if _is_list_of_records(node):
            candidate = JsonRecordsResult(records=node, path=path)
            if best is None or len(candidate.records) > len(best.records):
                best = candidate
            continue

        if isinstance(node, dict):
            for k, v in node.items():
                queue.append((v, f"{path}.{k}"))
        elif isinstance(node, list):
            for idx, v in enumerate(node[:50]):
                queue.append((v, f"{path}[{idx}]"))

    if best:
        return best

    # Fallback: If no list found, but root is a dict, treat it as a single record.
    # Essential for GraphQL / single-object API responses.
    if isinstance(payload, dict) and payload:
        return JsonRecordsResult(records=[payload], path="$")

    return None


def get_top_level_cursor(payload: Any, cursor_field: str) -> Optional[str]:
    if not cursor_field:
        return None

    # Support simple dotted paths like "data.after" in addition to top-level keys.
    node: Any = payload
    for part in cursor_field.split("."):
        if not part:
            return None
        if not isinstance(node, dict):
            return None
        node = node.get(part)
        if node is None:
            return None

    return str(node)
