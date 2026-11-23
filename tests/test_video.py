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
        data={"username": "uploader@example.com", "password": "secret123"},
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


async def _login_and_get_token(client: AsyncClient, email: str, password: str = "secret123") -> str:
    resp = await client.post(LOGIN_URL, data={"username": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _create_user_and_video(
    async_session,
    email: str,
    username: str,
    title: str,
    status: VideoStatus = VideoStatus.ready,
    visibility: VideoVisibility = VideoVisibility.public,
) -> tuple:
    user = User(
        email=email,
        username=username,
        password_hash=hash_password("secret123"),
        role=UserRole.user,
    )
    async_session.add(user)
    await async_session.flush()

    video = Video(
        author_id=user.id,
        title=title,
        description="Test video",
        original_s3_key=f"videos/{user.id}/test.mp4",
        visibility=visibility,
        status=status,
    )
    async_session.add(video)
    await async_session.commit()
    return user, video


@pytest.mark.asyncio
async def test_like_video(async_session, client: AsyncClient):
    user, video = await _create_user_and_video(
        async_session, "liker@example.com", "liker", "Likeable Video"
    )
    token = await _login_and_get_token(client, "liker@example.com")

    resp = await client.post(
        f"/videos/{video.id}/like",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["type"] == "like"
    assert body["target_type"] == "video"

    resp = await client.post(
        f"/videos/{video.id}/like",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204, resp.text


@pytest.mark.asyncio
async def test_like_video_unauthenticated(client: AsyncClient):
    resp = await client.post(
        "/videos/00000000-0000-0000-0000-000000000000/like"
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_like_nonexistent_video(async_session, client: AsyncClient):
    user = User(
        email="liker2@example.com",
        username="liker2",
        password_hash=hash_password("secret123"),
        role=UserRole.user,
    )
    async_session.add(user)
    await async_session.commit()
    token = await _login_and_get_token(client, "liker2@example.com")

    resp = await client.post(
        "/videos/00000000-0000-0000-0000-000000000000/like",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_create_comment(async_session, client: AsyncClient):
    user, video = await _create_user_and_video(
        async_session,
        "commenter@example.com",
        "commenter",
        "Commentable Video",
    )
    token = await _login_and_get_token(client, "commenter@example.com")

    resp = await client.post(
        f"/videos/{video.id}/comments",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "Отличное видео!"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["content"] == "Отличное видео!"
    assert body["author_username"] == "commenter"
    assert str(body["video_id"]) == str(video.id)
    assert body["parent_id"] is None
    assert body["is_deleted"] is False


@pytest.mark.asyncio
async def test_create_comment_with_parent(async_session, client: AsyncClient):
    user, video = await _create_user_and_video(
        async_session,
        "commenter2@example.com",
        "commenter2",
        "Commentable Video 2",
    )
    token = await _login_and_get_token(client, "commenter2@example.com")

    from app.models.comment import Comment

    parent = Comment(
        video_id=video.id,
        author_id=user.id,
        content="Родительский комментарий",
    )
    async_session.add(parent)
    await async_session.flush()

    resp = await client.post(
        f"/videos/{video.id}/comments",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "Ответ на комментарий", "parent_id": str(parent.id)},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert str(body["parent_id"]) == str(parent.id)
    assert body["content"] == "Ответ на комментарий"


@pytest.mark.asyncio
async def test_list_comments(async_session, client: AsyncClient):
    user, video = await _create_user_and_video(
        async_session,
        "commenter3@example.com",
        "commenter3",
        "Commentable Video 3",
    )
    token = await _login_and_get_token(client, "commenter3@example.com")

    for i in range(3):
        await client.post(
            f"/videos/{video.id}/comments",
            headers={"Authorization": f"Bearer {token}"},
            json={"content": f"Комментарий {i}"},
        )

    resp = await client.get(f"/videos/{video.id}/comments")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 3
    assert len(body["comments"]) == 3
    for c in body["comments"]:
        assert c["author_username"] == "commenter3"
        assert c["is_deleted"] is False


@pytest.mark.asyncio
async def test_list_comments_nonexistent_video(client: AsyncClient):
    resp = await client.get(
        "/videos/00000000-0000-0000-0000-000000000000/comments"
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_stream_video_public_ready(async_session, client: AsyncClient):
    user, video = await _create_user_and_video(
        async_session,
        "streamer@example.com",
        "streamer",
        "Streamable Video",
        status=VideoStatus.ready,
        visibility=VideoVisibility.public,
    )

    with patch(
        "app.api.video.get_presigned_url",
        new=AsyncMock(return_value="https://minio.example.com/presigned-url"),
    ) as mock_presigned:
        resp = await client.get(f"/videos/{video.id}/stream")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "url" in body
    assert body["expires_in"] == 3600
    mock_presigned.assert_called_once()


@pytest.mark.asyncio
async def test_stream_video_not_ready(async_session, client: AsyncClient):
    user, video = await _create_user_and_video(
        async_session,
        "streamer2@example.com",
        "streamer2",
        "Not Ready Video",
        status=VideoStatus.draft,
        visibility=VideoVisibility.public,
    )

    resp = await client.get(f"/videos/{video.id}/stream")
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_stream_video_not_public(async_session, client: AsyncClient):
    user, video = await _create_user_and_video(
        async_session,
        "streamer3@example.com",
        "streamer3",
        "Private Video",
        status=VideoStatus.ready,
        visibility=VideoVisibility.private,
    )

    resp = await client.get(f"/videos/{video.id}/stream")
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_stream_video_nonexistent(client: AsyncClient):
    resp = await client.get(
        "/videos/00000000-0000-0000-0000-000000000000/stream"
    )
    assert resp.status_code == 404, resp.text