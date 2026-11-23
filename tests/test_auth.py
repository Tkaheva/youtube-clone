import pytest
from httpx import AsyncClient

from app.core.security import hash_password
from app.models.user import User, UserRole

REGISTER_URL = "/auth/register"
LOGIN_URL = "/auth/login"


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    response = await client.post(
        REGISTER_URL,
        json={
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "secret123",
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["username"] == "newuser"
    assert data["role"] == "user"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(async_session, client: AsyncClient):
    existing = User(
        email="dup@example.com",
        username="dupuser",
        password_hash=hash_password("secret123"),
        role=UserRole.user,
    )
    async_session.add(existing)
    await async_session.commit()

    response = await client.post(
        REGISTER_URL,
        json={
            "email": "dup@example.com",
            "username": "another",
            "password": "secret123",
        },
    )
    assert response.status_code == 400, response.text
    assert "Email already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_username(async_session, client: AsyncClient):
    existing = User(
        email="dup2@example.com",
        username="dupusername",
        password_hash=hash_password("secret123"),
        role=UserRole.user,
    )
    async_session.add(existing)
    await async_session.commit()

    response = await client.post(
        REGISTER_URL,
        json={
            "email": "another2@example.com",
            "username": "dupusername",
            "password": "secret123",
        },
    )
    assert response.status_code == 400, response.text
    assert "Username already taken" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_success(async_session, client: AsyncClient):
    user = User(
        email="login@example.com",
        username="loginuser",
        password_hash=hash_password("secret123"),
        role=UserRole.user,
    )
    async_session.add(user)
    await async_session.commit()

    response = await client.post(
        LOGIN_URL,
        data={"username": "login@example.com", "password": "secret123"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(async_session, client: AsyncClient):
    user = User(
        email="wrong@example.com",
        username="wronguser",
        password_hash=hash_password("secret123"),
        role=UserRole.user,
    )
    async_session.add(user)
    await async_session.commit()

    response = await client.post(
        LOGIN_URL,
        data={"username": "wrong@example.com", "password": "badpassword"},
    )
    assert response.status_code == 401, response.text


@pytest.mark.asyncio
async def test_login_user_not_found(client: AsyncClient):
    response = await client.post(
        LOGIN_URL,
        data={"username": "nonexistent@example.com", "password": "secret123"},
    )
    assert response.status_code == 401, response.text