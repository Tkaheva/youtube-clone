import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class VideoStatus(str, enum.Enum):
    draft = "draft"
    processing = "processing"
    ready = "ready"
    rejected = "rejected"
    deleted = "deleted"


class VideoVisibility(str, enum.Enum):
    public = "public"
    unlisted = "unlisted"
    private = "private"


class Video(Base):
    __tablename__ = "videos"

    author_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    original_s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_s3_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    views_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[VideoStatus] = mapped_column(
        Enum(VideoStatus), default=VideoStatus.draft, nullable=False, index=True
    )
    visibility: Mapped[VideoVisibility] = mapped_column(
        Enum(VideoVisibility), default=VideoVisibility.public, nullable=False
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    author = relationship("User", back_populates="videos")
    streams = relationship(
        "VideoStream", back_populates="video", cascade="all, delete-orphan"
    )
    comments = relationship(
        "Comment", back_populates="video", cascade="all, delete-orphan"
    )


class VideoStream(Base):
    __tablename__ = "video_streams"

    video_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), index=True, nullable=False
    )
    resolution: Mapped[str] = mapped_column(String(10), nullable=False)  # 360p, 720p, 1080p
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    bitrate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    video = relationship("Video", back_populates="streams")