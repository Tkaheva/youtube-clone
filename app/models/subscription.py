import uuid
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    subscriber_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )  # кто подписался
    channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )  # на кого подписались (канал)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "subscriber_id", "channel_id", name="uq_subscription"
        ),
        CheckConstraint(
            "subscriber_id <> channel_id", name="chk_no_self_subscription"
        ),
        Index("ix_subscriptions_channel", "channel_id"),
    )

    subscriber = relationship(
        "User",
        foreign_keys=[subscriber_id],
        back_populates="subscriptions_as_subscriber",
    )
    channel = relationship(
        "User",
        foreign_keys=[channel_id],
        back_populates="subscriptions_as_channel",
    )