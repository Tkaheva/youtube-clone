import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ReactionTarget(str, enum.Enum):
    video = "video"
    comment = "comment"


class ReactionType(str, enum.Enum):
    like = "like"
    dislike = "dislike"


class Reaction(Base):
    __tablename__ = "reactions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    target_type: Mapped[ReactionTarget] = mapped_column(
        Enum(ReactionTarget), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        index=True, nullable=False
    )  # без FK: полиморфная цель (видео или комментарий)
    type: Mapped[ReactionType] = mapped_column(Enum(ReactionType), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "user_id", "target_type", "target_id", name="uq_reaction_user_target"
        ),
        Index("ix_reactions_target", "target_type", "target_id"),
    )

    user = relationship("User", back_populates="reactions")