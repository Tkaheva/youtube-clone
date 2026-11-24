import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_async_session
from app.core.config import settings
from app.core.s3 import ensure_bucket_exists, get_presigned_url, upload_fileobj
from app.models.user import User
from app.models.video import Video, VideoStatus, VideoVisibility
from app.schemas.video import VideoListResponse, VideoResponse, VideoUpload

router = APIRouter(prefix="/videos", tags=["videos"])


@router.post(
    "/upload",
    response_model=VideoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить видеофайл в S3 и создать запись о видео",
)
async def upload_video(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    visibility: VideoVisibility = Form(VideoVisibility.public),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> VideoResponse:
    """Загрузить видеофайл в S3-совместимое хранилище и сохранить метаданные в БД.

    Требуется аутентификация (JWT Bearer токен). Видео создаётся со статусом
    ``draft`` — после обработки (транSCODING) статус можно обновить на ``ready``.
    """
    await ensure_bucket_exists()

    # Генерируем уникальный ключ в S3: videos/{user_id}/{uuid}.{ext}
    filename = file.filename or "video"
    file_ext = filename.split(".")[-1] if "." in filename else "mp4"
    s3_key = f"videos/{current_user.id}/{uuid.uuid4()}.{file_ext}"

    # Загружаем файл в S3 (запускаем синхронный boto3 в пуле потоков)
    await upload_fileobj(
        file_obj=file.file,
        bucket=settings.S3_BUCKET,
        key=s3_key,
        content_type=file.content_type,
    )

    # Создаём запись о видео в БД
    video = Video(
        author_id=current_user.id,
        title=title,
        description=description,
        original_s3_key=s3_key,
        visibility=visibility,
        status=VideoStatus.draft,
    )
    session.add(video)
    await session.commit()
    await session.refresh(video)

    # Подгружаем автора для ответа
    result = await session.execute(select(User).where(User.id == current_user.id))
    author = result.scalar_one()

    return VideoResponse(
        id=video.id,
        title=video.title,
        description=video.description,
        s3_key=video.original_s3_key,
        thumbnail_s3_key=video.thumbnail_s3_key,
        duration_seconds=video.duration_seconds,
        views_count=video.views_count,
        status=video.status,
        visibility=video.visibility,
        author_id=video.author_id,
        author_username=author.username,
        created_at=video.created_at,
        updated_at=video.updated_at,
    )


@router.get(
    "",
    response_model=List[VideoListResponse],
    summary="Получить публичную ленту видео",
)
async def list_videos(
    session: AsyncSession = Depends(get_async_session),
    skip: int = 0,
    limit: int = 20,
) -> List[VideoListResponse]:
    """Вернуть список публичных видео (доступно без аутентификации)."""
    result = await session.execute(
        select(Video, User.username)
        .join(User, Video.author_id == User.id)
        .where(Video.visibility == VideoVisibility.public)
        .where(Video.status.in_([VideoStatus.ready, VideoStatus.draft]))
        .order_by(Video.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = result.all()

    return [
        VideoListResponse(
            id=video.id,
            title=video.title,
            description=video.description,
            s3_key=video.original_s3_key,
            thumbnail_s3_key=video.thumbnail_s3_key,
            status=video.status,
            visibility=video.visibility,
            author_id=video.author_id,
            author_username=username,
            created_at=video.created_at,
        )
        for video, username in rows
    ]


@router.get(
    "/search",
    response_model=List[VideoListResponse],
    summary="Поиск видео по названию",
)
async def search_videos(
    query: str = Query(..., min_length=1, description="Поисковый запрос"),
    session: AsyncSession = Depends(get_async_session),
) -> List[VideoListResponse]:
    """Ищет видео по названию (без учета регистра)."""
    result = await session.execute(
        select(Video, User.username)
        .join(User, Video.author_id == User.id)
        .where(Video.title.ilike(f"%{query}%"))
        .where(Video.visibility == VideoVisibility.public)
        .where(Video.status.in_([VideoStatus.ready, VideoStatus.draft]))
        .order_by(Video.created_at.desc())
    )
    rows = result.all()

    return [
        VideoListResponse(
            id=video.id,
            title=video.title,
            description=video.description,
            s3_key=video.original_s3_key,
            thumbnail_s3_key=video.thumbnail_s3_key,
            status=video.status,
            visibility=video.visibility,
            author_id=video.author_id,
            author_username=username,
            created_at=video.created_at,
        )
        for video, username in rows
    ]


@router.get(
    "/{video_id}/stream",
    summary="Получить presigned URL для просмотра видео",
)
async def stream_video(
    video_id: str,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Вернуть presigned URL для скачивания/просмотра видео из S3.

    Доступно для видео со статусом ``ready`` и visibility ``public``.
    """
    result = await session.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
        )

    if video.visibility != VideoVisibility.public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Video is not public",
        )

    if video.status != VideoStatus.ready:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Video is not ready for streaming",
        )

    presigned_url = await get_presigned_url(
        bucket=settings.S3_BUCKET,
        key=video.original_s3_key,
        expiration=3600,
    )
    return {"url": presigned_url, "expires_in": 3600}