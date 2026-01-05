from __future__ import annotations

import socket
from ipaddress import ip_address
from typing import Iterable
from urllib.parse import urlparse

from app.core.errors import FetchError


_PRIVATE_IP_PREFIXES = (
    "127.",
    "10.",
    "192.168.",
)


def _is_private_or_local(ip: str) -> bool:
    try:
        obj = ip_address(ip)
    except ValueError:
        return True

    if obj.is_loopback or obj.is_private or obj.is_link_local or obj.is_multicast or obj.is_reserved:
        return True

    # Some environments return IPv4-mapped IPv6; handle quickly.
    if obj.version == 4 and any(ip.startswith(p) for p in _PRIVATE_IP_PREFIXES):
        return True

    return False


def validate_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise FetchError("Only http/https URLs are allowed")

    host = parsed.hostname
    if not host:
        raise FetchError("Invalid URL: missing host")

    if host in {"localhost"}:
        raise FetchError("Blocked host: localhost")


def resolve_and_block_private_hosts(url: str) -> None:
    """Block URLs that resolve to private/internal IPs.

    This is a basic SSRF mitigation for deployments exposed to untrusted users.
    """

    validate_public_http_url(url)

    host = urlparse(url).hostname
    if not host:
        raise FetchError("Invalid URL: missing host")

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise FetchError(f"DNS resolution failed for host '{host}': {exc}") from exc

    ips: list[str] = []
    for family, _type, _proto, _canon, sockaddr in infos:
        if family == socket.AF_INET:
            ips.append(sockaddr[0])
        elif family == socket.AF_INET6:
            ips.append(sockaddr[0])

    if not ips:
        raise FetchError(f"No IP addresses resolved for host '{host}'")

    if any(_is_private_or_local(ip) for ip in ips):
        raise FetchError(f"Blocked host '{host}' (resolves to private/internal IP)")
