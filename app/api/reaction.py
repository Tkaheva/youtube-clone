from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_async_session
from app.models.reaction import Reaction, ReactionTarget, ReactionType
from app.models.user import User
from app.models.video import Video
from app.schemas.reaction import ReactionResponse

router = APIRouter(prefix="/videos", tags=["reactions"])


@router.post(
    "/{video_id}/like",
    response_model=ReactionResponse,
    summary="Поставить/убрать лайк на видео",
)
async def like_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ReactionResponse:
    """Переключить лайк на видео.

    Если пользователь уже ставил лайк — удаляет его (toggle).
    Если стоял dislike — заменяет на like.
    """
    # Проверяем, что видео существует
    result = await session.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
        )

    # Ищем существующую реакцию пользователя на это видео
    result = await session.execute(
        select(Reaction).where(
            Reaction.user_id == current_user.id,
            Reaction.target_type == ReactionTarget.video,
            Reaction.target_id == video_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        if existing.type == ReactionType.like:
            # Уже был лайк — удаляем (unlike)
            await session.delete(existing)
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_204_NO_CONTENT, detail="Like removed"
            )
        else:
            # Был dislike — меняем на like
            existing.type = ReactionType.like
            await session.commit()
            await session.refresh(existing)
            return ReactionResponse.model_validate(existing)

    # Создаём новый лайк
    reaction = Reaction(
        user_id=current_user.id,
        target_type=ReactionTarget.video,
        target_id=video_id,
        type=ReactionType.like,
    )
    session.add(reaction)
    await session.commit()
    await session.refresh(reaction)
    return ReactionResponse.model_validate(reaction)