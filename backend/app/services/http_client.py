"""
HTTP client with GET, POST, cookie support, and retry logic.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests

from app.core.config import settings
from app.core.errors import FetchError
from app.services.url_safety import resolve_and_block_private_hosts


DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class FetchResult:
    url: str
    status_code: int
    headers: dict[str, str]
    content: bytes


def _merged_headers(extra: Optional[dict[str, str]]) -> dict[str, str]:
    merged = {"User-Agent": DEFAULT_UA}
    if extra:
        merged.update(extra)
    return merged


def _build_cookie_header(cookies: Optional[dict[str, str]]) -> Optional[str]:
    """Convert cookie dict to cookie header string."""
    if not cookies:
        return None
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def get_bytes(
    url: str,
    headers: Optional[dict[str, str]] = None,
    params: Optional[dict[str, Any]] = None,
    cookies: Optional[dict[str, str]] = None,
    max_retries: int = 0,
) -> FetchResult:
    """
    Perform a GET request with optional cookies and retry logic.
    """
    if settings.block_private_networks:
        resolve_and_block_private_hosts(url)

    merged = _merged_headers(headers)
    cookie_header = _build_cookie_header(cookies)
    if cookie_header:
        merged["Cookie"] = cookie_header

    last_error: Optional[Exception] = None
    
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(
                url,
                headers=merged,
                params=params,
                timeout=(settings.http_connect_timeout_s, settings.http_read_timeout_s),
            )
            
            content = resp.content or b""
            if len(content) > settings.http_max_bytes:
                raise FetchError(f"Response too large (>{settings.http_max_bytes} bytes)")

            return FetchResult(
                url=str(resp.url),
                status_code=int(resp.status_code),
                headers={k: v for k, v in resp.headers.items()},
                content=content,
            )
        except requests.RequestException as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(1)  # Wait 1s before retry
                continue
            raise FetchError(f"Failed to fetch URL after {max_retries + 1} attempts: {exc}") from exc

    raise FetchError(f"Failed to fetch URL: {last_error}") from last_error


def post_bytes(
    url: str,
    headers: Optional[dict[str, str]] = None,
    body: Optional[dict[str, Any]] = None,
    cookies: Optional[dict[str, str]] = None,
    max_retries: int = 0,
) -> FetchResult:
    """
    Perform a POST request with JSON body, cookies, and retry logic.
    Ideal for GraphQL and other POST-based APIs.
    """
    if settings.block_private_networks:
        resolve_and_block_private_hosts(url)

    merged = _merged_headers(headers)
    
    # Ensure Content-Type for JSON
    if body is not None and "Content-Type" not in merged:
        merged["Content-Type"] = "application/json"
    
    cookie_header = _build_cookie_header(cookies)
    if cookie_header:
        merged["Cookie"] = cookie_header

    last_error: Optional[Exception] = None
    
    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(
                url,
                headers=merged,
                json=body,  # Auto-serializes dict to JSON
                timeout=(settings.http_connect_timeout_s, settings.http_read_timeout_s),
            )
            
            content = resp.content or b""
            if len(content) > settings.http_max_bytes:
                raise FetchError(f"Response too large (>{settings.http_max_bytes} bytes)")

            return FetchResult(
                url=str(resp.url),
                status_code=int(resp.status_code),
                headers={k: v for k, v in resp.headers.items()},
                content=content,
            )
        except requests.RequestException as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(1)  # Wait 1s before retry
                continue
            raise FetchError(f"Failed to POST URL after {max_retries + 1} attempts: {exc}") from exc

    raise FetchError(f"Failed to POST URL: {last_error}") from last_error


def try_parse_json(content: bytes) -> Optional[Any]:
    """Try to parse bytes as JSON."""
    try:
        return json.loads(content.decode("utf-8", errors="replace"))
    except Exception:
        return None
