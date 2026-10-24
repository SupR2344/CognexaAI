"""Security and Authentication Utilities.

Provides password hashing, JWT generation/validation, and
FastAPI dependencies for user session resolution.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme extraction for Bearer tokens
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login",
    description="Bearer JWT authentication token",
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check if the provided plain password matches the hashed password.

    Args:
        plain_password: Cleartext password string.
        hashed_password: Stored bcrypt hashed string.

    Returns:
        bool: True if passwords match, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate a bcrypt salt and hash for the plain password.

    Args:
        password: Raw password string.

    Returns:
        str: Bcrypt hashed password.
    """
    return pwd_context.hash(password)


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        data: Dictionary of claims to include in the payload.
        expires_delta: Optional custom duration until token expiration.

    Returns:
        str: Encoded JWT token string.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token.

    Args:
        token: Raw JWT string.

    Returns:
        Dict[str, Any]: Decoded payload claims.

    Raises:
        JWTError: If signature or expiration is invalid.
    """
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency to extract and authenticate the current user.

    Args:
        token: Bearer JWT token from Authorization header.
        db: Active async database session.

    Returns:
        User: Authenticated User database model.

    Raises:
        HTTPException: If credentials are invalid, token expired, or user not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Query the user in the database
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user
