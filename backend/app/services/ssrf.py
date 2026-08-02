"""SSRF guard for outbound image fetches.

The worker fetches client-supplied image URLs. This module validates that
the target is reachable without giving an attacker a probe of the local
host, the docker bridge, or cloud metadata.

Policy (local/LAN-only deployment):
  - http/https schemes only
  - loopback, link-local (incl. cloud metadata 169.254.169.254), multicast,
    broadcast, IANA special-purpose, benchmarking and TEST-NET ranges blocked
  - RFC1918 private ranges and IPv6 ULA are ALLOWED by default (trusted LAN)
  - IMAGE_ALLOW_HOSTS can opt-in hostnames/CIDRs that resolve to otherwise
    blocked addresses (defense-in-depth override for trusted infra)
"""

from __future__ import annotations

import ipaddress
import logging
import socket

from app.config import get_settings

log = logging.getLogger(__name__)

_BLOCKED_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    # IPv4
    ipaddress.ip_network("0.0.0.0/8"),        # "this" network
    ipaddress.ip_network("100.64.0.0/10"),     # shared/CGNAT
    ipaddress.ip_network("127.0.0.0/8"),       # loopback
    ipaddress.ip_network("169.254.0.0/16"),    # link-local (cloud metadata)
    ipaddress.ip_network("192.0.0.0/24"),      # IETF protocol assignments
    ipaddress.ip_network("192.0.2.0/24"),      # TEST-NET-1
    ipaddress.ip_network("192.88.99.0/24"),    # 6to4 relay anycast
    ipaddress.ip_network("198.18.0.0/15"),     # benchmarking
    ipaddress.ip_network("198.51.100.0/24"),   # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),    # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),       # multicast
    ipaddress.ip_network("240.0.0.0/4"),       # reserved
    ipaddress.ip_network("255.255.255.255/32"),  # limited broadcast
    # IPv6
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("::ffff:0:0/96"),     # IPv4-mapped (checked via v4 too)
    ipaddress.ip_network("fe80::/10"),         # link-local
    ipaddress.ip_network("ff00::/8"),          # multicast
    ipaddress.ip_network("2001:db8::/32"),     # documentation
]

_ALLOWED_LAN = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("fc00::/7"),          # IPv6 ULA
]


def _resolve_ips(hostname: str) -> list[ipaddress._BaseAddress]:
    """Resolve a hostname to a list of IP addresses."""
    try:
        infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return []
    seen: set[str] = set()
    ips: list[ipaddress._BaseAddress] = []
    for info in infos:
        addr = info[4][0]
        if addr in seen:
            continue
        seen.add(addr)
        try:
            ips.append(ipaddress.ip_address(addr))
        except ValueError:
            continue
    return ips


def _is_blocked(ip: ipaddress._BaseAddress) -> bool:
    """Return True if the address is in a blocked (never-legit) range."""
    candidates: list[ipaddress._BaseAddress] = [ip]
    mapped = ip.ipv4_mapped if ip.version == 6 else None
    if mapped is not None:
        candidates.append(mapped)
    for cand in candidates:
        for net in _BLOCKED_NETWORKS:
            if cand.version == net.version and cand in net:
                return True
    return False


def _load_allow_hosts() -> set[str]:
    settings = get_settings()
    raw = settings.image_allow_hosts or ""
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def check_image_url(url: str) -> None:
    """Validate a URL and its resolved addresses against the SSRF policy.

    Raises ValueError with a safe reason if the URL is not acceptable.
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme or 'none'}")
    host = parsed.hostname or ""
    if not host:
        raise ValueError("URL has no host")

    allow_hosts = _load_allow_hosts()
    if host.lower() in allow_hosts:
        return

    # Hostnames that are themselves in an allowed LAN range short-circuit too.
    try:
        literal = ipaddress.ip_address(host)
        if any(literal.version == n.version and literal in n for n in _ALLOWED_LAN):
            return
    except ValueError:
        pass  # not a literal IP — resolve it

    ips = _resolve_ips(host)
    if not ips:
        raise ValueError("Could not resolve image host")
    if any(_is_blocked(ip) for ip in ips):
        raise ValueError("Image URL resolves to a blocked address")


__all__ = ["check_image_url"]
