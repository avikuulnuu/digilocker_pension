"""IP allowlist helpers for restricted admin and management paths."""

from __future__ import annotations

import ipaddress
from typing import Iterable


def get_client_ip(request, *, trust_x_forwarded_for: bool) -> str:
    """Extract the client IP, optionally honoring X-Forwarded-For behind a trusted proxy."""
    if trust_x_forwarded_for:
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip()


def parse_ip_allowlist(entries: Iterable[str]) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address | ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """Parse comma-separated IPs or CIDR strings into address/network objects."""
    allowed: list = []
    for raw in entries:
        entry = raw.strip()
        if not entry:
            continue
        try:
            if "/" in entry:
                allowed.append(ipaddress.ip_network(entry, strict=False))
            else:
                allowed.append(ipaddress.ip_address(entry))
        except ValueError:
            continue
    return allowed


def ip_is_allowed(ip_str: str, allowed: list) -> bool:
    if not allowed:
        return False
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    for item in allowed:
        if isinstance(item, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
            if ip in item:
                return True
        elif ip == item:
            return True
    return False
