from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_async_session
from app.core.config import settings
from app.models.complaint import (
    Complaint,
    ComplaintReason,
    ComplaintStatus,
    ComplaintTargetType,
    ModerationLog,
)
from app.models.user import User, UserRole
from app.models.video import Video, VideoStatus
from app.schemas.moderation import ComplaintCreate, ComplaintResponse, VideoHideRequest

router = APIRouter(prefix="", tags=["moderation"])


def _require_moderator_or_admin(current_user: User) -> None:
    if current_user.role not in (UserRole.moderator, UserRole.admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Moderator or admin role required",
        )


@router.post(
    "/reports",
    response_model=ComplaintResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Подать жалобу на контент",
)
async def create_complaint(
    complaint_in: ComplaintCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ComplaintResponse:
    """Создать жалобу (report) на видео, комментарий или пользователя.

    Требуется аутентификация. Любой авторизованный пользователь может пожаловаться.
    """
    complaint = Complaint(
        reporter_id=current_user.id,
        target_type=complaint_in.target_type,
        target_id=complaint_in.target_id,
        reason=complaint_in.reason,
        description=complaint_in.description,
        status=ComplaintStatus.pending,
    )
    session.add(complaint)
    await session.commit()
    await session.refresh(complaint)
    return ComplaintResponse.model_validate(complaint)


@router.patch(
    "/moderation/videos/{video_id}/hide",
    response_model=dict,
    summary="Скрыть видео (модератор/админ)",
)
async def hide_video(
    video_id: str,
    hide_request: VideoHideRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Скрыть видео — установить статус ``rejected`` и создать запись в логе модерации.

    Доступно только для moderator и admin.
    """
    _require_moderator_or_admin(current_user)

    result = await session.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
        )

    video.status = VideoStatus.rejected
    session.add(video)

    log = ModerationLog(
        moderator_id=current_user.id,
        action_type="video_hidden",
        target_type="video",
        target_id=video_id,
        reason=hide_request.reason,
    )
    session.add(log)
    await session.commit()

    return {
        "id": str(video.id),
        "status": video.status,
        "message": "Video hidden",
    }