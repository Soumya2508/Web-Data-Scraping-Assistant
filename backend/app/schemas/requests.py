from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.pagination import Pagination


class DocumentAnalyzeRequest(BaseModel):
    url: str = Field(min_length=1)
    requested_fields: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    cookies: dict[str, str] = Field(default_factory=dict, description="Cookies to send with request")
    css_selector: Optional[str] = Field(default=None, description="CSS selector for repeating elements to extract")
    pagination: Optional[Pagination] = None
    delay_ms: int = Field(default=500, ge=0, le=10000, description="Delay between paginated requests in milliseconds")
    batch_identifiers: Optional[list[str]] = Field(default=None, description="List of identifiers to loop over")
    batch_variable_name: str = Field(default="id", description="Variable name to replace with identifier")


class XhrAnalyzeRequest(BaseModel):
    api_url: str = Field(min_length=1)
    method: Literal["GET", "POST"] = Field(default="GET", description="HTTP method")
    requested_fields: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    cookies: dict[str, str] = Field(default_factory=dict, description="Cookies to send with request")
    params: dict[str, Any] = Field(default_factory=dict, description="Query parameters (for GET)")
    body: Optional[dict[str, Any]] = Field(default=None, description="Request body JSON (for POST/GraphQL)")
    pagination: Optional[Pagination] = None
    delay_ms: int = Field(default=500, ge=0, le=10000, description="Delay between paginated requests in milliseconds")
    max_retries: int = Field(default=2, ge=0, le=5, description="Number of retries on failure")
    batch_identifiers: Optional[list[str]] = Field(default=None, description="List of identifiers to loop over")
    batch_variable_name: str = Field(default="id", description="Variable name to replace with identifier")


class SeleniumAnalyzeRequest(BaseModel):
    url: str = Field(min_length=1)
    requested_fields: list[str] = Field(default_factory=list)
    css_selector: str = Field(min_length=1)
    cookies: dict[str, str] = Field(default_factory=dict, description="Cookies to set before loading")
    wait_time: int = Field(default=5, ge=0, le=60)
    scroll_count: int = Field(default=0, ge=0, le=50, description="Number of times to scroll to bottom")
    scroll_delay_ms: int = Field(default=2000, ge=0, le=10000, description="Delay between scrolls in milliseconds")
    pagination: Optional[Pagination] = None
    delay_ms: int = Field(default=1000, ge=0, le=10000, description="Delay between paginated requests in milliseconds")
    batch_identifiers: Optional[list[str]] = Field(default=None, description="List of identifiers to loop over")
    batch_variable_name: str = Field(default="id", description="Variable name to replace with identifier")
