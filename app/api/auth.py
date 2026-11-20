import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserLogin, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация нового пользователя",
)
async def register(
    user_in: UserCreate,
    session: AsyncSession = Depends(get_async_session),
) -> UserResponse:
    """Создать нового пользователя с хешированным паролем."""
    # Проверка уникальности email и username
    result = await session.execute(
        select(User).where(
            (User.email == user_in.email) | (User.username == user_in.username)
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        if existing.email == user_in.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    new_user = User(
        email=user_in.email,
        username=user_in.username,
        password_hash=hash_password(user_in.password),
        role=UserRole.user,
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return UserResponse.model_validate(new_user)


@router.post(
    "/login",
    response_model=Token,
    summary="Вход: вернуть access и refresh JWT токены",
)
async def login(
    user_in: UserLogin,
    session: AsyncSession = Depends(get_async_session),
) -> Token:
    """Проверить учетные данные и вернуть пару JWT токенов."""
    result = await session.execute(select(User).where(User.email == user_in.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(user_in.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )

    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))
    return Token(access_token=access_token, refresh_token=refresh_token)