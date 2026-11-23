from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_async_session
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.subscription import SubscriptionResponse, SubscriptionStatus

router = APIRouter(prefix="/users", tags=["subscriptions"])


@router.post(
    "/{user_id}/subscribe",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Подписаться на канал пользователя",
)
async def subscribe_to_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> SubscriptionResponse:
    """Подписаться на канал.

    Если подписка уже существует (в т.ч. неактивная) — активирует её.
    Нельзя подписаться на самого себя.
    """
    # Проверяем, что канал существует
    result = await session.execute(select(User).where(User.id == user_id))
    channel = result.scalar_one_or_none()
    if channel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Нельзя подписаться на самого себя
    if current_user.id == channel.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot subscribe to yourself",
        )

    # Ищем существующую подписку
    result = await session.execute(
        select(Subscription).where(
            Subscription.subscriber_id == current_user.id,
            Subscription.channel_id == user_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        if existing.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Already subscribed",
            )
        # Reactivate
        existing.is_active = True
        await session.commit()
        await session.refresh(existing)
        return SubscriptionResponse.model_validate(existing)

    subscription = Subscription(
        subscriber_id=current_user.id,
        channel_id=user_id,
        is_active=True,
    )
    session.add(subscription)
    await session.commit()
    await session.refresh(subscription)
    return SubscriptionResponse.model_validate(subscription)


@router.delete(
    "/{user_id}/subscribe",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Отписаться от канала пользователя",
)
async def unsubscribe_from_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Отписаться от канала (помечает подписку как неактивную)."""
    result = await session.execute(
        select(Subscription).where(
            Subscription.subscriber_id == current_user.id,
            Subscription.channel_id == user_id,
        )
    )
    subscription = result.scalar_one_or_none()
    if subscription is None or not subscription.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )

    subscription.is_active = False
    await session.commit()


@router.get(
    "/{user_id}/subscribe",
    response_model=SubscriptionStatus,
    summary="Проверить статус подписки на канал",
)
async def get_subscription_status(
    user_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> SubscriptionStatus:
    """Проверить, подписан ли текущий пользователь на канал."""
    result = await session.execute(
        select(Subscription).where(
            Subscription.subscriber_id == current_user.id,
            Subscription.channel_id == user_id,
        )
    )
    subscription = result.scalar_one_or_none()

    if subscription is None:
        return SubscriptionStatus(subscribed=False, is_active=False)

    return SubscriptionStatus(
        subscribed=subscription.is_active, is_active=subscription.is_active
    )