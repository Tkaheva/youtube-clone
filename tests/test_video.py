import pytest
from httpx import AsyncClient
from unittest.mock import patch
import io

from app.models.video import Video, VideoStatus, VideoVisibility
from app.models.user import User, UserRole
from app.core.security import hash_password
from app.models.comment import Comment
from app.models.reaction import Reaction, ReactionType

@pytest.mark.asyncio
async def test_upload_video(async_session, client: AsyncClient):
    # 1. Создаем пользователя напрямую в БД
    user = User(
        email="uploader@example.com",
        username="uploader",
        password_hash=hash_password("secret123"),
        role=UserRole.user
    )
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)

    # 2. Логинимся, чтобы получить токен
    login_data = {"username": "uploader@example.com", "password": "secret123"}
    login_res = await client.post("/auth/login", data=login_data)
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Загружаем видео (мокаем S3, чтобы не делать реальный запрос)
    file_content = b"fake video content"
    files = {"file": ("test.mp4", io.BytesIO(file_content), "video/mp4")}
    data = {"title": "My Test Video", "description": "Test description", "visibility": "public"}

    # Мокаем функцию загрузки в S3 (если Cline использовал boto3 upload_fileobj)
    with patch("app.core.s3.upload_fileobj") as mock_upload:
        mock_upload.return_value = "videos/test_key.mp4"
        
        res = await client.post(
            "/videos/upload",
            headers=headers,
            files=files,
            data=data
        )

    assert res.status_code == 200
    json_data = res.json()
    assert json_data["title"] == "My Test Video"
    assert json_data["author_username"] == "uploader"
    assert "id" in json_data

@pytest.mark.asyncio
async def test_upload_video_unauthorized(client: AsyncClient):
    # Попытка загрузить видео без токена
    files = {"file": ("test.mp4", io.BytesIO(b"fake"), "video/mp4")}
    data = {"title": "Hacked Video"}
    
    res = await client.post("/videos/upload", files=files, data=data)
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_get_videos_feed(async_session, client: AsyncClient):
    # Создаем пользователя и два видео (одно публичное, одно приватное)
    user = User(email="author@test.com", username="author", password_hash="h")
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)

    v1 = Video(title="Public Video", author_id=user.id, visibility=VideoVisibility.public, status=VideoStatus.ready, original_s3_key="k1")
    v2 = Video(title="Private Video", author_id=user.id, visibility=VideoVisibility.private, status=VideoStatus.ready, original_s3_key="k2")
    async_session.add_all([v1, v2])
    await async_session.commit()

    res = await client.get("/videos")
    assert res.status_code == 200
    data = res.json()
    
    # В публичной ленте должно быть только публичное видео
    assert len(data) == 1
    assert data[0]["title"] == "Public Video"

@pytest.mark.asyncio
async def test_video_streaming_url(async_session, client: AsyncClient):
    user = User(email="streamer@test.com", username="streamer", password_hash="h")
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)

    video = Video(title="Stream Me", author_id=user.id, visibility=VideoVisibility.public, status=VideoStatus.ready, original_s3_key="stream_key")
    async_session.add(video)
    await async_session.commit()

    # Мокаем генерацию presigned URL
    with patch("app.core.s3.get_presigned_url") as mock_presigned:
        mock_presigned.return_value = "http://localhost:9000/videos/stream_key.mp4"
        
        res = await client.get(f"/videos/{video.id}/stream")
        assert res.status_code == 200
        assert "url" in res.json() or "stream_url" in res.json()

@pytest.mark.asyncio
async def test_search_videos(async_session, client: AsyncClient):
    # Создаем автора
    user = User(email="search@test.com", username="searcher", password_hash=hash_password("secret"), role=UserRole.user)
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)

    # Создаем видео
    v1 = Video(title="Python Basics", author_id=user.id, visibility=VideoVisibility.public, status=VideoStatus.ready, original_s3_key="v1")
    v2 = Video(title="Advanced Python", author_id=user.id, visibility=VideoVisibility.public, status=VideoStatus.ready, original_s3_key="v2")
    v3 = Video(title="Java Tutorial", author_id=user.id, visibility=VideoVisibility.public, status=VideoStatus.ready, original_s3_key="v3")
    
    async_session.add_all([v1, v2, v3])
    await async_session.commit()

    # 1. Поиск с результатами
    resp = await client.get("/videos/search?query=Python")
    assert resp.status_code == 200
    data = resp.json()
    
    assert len(data) == 2
    titles = [v["title"] for v in data]
    assert "Python Basics" in titles
    assert "Advanced Python" in titles
    assert "Java Tutorial" not in titles

    # 2. Поиск без результатов
    resp_empty = await client.get("/videos/search?query=Ruby")
    assert resp_empty.status_code == 200
    assert len(resp_empty.json()) == 0