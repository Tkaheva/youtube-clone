import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ComplaintStatus(str, enum.Enum):
    pending = "pending"
    reviewed = "reviewed"
    resolved = "resolved"
    rejected = "rejected"


class ComplaintTargetType(str, enum.Enum):
    video = "video"
    comment = "comment"
    user = "user"


class ComplaintReason(str, enum.Enum):
    spam = "spam"
    violence = "violence"
    hate_speech = "hate_speech"
    copyright = "copyright"
    misinformation = "misinformation"
    other = "other"


class Complaint(Base):
    __tablename__ = "complaints"

    reporter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )  # кто пожаловался
    target_type: Mapped[ComplaintTargetType] = mapped_column(
        Enum(ComplaintTargetType), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        index=True, nullable=False
    )  # полиморфная цель (video / comment / user)
    reason: Mapped[ComplaintReason] = mapped_column(Enum(ComplaintReason), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[ComplaintStatus] = mapped_column(
        Enum(ComplaintStatus),
        default=ComplaintStatus.pending,
        nullable=False,
        index=True,
    )
    moderator_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )  # модератор, рассмотревший жалобу
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    reporter = relationship(
        "User",
        foreign_keys=[reporter_id],
        back_populates="complaints_reported",
    )
    moderator = relationship(
        "User",
        foreign_keys=[moderator_id],
        back_populates="complaints_reviewed",
    )


class ModerationLog(Base):
    __tablename__ = "moderation_logs"

    moderator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)  # video_approved, comment_blocked и т.д.
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)  # video / comment / user / complaint
    target_id: Mapped[uuid.UUID] = mapped_column(index=True, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    moderator = relationship("User", back_populates="moderation_logs")