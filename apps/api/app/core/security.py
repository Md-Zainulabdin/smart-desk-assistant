import hashlib
import secrets

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Response

from app.config import settings


class TokenEncryptionError(Exception):
    """The encryption key is missing, or a stored token cannot be decrypted with it."""


def _fernet() -> Fernet:
    try:
        return Fernet(settings.token_encryption_key)
    except ValueError:
        raise TokenEncryptionError("TOKEN_ENCRYPTION_KEY is not a valid Fernet key") from None


def encrypt_token(raw: str) -> str:
    """Encrypt an OAuth token before it is stored. The key lives outside the database."""
    return _fernet().encrypt(raw.encode()).decode()


def decrypt_token(stored: str) -> str:
    try:
        return _fernet().decrypt(stored.encode()).decode()
    except InvalidToken:
        raise TokenEncryptionError("stored token cannot be decrypted with this key") from None


def new_session_token() -> str:
    """A random opaque token. The raw value goes only into the cookie."""
    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> bytes:
    """The database stores only this hash, never the raw token."""
    return hashlib.sha256(raw_token.encode()).digest()


def set_session_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        max_age=settings.session_ttl_days * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
