import pytest
from httpx import AsyncClient

from app.core.security import hash_password
from app.models.user import User, UserRole

SUBSCRIBE_URL_TEMPLATE = "/users/{}/subscribe"
LOGIN_URL = "/auth/login"


async def _login_and_get_token(client: AsyncClient, email: str, password: str = "secret123") -> str:
    resp = await client.post(LOGIN_URL, data={"username": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _create_user(
    async_session, email: str, username: str, role: UserRole = UserRole.user
) -> User:
    user = User(
        email=email,
        username=username,
        password_hash=hash_password("secret123"),
        role=role,
    )
    async_session.add(user)
    await async_session.commit()
    return user


@pytest.mark.asyncio
async def test_subscribe_to_user(async_session, client: AsyncClient):
    subscriber = await _create_user(
        async_session, "subscriber@example.com", "subscriber"
    )
    channel = await _create_user(
        async_session, "channel@example.com", "channel_owner"
    )
    token = await _login_and_get_token(client, "subscriber@example.com")

    resp = await client.post(
        SUBSCRIBE_URL_TEMPLATE.format(channel.id),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["is_active"] is True
    assert str(body["subscriber_id"]) == str(subscriber.id)
    assert str(body["channel_id"]) == str(channel.id)


@pytest.mark.asyncio
async def test_subscribe_already_subscribed(async_session, client: AsyncClient):
    from app.models.subscription import Subscription

    subscriber = await _create_user(
        async_session, "sub2@example.com", "sub2"
    )
    channel = await _create_user(
        async_session, "ch2@example.com", "ch2"
    )

    sub = Subscription(
        subscriber_id=subscriber.id,
        channel_id=channel.id,
        is_active=True,
    )
    async_session.add(sub)
    await async_session.commit()

    token = await _login_and_get_token(client, "sub2@example.com")

    resp = await client.post(
        SUBSCRIBE_URL_TEMPLATE.format(channel.id),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400, resp.text
    assert "Already subscribed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_subscribe_to_self(async_session, client: AsyncClient):
    user = await _create_user(
        async_session, "selfsub@example.com", "selfsub"
    )
    token = await _login_and_get_token(client, "selfsub@example.com")

    resp = await client.post(
        SUBSCRIBE_URL_TEMPLATE.format(user.id),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400, resp.text
    assert "Cannot subscribe to yourself" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_subscribe_nonexistent_user(async_session, client: AsyncClient):
    user = await _create_user(
        async_session, "sub3@example.com", "sub3"
    )
    token = await _login_and_get_token(client, "sub3@example.com")

    resp = await client.post(
        "/users/00000000-0000-0000-0000-000000000000/subscribe",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_unsubscribe(async_session, client: AsyncClient):
    from app.models.subscription import Subscription

    subscriber = await _create_user(
        async_session, "unsub@example.com", "unsub"
    )
    channel = await _create_user(
        async_session, "unch@example.com", "unch"
    )

    sub = Subscription(
        subscriber_id=subscriber.id,
        channel_id=channel.id,
        is_active=True,
    )
    async_session.add(sub)
    await async_session.commit()

    token = await _login_and_get_token(client, "unsub@example.com")

    resp = await client.delete(
        SUBSCRIBE_URL_TEMPLATE.format(channel.id),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204, resp.text

    resp = await client.get(
        SUBSCRIBE_URL_TEMPLATE.format(channel.id),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["subscribed"] is False


@pytest.mark.asyncio
async def test_unsubscribe_not_subscribed(async_session, client: AsyncClient):
    user = await _create_user(
        async_session, "unsub2@example.com", "unsub2"
    )
    channel = await _create_user(
        async_session, "unch2@example.com", "unch2"
    )
    token = await _login_and_get_token(client, "unsub2@example.com")

    resp = await client.delete(
        SUBSCRIBE_URL_TEMPLATE.format(channel.id),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_subscription_status(async_session, client: AsyncClient):
    subscriber = await _create_user(
        async_session, "status_sub@example.com", "status_sub"
    )
    channel = await _create_user(
        async_session, "status_ch@example.com", "status_ch"
    )
    token = await _login_and_get_token(client, "status_sub@example.com")

    resp = await client.get(
        SUBSCRIBE_URL_TEMPLATE.format(channel.id),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["subscribed"] is False

    from app.models.subscription import Subscription

    sub = Subscription(
        subscriber_id=subscriber.id,
        channel_id=channel.id,
        is_active=True,
    )
    async_session.add(sub)
    await async_session.commit()

    resp = await client.get(
        SUBSCRIBE_URL_TEMPLATE.format(channel.id),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["subscribed"] is True


@pytest.mark.asyncio
async def test_subscribe_unauthenticated(client: AsyncClient):
    resp = await client.post(
        "/users/00000000-0000-0000-0000-000000000000/subscribe"
    )
    assert resp.status_code == 401