"""IP allowlist helpers for restricted admin and management paths."""

from __future__ import annotations

import ipaddress
from typing import Iterable


def get_client_ip(
    request,
    *,
    trust_x_forwarded_for: bool,
    trusted_proxy_ips: Iterable[str] = ("127.0.0.1", "::1"),
) -> str:
    """Extract the client IP, honoring headers only from a trusted proxy."""
    remote_addr = (request.META.get("REMOTE_ADDR") or "").strip()
    trusted_proxies = parse_ip_allowlist(trusted_proxy_ips)
    if trust_x_forwarded_for and ip_is_allowed(remote_addr, trusted_proxies):
        real_ip = request.META.get("HTTP_X_REAL_IP")
        if real_ip:
            return real_ip.strip()
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[-1].strip()
    return remote_addr


def get_axes_client_ip(request) -> str:
    """Resolve Axes client IP through the same trusted-proxy policy."""
    from django.conf import settings

    return get_client_ip(
        request,
        trust_x_forwarded_for=getattr(settings, "TRUST_X_FORWARDED_FOR", False),
        trusted_proxy_ips=getattr(settings, "TRUSTED_PROXY_IPS", ()),
    )


def normalize_client_ip(ip_str: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Parse client IP; map IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1) to IPv4 for allowlist checks."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        return ip.ipv4_mapped
    return ip


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
    ip = normalize_client_ip(ip_str)
    if ip is None:
        return False
    for item in allowed:
        if isinstance(item, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
            if ip in item:
                return True
        elif ip == item:
            return True
    return False
