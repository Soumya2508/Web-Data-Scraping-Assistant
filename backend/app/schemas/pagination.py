from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field


class PageParamPagination(BaseModel):
    type: Literal["page_param"]
    param: str = Field(min_length=1)
    start: int = Field(ge=1)
    end: int = Field(ge=1)


class OffsetPagination(BaseModel):
    type: Literal["offset"]
    offset_param: str = Field(min_length=1)
    limit_param: str = Field(min_length=1)
    limit: int = Field(ge=1)
    max_pages: int = Field(ge=1)
    start_offset: int = Field(ge=0, default=0)


class CursorPagination(BaseModel):
    type: Literal["cursor"]
    cursor_param: str = Field(min_length=1)
    cursor_field: str = Field(min_length=1)
    max_pages: int = Field(ge=1, default=10)
    initial_cursor: Optional[str] = None


Pagination = Annotated[
    Union[PageParamPagination, OffsetPagination, CursorPagination],
    Field(discriminator="type"),
]
