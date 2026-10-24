"""Authentication API Routes.

Handles user registration, login credential validation, JWT issuance,
and authenticated identity resolution.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.database import get_db
from app.models.user import User
from app.schemas.auth import Token, UserCreate, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Create a new user profile with hashed password credentials.

    Args:
        user_in: Registration details (username, email, password).
        db: Database session.

    Returns:
        UserResponse: Created user profile.

    Raises:
        HTTPException: If username or email is already taken.
    """
    stmt = select(User).where(
        or_(
            User.username == user_in.username.strip(),
            User.email == user_in.email.lower().strip(),
        )
    )
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        if existing_user.username == user_in.username.strip():
            detail = "Username is already taken"
        else:
            detail = "Email address is already registered"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )

    hashed_pw = get_password_hash(user_in.password)
    new_user = User(
        username=user_in.username.strip(),
        email=user_in.email.lower().strip(),
        hashed_password=hashed_pw,
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    access_token = create_access_token(
        data={"sub": new_user.username, "user_id": str(new_user.id)}
    )
    logger.info("New user registered successfully: %s (%s)", new_user.username, new_user.id)
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(new_user),
    )


@router.post(
    "/login",
    response_model=Token,
    summary="Authenticate and obtain JWT Bearer token",
)
async def login(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Authenticate user credentials and issue a signed JWT access token.

    Supports both standard JSON payload (`{"username": "...", "password": "..."}`)
    and form-data (`OAuth2PasswordRequestForm`) for seamless Swagger UI testing.

    Args:
        request: FastAPI HTTP Request.
        db: Database session.

    Returns:
        Token: JWT access token and token_type.

    Raises:
        HTTPException: If credentials are invalid.
    """
    username: Optional[str] = None
    password: Optional[str] = None

    # Determine if request payload is JSON or Form-data
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = await request.json()
            username = body.get("username") or body.get("email")
            password = body.get("password")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload",
            )
    else:
        form = await request.form()
        username = form.get("username") or form.get("email")  # type: ignore
        password = form.get("password")  # type: ignore

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email and password are required",
        )

    # Check against username or email
    stmt = select(User).where(
        or_(
            User.username == str(username).strip(),
            User.email == str(username).lower().strip(),
        )
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    access_token = create_access_token(
        data={"sub": user.username, "user_id": str(user.id)}
    )
    logger.info("User logged in successfully: %s", user.username)

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get currently authenticated user details",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Return profile attributes of the authenticated user.

    Args:
        current_user: User instance verified from Bearer JWT.

    Returns:
        UserResponse: Current user profile data.
    """
    return UserResponse.model_validate(current_user)
