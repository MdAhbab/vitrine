"""Preview health-check SSRF guards.

/hosting/health makes an outbound request to a user-supplied URL, so it is the
one endpoint that can be aimed at internal infrastructure. Two layers guard it:
a hostname allow-list, and a resolved-address check for allow-listed names that
point somewhere private.
"""
from __future__ import annotations

import pytest

from backend.services.hosting.app import _host_allowed, _resolves_to_public_ip


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "gopher://127.0.0.1:6379/_INFO",
    "ftp://vercel.app/",
])
def test_non_http_schemes_are_rejected(url):
    assert _host_allowed(url) is False


@pytest.mark.parametrize("url", [
    "http://169.254.169.254/latest/meta-data/",
    "http://localhost:6379/",
    "https://evil.example.com/",
])
def test_hosts_outside_the_allow_list_are_rejected(url):
    assert _host_allowed(url) is False


@pytest.mark.parametrize("url", [
    "https://my-demo.vercel.app/",
    "https://vercel.app/",
])
def test_allow_listed_preview_hosts_pass_the_name_check(url):
    assert _host_allowed(url) is True


@pytest.mark.asyncio
@pytest.mark.parametrize("url,label", [
    ("http://127.0.0.1/", "loopback"),
    ("http://localhost/", "loopback by name"),
    ("http://169.254.169.254/", "cloud metadata link-local"),
    ("http://10.0.0.5/", "RFC1918"),
    ("http://192.168.1.1/", "RFC1918"),
    ("http://172.16.0.1/", "RFC1918"),
    ("http://0.0.0.0/", "unspecified"),
    ("http://[::1]/", "IPv6 loopback"),
])
async def test_private_targets_are_rejected_by_the_address_check(url, label):
    """The allow-list is a string match and preview hosts are user-controlled
    subdomains, so an attacker can point an allowed name at a private address.
    This is the layer that catches it."""
    assert await _resolves_to_public_ip(url) is False, label


@pytest.mark.asyncio
async def test_a_public_address_is_allowed_through():
    assert await _resolves_to_public_ip("http://8.8.8.8/") is True


@pytest.mark.asyncio
async def test_unresolvable_host_fails_closed():
    assert await _resolves_to_public_ip(
        "http://definitely-not-a-real-host.invalid/") is False
