from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def with_query_param(url: str, key: str, value: str) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query[key] = value
    new_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=new_query))
