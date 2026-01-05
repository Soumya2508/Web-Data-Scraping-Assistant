from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from app.schemas.pagination import CursorPagination, OffsetPagination, PageParamPagination, Pagination


@dataclass
class PaginationRunResult:
    pages_fetched: int
    records_total: int
    stopped_reason: str


def run_pagination(
    *,
    pagination: Pagination,
    fetch_page: Callable[[dict[str, Any]], list[dict[str, Any]]],
    base_params: Optional[dict[str, Any]] = None,
    cursor_getter: Optional[Callable[[], Optional[str]]] = None,
    cursor_setter: Optional[Callable[[Optional[str]], None]] = None,
) -> tuple[list[dict[str, Any]], PaginationRunResult]:
    params = dict(base_params or {})
    all_records: list[dict[str, Any]] = []

    if isinstance(pagination, PageParamPagination):
        pages_fetched = 0
        for page in range(pagination.start, pagination.end + 1):
            params[pagination.param] = page
            records = fetch_page(params)
            pages_fetched += 1
            if not records:
                return (
                    all_records,
                    PaginationRunResult(pages_fetched=pages_fetched, records_total=len(all_records), stopped_reason="empty_page"),
                )
            all_records.extend(records)
        return (
            all_records,
            PaginationRunResult(pages_fetched=pages_fetched, records_total=len(all_records), stopped_reason="end_reached"),
        )

    if isinstance(pagination, OffsetPagination):
        pages_fetched = 0
        offset = pagination.start_offset
        for _ in range(pagination.max_pages):
            params[pagination.offset_param] = offset
            params[pagination.limit_param] = pagination.limit
            records = fetch_page(params)
            pages_fetched += 1
            if not records:
                return (
                    all_records,
                    PaginationRunResult(pages_fetched=pages_fetched, records_total=len(all_records), stopped_reason="empty_page"),
                )
            all_records.extend(records)
            offset += pagination.limit
        return (
            all_records,
            PaginationRunResult(pages_fetched=pages_fetched, records_total=len(all_records), stopped_reason="max_pages"),
        )

    if isinstance(pagination, CursorPagination):
        pages_fetched = 0
        cursor = pagination.initial_cursor
        for _ in range(pagination.max_pages):
            if cursor is not None:
                params[pagination.cursor_param] = cursor
            elif pagination.cursor_param in params:
                params.pop(pagination.cursor_param, None)

            records = fetch_page(params)
            pages_fetched += 1
            if not records:
                return (
                    all_records,
                    PaginationRunResult(pages_fetched=pages_fetched, records_total=len(all_records), stopped_reason="empty_page"),
                )
            all_records.extend(records)

            if cursor_getter is None:
                return (
                    all_records,
                    PaginationRunResult(pages_fetched=pages_fetched, records_total=len(all_records), stopped_reason="missing_cursor_getter"),
                )

            cursor = cursor_getter()
            if cursor_setter is not None:
                cursor_setter(cursor)

            if cursor is None:
                return (
                    all_records,
                    PaginationRunResult(pages_fetched=pages_fetched, records_total=len(all_records), stopped_reason="cursor_missing"),
                )

        return (
            all_records,
            PaginationRunResult(pages_fetched=pages_fetched, records_total=len(all_records), stopped_reason="max_pages"),
        )

    raise ValueError("Unknown pagination type")
