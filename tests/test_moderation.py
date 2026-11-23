import pytest
from httpx import AsyncClient

from app.core.security import hash_password
from app.models.complaint import ComplaintReason, ComplaintTargetType
from app.models.user import User, UserRole
from app.models.video import Video, VideoStatus, VideoVisibility

REPORTS_URL = "/reports"
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


async def _create_video(
    async_session, author: User, title: str = "Test Video"
) -> Video:
    video = Video(
        author_id=author.id,
        title=title,
        description="Test video",
        original_s3_key=f"videos/{author.id}/test.mp4",
        visibility=VideoVisibility.public,
        status=VideoStatus.ready,
    )
    async_session.add(video)
    await async_session.commit()
    return video


@pytest.mark.asyncio
async def test_create_complaint(async_session, client: AsyncClient):
    reporter = await _create_user(
        async_session, "reporter@example.com", "reporter"
    )
    video_author = await _create_user(
        async_session, "video_author@example.com", "video_author"
    )
    video = await _create_video(async_session, video_author)
    token = await _login_and_get_token(client, "reporter@example.com")

    resp = await client.post(
        REPORTS_URL,
        headers={"Authorization": f"Bearer {token}"},
        json={
            "target_type": "video",
            "target_id": str(video.id),
            "reason": "spam",
            "description": "Это спам",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert str(body["reporter_id"]) == str(reporter.id)
    assert body["target_type"] == "video"
    assert str(body["target_id"]) == str(video.id)
    assert body["reason"] == "spam"
    assert body["status"] == "pending"


@pytest.mark.asyncio
async def test_create_complaint_unauthenticated(client: AsyncClient):
    resp = await client.post(
        REPORTS_URL,
        json={
            "target_type": "video",
            "target_id": "00000000-0000-0000-0000-000000000000",
            "reason": "spam",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_hide_video_by_moderator(async_session, client: AsyncClient):
    moderator = await _create_user(
        async_session,
        "mod@example.com",
        "moderator",
        role=UserRole.moderator,
    )
    video_author = await _create_user(
        async_session, "vid_author@example.com", "vid_author"
    )
    video = await _create_video(async_session, video_author)
    token = await _login_and_get_token(client, "mod@example.com")

    resp = await client.patch(
        f"/moderation/videos/{video.id}/hide",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "Нарушение правил"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "rejected"
    assert "Video hidden" in body["message"]


@pytest.mark.asyncio
async def test_hide_video_by_admin(async_session, client: AsyncClient):
    admin = await _create_user(
        async_session,
        "admin@example.com",
        "admin_user",
        role=UserRole.admin,
    )
    video_author = await _create_user(
        async_session, "vid_author2@example.com", "vid_author2"
    )
    video = await _create_video(async_session, video_author)
    token = await _login_and_get_token(client, "admin@example.com")

    resp = await client.patch(
        f"/moderation/videos/{video.id}/hide",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "Недопустимый контент"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "rejected"


@pytest.mark.asyncio
async def test_hide_video_by_regular_user_forbidden(async_session, client: AsyncClient):
    user = await _create_user(
        async_session, "regular@example.com", "regular"
    )
    video_author = await _create_user(
        async_session, "vid_author3@example.com", "vid_author3"
    )
    video = await _create_video(async_session, video_author)
    token = await _login_and_get_token(client, "regular@example.com")

    resp = await client.patch(
        f"/moderation/videos/{video.id}/hide",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "Невозможно"},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_hide_nonexistent_video(async_session, client: AsyncClient):
    moderator = await _create_user(
        async_session,
        "mod2@example.com",
        "moderator2",
        role=UserRole.moderator,
    )
    token = await _login_and_get_token(client, "mod2@example.com")

    resp = await client.patch(
        "/moderation/videos/00000000-0000-0000-0000-000000000000/hide",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "Тест"},
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_hide_video_unauthenticated(client: AsyncClient):
    resp = await client.patch(
        "/moderation/videos/00000000-0000-0000-0000-000000000000/hide",
        json={"reason": "Тест"},
    )
    assert resp.status_code == 401