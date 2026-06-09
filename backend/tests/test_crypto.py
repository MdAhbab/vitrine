"""Encryption helpers for admin API keys."""
from __future__ import annotations

from backend.shared.crypto import decrypt_value, encrypt_value


def test_encrypt_decrypt_roundtrip():
    plain = "sk-test-openai-key-12345"
    token = encrypt_value(plain)
    assert token != plain
    assert decrypt_value(token) == plain
