from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional, Union

from app.core.errors import ParseError


@dataclass(frozen=True)
class PageParamPagination:
    type: Literal["page_param"]
    param: str
    start: int
    end: int


@dataclass(frozen=True)
class OffsetPagination:
    type: Literal["offset"]
    offset_param: str
    limit_param: str
    limit: int
    max_pages: int
    start_offset: int = 0


@dataclass(frozen=True)
class CursorPagination:
    type: Literal["cursor"]
    cursor_param: str
    cursor_field: str
    max_pages: int = 10
    initial_cursor: Optional[str] = None


Pagination = Union[PageParamPagination, OffsetPagination, CursorPagination]


def parse_pagination(pagination: dict[str, Any], *, allow_cursor: bool) -> Pagination:
    if not isinstance(pagination, dict):
        raise ParseError("pagination must be an object")

    ptype = pagination.get("type")
    if ptype == "page_param":
        param = str(pagination.get("param") or "").strip()
        start = int(pagination.get("start") or 1)
        end = int(pagination.get("end") or start)
        if not param:
            raise ParseError("pagination.param is required")
        if start < 1 or end < start:
            raise ParseError("pagination.start/end invalid")
        return PageParamPagination(type="page_param", param=param, start=start, end=end)

    if ptype == "offset":
        offset_param = str(pagination.get("offset_param") or "").strip()
        limit_param = str(pagination.get("limit_param") or "").strip()
        limit = int(pagination.get("limit") or 0)
        max_pages = int(pagination.get("max_pages") or 0)
        start_offset = int(pagination.get("start_offset") or 0)
        if not offset_param or not limit_param:
            raise ParseError("pagination.offset_param and pagination.limit_param are required")
        if limit < 1 or max_pages < 1 or start_offset < 0:
            raise ParseError("pagination.limit/max_pages/start_offset invalid")
        return OffsetPagination(
            type="offset",
            offset_param=offset_param,
            limit_param=limit_param,
            limit=limit,
            max_pages=max_pages,
            start_offset=start_offset,
        )

    if ptype == "cursor":
        if not allow_cursor:
            raise ParseError("cursor pagination is API-only")
        cursor_param = str(pagination.get("cursor_param") or "").strip()
        cursor_field = str(pagination.get("cursor_field") or "").strip()
        max_pages = int(pagination.get("max_pages") or 10)
        initial_cursor = pagination.get("initial_cursor")
        if initial_cursor is not None:
            initial_cursor = str(initial_cursor)
        if not cursor_param or not cursor_field:
            raise ParseError("pagination.cursor_param and pagination.cursor_field are required")
        if max_pages < 1:
            raise ParseError("pagination.max_pages invalid")
        return CursorPagination(
            type="cursor",
            cursor_param=cursor_param,
            cursor_field=cursor_field,
            max_pages=max_pages,
            initial_cursor=initial_cursor,
        )

    raise ParseError("pagination.type must be one of: page_param, offset, cursor")
