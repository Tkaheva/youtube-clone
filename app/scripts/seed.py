"""Скрипт наполнения базы демо-данными для YouTude.

Запуск:
    python -m app.scripts.seed

Требуется:
    - запущенная PostgreSQL (локальная или через docker compose)
    - переменные окружения из .env (DATABASE_URL)

Создаёт:
    - 6 пользователей (в т.ч. moderator и admin)
    - 8 видео (разных авторов, статусов и видимостей)
    - 12 комментариев (включая ответы на комментарии)
    - реакции (лайки/дизлайки) на видео
    - подписки между пользователями
    - жалобы (complaints) в разном статусе
"""

import asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import async_session_maker
from app.models.comment import Comment
from app.models.complaint import (
    Complaint,
    ComplaintReason,
    ComplaintStatus,
    ComplaintTargetType,
)
from app.models.reaction import Reaction, ReactionTarget, ReactionType
from app.models.subscription import Subscription
from app.models.user import User, UserRole
from app.models.video import Video, VideoStatus, VideoVisibility

USERS = [
    {
        "email": "alice@example.com",
        "username": "alice",
        "password": "password123",
        "role": UserRole.user,
        "is_verified": True,
    },
    {
        "email": "bob@example.com",
        "username": "bob",
        "password": "password123",
        "role": UserRole.user,
        "is_verified": False,
    },
    {
        "email": "carol@example.com",
        "username": "carol",
        "password": "password123",
        "role": UserRole.moderator,
        "is_verified": True,
    },
    {
        "email": "dave@example.com",
        "username": "dave",
        "password": "password123",
        "role": UserRole.admin,
        "is_verified": True,
    },
    {
        "email": "eve@example.com",
        "username": "eve",
        "password": "password123",
        "role": UserRole.user,
        "is_verified": True,
    },
    {
        "email": "frank@example.com",
        "username": "frank",
        "password": "password123",
        "role": UserRole.user,
        "is_verified": False,
    },
]

VIDEOS = [
    {
        "title": "Как начать разработку на FastAPI",
        "description": "Разбираем основы FastAPI: роутинг, зависимость, валидация Pydantic.",
        "original_s3_key": "videos/demo/001-fastapi-basics.mp4",
        "thumbnail_s3_key": "videos/demo/001-fastapi-basics-thumb.jpg",
        "duration_seconds": 1245,
        "status": VideoStatus.ready,
        "visibility": VideoVisibility.public,
    },
    {
        "title": "Погружение в PostgreSQL: индексы и оптимизация",
        "description": "Как правильно строить индексы и analyser запросов в PostgreSQL.",
        "original_s3_key": "videos/demo/002-postgres-indexes.mp4",
        "thumbnail_s3_key": "videos/demo/002-postgres-indexes-thumb.jpg",
        "duration_seconds": 2100,
        "status": VideoStatus.ready,
        "visibility": VideoVisibility.public,
    },
    {
        "title": "MinIO и S3: храним видео правильно",
        "description": "Настройка S3-совместимого хранилища MinIO для видеоплатформы.",
        "original_s3_key": "videos/demo/003-minio-s3.mp4",
        "thumbnail_s3_key": "videos/demo/003-minio-s3-thumb.jpg",
        "duration_seconds": 980,
        "status": VideoStatus.ready,
        "visibility": VideoVisibility.public,
    },
    {
        "title": "Черновик моего нового видео",
        "description": "Ещё не готово к публикации.",
        "original_s3_key": "videos/demo/004-draft.mp4",
        "thumbnail_s3_key": None,
        "duration_seconds": None,
        "status": VideoStatus.draft,
        "visibility": VideoVisibility.private,
    },
    {
        "title": "Отклонённое видео",
        "description": "Видео было отклонено модерацией.",
        "original_s3_key": "videos/demo/005-rejected.mp4",
        "thumbnail_s3_key": None,
        "duration_seconds": None,
        "status": VideoStatus.rejected,
        "visibility": VideoVisibility.private,
    },
    {
        "title": "Анонс канала Eve",
        "description": "Привет, я Eve! Добро пожаловать на мой канал.",
        "original_s3_key": "videos/demo/006-eve-intro.mp4",
        "thumbnail_s3_key": "videos/demo/006-eve-intro-thumb.jpg",
        "duration_seconds": 300,
        "status": VideoStatus.ready,
        "visibility": VideoVisibility.public,
    },
    {
        "title": "Таймлапс кодирования",
        "description": "12 часов кодирования за 3 минуты.",
        "original_s3_key": "videos/demo/007-timelapse.mp4",
        "thumbnail_s3_key": "videos/demo/007-timelapse-thumb.jpg",
        "duration_seconds": 180,
        "status": VideoStatus.ready,
        "visibility": VideoVisibility.public,
    },
    {
        "title": "Процессинг видео",
        "description": "Как мы перекодируем загруженные видео в разные разрешения.",
        "original_s3_key": "videos/demo/008-processing.mp4",
        "thumbnail_s3_key": None,
        "duration_seconds": None,
        "status": VideoStatus.processing,
        "visibility": VideoVisibility.public,
    },
]

COMMENTS = [
    {
        "video_index": 0,
        "user_index": 1,
        "content": "Отличное видео, спасибо!",
        "parent_id": None,
    },
    {
        "video_index": 0,
        "user_index": 2,
        "content": "А когда будет вторая часть?",
        "parent_id": None,
    },
    {
        "video_index": 0,
        "user_index": 0,
        "content": "Вторая часть планируется на следующий месяц.",
        "parent_id": 1,
    },
    {
        "video_index": 1,
        "user_index": 3,
        "content": "Полезно, особенно про индексы.",
        "parent_id": None,
    },
    {
        "video_index": 2,
        "user_index": 4,
        "content": "MinIO отлично работает с Docker.",
        "parent_id": None,
    },
    {
        "video_index": 5,
        "user_index": 0,
        "content": "Добро пожаловать, Eve!",
        "parent_id": None,
    },
    {
        "video_index": 5,
        "user_index": 1,
        "content": "Интересный канал, подписался.",
        "parent_id": None,
    },
    {
        "video_index": 6,
        "user_index": 2,
        "content": "Какой шрифт использовал в редакторе?",
        "parent_id": None,
    },
    {
        "video_index": 6,
        "user_index": 5,
        "content": "Fira Code.",
        "parent_id": 7,
    },
    {
        "video_index": 3,
        "user_index": 0,
        "content": "Когда будет готово?",
        "parent_id": None,
    },
    {
        "video_index": 7,
        "user_index": 1,
        "content": "Жду релиза!",
        "parent_id": None,
    },
    {
        "video_index": 7,
        "user_index": 3,
        "content": "Обработка идёт, скоро будет.",
        "parent_id": None,
    },
]


async def _create_user(session: AsyncSession, data: dict) -> User:
    user = User(
        email=data["email"],
        username=data["username"],
        password_hash=hash_password(data["password"]),
        role=data["role"],
        is_active=True,
        is_verified=data.get("is_verified", False),
    )
    session.add(user)
    await session.flush()
    return user


async def _create_video(
    session: AsyncSession, author: User, data: dict
) -> Video:
    video = Video(
        author_id=author.id,
        title=data["title"],
        description=data["description"],
        original_s3_key=data["original_s3_key"],
        thumbnail_s3_key=data.get("thumbnail_s3_key"),
        duration_seconds=data.get("duration_seconds"),
        status=data["status"],
        visibility=data["visibility"],
        published_at=(
            datetime.now(timezone.utc)
            if data["status"] == VideoStatus.ready
            else None
        ),
    )
    session.add(video)
    await session.flush()
    return video


async def _create_comment(
    session: AsyncSession, video: Video, author: User, data: dict
) -> Comment:
    comment = Comment(
        video_id=video.id,
        author_id=author.id,
        parent_id=data.get("parent_id"),
        content=data["content"],
        is_deleted=False,
        is_blocked=False,
    )
    session.add(comment)
    await session.flush()
    return comment