import io
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import hash_password
from app.models.user import User, UserRole
from app.models.video import Video, VideoStatus, VideoVisibility

REGISTER_URL = "/auth/register"
LOGIN_URL = "/auth/login"
UPLOAD_URL = "/videos/upload"
LIST_URL = "/videos"


@pytest.mark.asyncio
async def test_upload_video(async_session, client: AsyncClient):
    user = User(
        email="uploader@example.com",
        username="uploader",
        password_hash=hash_password("secret123"),
        role=UserRole.user,
    )
    async_session.add(user)
    await async_session.commit()

    # Логинимся, чтобы получить JWT
    login_resp = await client.post(
        LOGIN_URL,
        json={"email": "uploader@example.com", "password": "secret123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    # Мокаем S3-вызовы (MinIO не запущен в тестах). Патчим там, где используются функции — в app.api.video
    with patch(
        "app.api.video.upload_fileobj", new=AsyncMock(return_value="mocked/key.mp4")
    ) as mock_upload, patch(
        "app.api.video.ensure_bucket_exists", new=AsyncMock()
    ) as mock_ensure:
        file_content = b"fake video content"
        files = {"file": ("test.mp4", io.BytesIO(file_content), "video/mp4")}
        data = {
            "title": "Test Video",
            "description": "A test video",
            "visibility": "public",
        }
        resp = await client.post(
            UPLOAD_URL,
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
        )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "Test Video"
    assert body["description"] == "A test video"
    assert body["author_username"] == "uploader"
    assert body["status"] == "draft"
    assert body["visibility"] == "public"
    assert body["id"] is not None
    # S3-ключ генерируется сервисом: videos/{user_id}/{uuid}.mp4
    assert body["s3_key"].startswith(f"videos/{user.id}/")
    assert body["s3_key"].endswith(".mp4")
    mock_upload.assert_called_once()
    mock_ensure.assert_called_once()


@pytest.mark.asyncio
async def test_upload_video_unauthenticated(client: AsyncClient):
    with patch("app.api.video.upload_fileobj", new=AsyncMock()), patch(
        "app.api.video.ensure_bucket_exists", new=AsyncMock()
    ):
        file_content = b"fake video content"
        files = {"file": ("test.mp4", io.BytesIO(file_content), "video/mp4")}
        data = {"title": "Test Video"}
        resp = await client.post(UPLOAD_URL, files=files, data=data)

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_videos(async_session, client: AsyncClient):
    # Создаём автора и несколько видео
    author = User(
        email="author@example.com",
        username="author",
        password_hash=hash_password("secret123"),
        role=UserRole.user,
    )
    async_session.add(author)
    await async_session.flush()

    public_video = Video(
        author_id=author.id,
        title="Public Video",
        description="Public",
        original_s3_key="videos/author/1.mp4",
        visibility=VideoVisibility.public,
        status=VideoStatus.ready,
    )
    private_video = Video(
        author_id=author.id,
        title="Private Video",
        description="Private",
        original_s3_key="videos/author/2.mp4",
        visibility=VideoVisibility.private,
        status=VideoStatus.ready,
    )
    draft_video = Video(
        author_id=author.id,
        title="Draft Video",
        description="Draft",
        original_s3_key="videos/author/3.mp4",
        visibility=VideoVisibility.public,
        status=VideoStatus.draft,
    )
    async_session.add_all([public_video, private_video, draft_video])
    await async_session.commit()

    resp = await client.get(LIST_URL)
    assert resp.status_code == 200
    body = resp.json()
    # Должны вернуться только public видео (ready + draft)
    assert len(body) == 2
    titles = {v["title"] for v in body}
    assert titles == {"Public Video", "Draft Video"}
    for v in body:
        assert v["visibility"] == "public"
        assert v["author_username"] == "author"