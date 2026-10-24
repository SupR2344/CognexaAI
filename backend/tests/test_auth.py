"""Unit tests for Cognexa AI authentication and security utilities."""

from datetime import timedelta
import pytest
from jose import jwt

from app.auth.security import create_access_token, get_password_hash, verify_password
from app.config import settings


def test_password_hashing():
    """Verify bcrypt password hashing and verification."""
    password = "SuperSecretPassword123!"
    hashed = get_password_hash(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_create_access_token():
    """Verify signed JWT token generation and decoding."""
    subject = "admin@cognexa.ai"
    token = create_access_token(data={"sub": subject}, expires_delta=timedelta(minutes=30))

    assert isinstance(token, str)
    assert len(token) > 20

    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert decoded.get("sub") == subject
    assert "exp" in decoded
