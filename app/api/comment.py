from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_async_session
from app.models.comment import Comment
from app.models.user import User
from app.models.video import Video
from app.schemas.comment import CommentCreate, CommentListResponse, CommentResponse

router = APIRouter(prefix="/videos", tags=["comments"])


@router.post(
    "/{video_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить комментарий к видео",
)
async def create_comment(
    video_id: str,
    comment_in: CommentCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> CommentResponse:
    """Создать комментарий к видео (требуется аутентификация)."""
    # Проверяем, что видео существует
    result = await session.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
        )

    # Если указан parent_id, проверяем что родительский комментарий существует
    if comment_in.parent_id is not None:
        result = await session.execute(
            select(Comment).where(Comment.id == comment_in.parent_id)
        )
        parent = result.scalar_one_or_none()
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent comment not found",
            )

    comment = Comment(
        video_id=video_id,
        author_id=current_user.id,
        parent_id=comment_in.parent_id,
        content=comment_in.content,
    )
    session.add(comment)
    await session.commit()
    await session.refresh(comment)

    # Подгружаем автора для ответа
    result = await session.execute(select(User).where(User.id == current_user.id))
    author = result.scalar_one()

    return CommentResponse(
        id=comment.id,
        video_id=comment.video_id,
        author_id=comment.author_id,
        author_username=author.username,
        parent_id=comment.parent_id,
        content=comment.content,
        is_deleted=comment.is_deleted,
        is_blocked=comment.is_blocked,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


@router.get(
    "/{video_id}/comments",
    response_model=CommentListResponse,
    summary="Получить комментарии к видео",
)
async def list_comments(
    video_id: str,
    session: AsyncSession = Depends(get_async_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> CommentListResponse:
    """Получить список комментариев к видео (доступно без аутентификации)."""
    # Проверяем, что видео существует
    result = await session.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
        )

    # Считаем общее количество
    count_result = await session.execute(
        select(func.count(Comment.id)).where(
            Comment.video_id == video_id, Comment.is_deleted == False  # noqa: E712
        )
    )
    total = count_result.scalar_one()

    # Получаем комментарии с авторами
    result = await session.execute(
        select(Comment)
        .options(selectinload(Comment.author))
        .where(Comment.video_id == video_id, Comment.is_deleted == False)  # noqa: E712
        .order_by(Comment.created_at.asc())
        .offset(skip)
        .limit(limit)
    )
    comments = result.scalars().all()

    comment_responses = []
    for comment in comments:
        author_username = (
            comment.author.username if comment.author else "unknown"
        )
        comment_responses.append(
            CommentResponse(
                id=comment.id,
                video_id=comment.video_id,
                author_id=comment.author_id,
                author_username=author_username,
                parent_id=comment.parent_id,
                content=comment.content,
                is_deleted=comment.is_deleted,
                is_blocked=comment.is_blocked,
                created_at=comment.created_at,
                updated_at=comment.updated_at,
            )
        )

    return CommentListResponse(comments=comment_responses, total=total)