"""SSRF guard tests — the image loader must never touch internal/blocked ranges."""

import ipaddress

import pytest

from app.services import ssrf
from app.services.ssrf import check_image_url

_PUBLIC_IP = ipaddress.ip_address("93.184.216.34")


def _resolve_public(host):
    return [_PUBLIC_IP]


def test_allows_public_https(monkeypatch):
    monkeypatch.setattr(ssrf, "_resolve_ips", _resolve_public)
    check_image_url("https://example.com/image.png")  # no raise


def test_allows_public_http(monkeypatch):
    monkeypatch.setattr(ssrf, "_resolve_ips", _resolve_public)
    check_image_url("http://images.example.com/x.png")


def test_allows_lan_rfc1918_by_default():
    # Local-only deployment trusts the LAN.
    check_image_url("http://192.168.1.50/image.png")
    check_image_url("http://10.0.0.5/x.png")
    check_image_url("http://172.16.5.5/x.png")


def test_allows_lan_hostname_resolving_to_private(monkeypatch):
    monkeypatch.setattr(
        ssrf, "_resolve_ips", lambda host: [ipaddress.ip_address("192.168.1.9")]
    )
    check_image_url("http://n8n.local/image.png")


def test_blocks_loopback():
    with pytest.raises(ValueError):
        check_image_url("http://127.0.0.1:6379/")
    with pytest.raises(ValueError):
        check_image_url("http://localhost:4000/render")


def test_blocks_cloud_metadata():
    with pytest.raises(ValueError):
        check_image_url("http://169.254.169.254/latest/meta-data/")


def test_blocks_link_local():
    with pytest.raises(ValueError):
        check_image_url("http://169.254.100.1/status")


def test_blocks_hostname_resolving_to_blocked(monkeypatch):
    monkeypatch.setattr(
        ssrf, "_resolve_ips", lambda host: [ipaddress.ip_address("169.254.169.254")]
    )
    with pytest.raises(ValueError):
        check_image_url("http://metadata.aws.internal/secret")


def test_blocks_non_http_schemes():
    with pytest.raises(ValueError):
        check_image_url("file:///etc/passwd")
    with pytest.raises(ValueError):
        check_image_url("ftp://example.com/x.png")


def test_blocks_ipv6_loopback():
    with pytest.raises(ValueError):
        check_image_url("http://[::1]/x")


def test_allowlist_overrides_blocked_host(monkeypatch):
    monkeypatch.setattr(
        ssrf, "get_settings", lambda: type("S", (), {"image_allow_hosts": "169.254.169.254"})()
    )
    check_image_url("http://169.254.169.254/meta")  # explicitly trusted
