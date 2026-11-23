import pytest
from cryptography.fernet import Fernet

from app.config import settings
from app.core.security import TokenEncryptionError, decrypt_token, encrypt_token


def test_token_round_trips_and_is_not_stored_in_plain_text():
    stored = encrypt_token("1//refresh-token")
    assert "refresh-token" not in stored
    assert decrypt_token(stored) == "1//refresh-token"


@pytest.mark.parametrize("key", ["", "too-short"])
def test_missing_or_invalid_key_fails_clearly(monkeypatch, key):
    monkeypatch.setattr(settings, "token_encryption_key", key)
    with pytest.raises(TokenEncryptionError, match="not a valid"):
        encrypt_token("x")


def test_token_from_another_key_cannot_be_decrypted(monkeypatch):
    stored = encrypt_token("x")
    monkeypatch.setattr(settings, "token_encryption_key", Fernet.generate_key().decode())
    with pytest.raises(TokenEncryptionError):
        decrypt_token(stored)
