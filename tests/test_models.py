import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.models.comment import Comment
from app.models.complaint import Complaint, ComplaintReason, ComplaintStatus
from app.models.reaction import Reaction, ReactionTarget, ReactionType
from app.models.subscription import Subscription
from app.models.user import User, UserRole
from app.models.video import Video, VideoStatus


@pytest.mark.asyncio
async def test_user_video_comment_lifecycle(async_session):
    author = User(
        email="author@test.com",
        username="author",
        password_hash="hashed_password",
        role=UserRole.user,
    )
    async_session.add(author)
    await async_session.flush()

    video = Video(
        author_id=author.id,
        title="My First Video",
        original_s3_key="videos/1/original.mp4",
        thumbnail_s3_key="videos/1/thumb.jpg",
        status=VideoStatus.ready,
    )
    async_session.add(video)
    await async_session.flush()

    comment = Comment(
        video_id=video.id,
        author_id=author.id,
        content="Great video!",
    )
    async_session.add(comment)
    await async_session.commit()

    stmt = (
        select(User)
        .where(User.id == author.id)
        .options(selectinload(User.videos), selectinload(User.comments))
    )
    result = await async_session.execute(stmt)
    loaded_user = result.scalar_one()

    assert len(loaded_user.videos) == 1
    assert loaded_user.videos[0].title == "My First Video"
    assert loaded_user.videos[0].status == VideoStatus.ready
    assert len(loaded_user.comments) == 1
    assert loaded_user.comments[0].content == "Great video!"
    assert loaded_user.comments[0].video_id == video.id


@pytest.mark.asyncio
async def test_comment_replies_self_reference(async_session):
    author = User(email="a@t.com", username="a", password_hash="h")
    async_session.add(author)
    await async_session.flush()

    video = Video(author_id=author.id, title="V", original_s3_key="k", status=VideoStatus.ready)
    async_session.add(video)
    await async_session.flush()

    parent = Comment(video_id=video.id, author_id=author.id, content="Parent comment")
    async_session.add(parent)
    await async_session.flush()

    reply = Comment(
        video_id=video.id,
        author_id=author.id,
        content="Reply",
        parent_id=parent.id,
    )
    async_session.add(reply)
    await async_session.commit()

    assert reply.parent_id == parent.id


@pytest.mark.asyncio
async def test_reaction_and_duplicate_constraint(async_session):
    author = User(email="a@t.com", username="a", password_hash="h")
    viewer = User(email="b@t.com", username="b", password_hash="h")
    async_session.add_all([author, viewer])
    await async_session.flush()

    video = Video(author_id=author.id, title="V", original_s3_key="k", status=VideoStatus.ready)
    async_session.add(video)
    await async_session.flush()

    reaction = Reaction(
        user_id=viewer.id,
        target_type=ReactionTarget.video,
        target_id=video.id,
        type=ReactionType.like,
    )
    async_session.add(reaction)
    await async_session.commit()
    assert reaction.id is not None

    # Повторная реакция на ту же цель — нарушение UNIQUE(user_id, target_type, target_id)
    dup = Reaction(
        user_id=viewer.id,
        target_type=ReactionTarget.video,
        target_id=video.id,
        type=ReactionType.dislike,
    )
    async_session.add(dup)
    with pytest.raises(IntegrityError):
        await async_session.flush()


@pytest.mark.asyncio
async def test_self_subscription_rejected(async_session):
    user = User(email="s@t.com", username="selfie", password_hash="h")
    async_session.add(user)
    await async_session.flush()

    sub = Subscription(subscriber_id=user.id, channel_id=user.id)
    async_session.add(sub)
    with pytest.raises(IntegrityError):
        await async_session.flush()


@pytest.mark.asyncio
async def test_subscription_unique_pair(async_session):
    a = User(email="a@t.com", username="a", password_hash="h")
    b = User(email="b@t.com", username="b", password_hash="h")
    async_session.add_all([a, b])
    await async_session.flush()

    async_session.add_all(
        [
            Subscription(subscriber_id=b.id, channel_id=a.id),
            Subscription(subscriber_id=b.id, channel_id=a.id),
        ]
    )
    with pytest.raises(IntegrityError):
        await async_session.flush()


@pytest.mark.asyncio
async def test_complaint_workflow(async_session):
    reporter = User(email="r@t.com", username="r", password_hash="h")
    moderator = User(
        email="m@t.com", username="m", password_hash="h", role=UserRole.moderator
    )
    async_session.add_all([reporter, moderator])
    await async_session.flush()

    complaint = Complaint(
        reporter_id=reporter.id,
        target_type="video",
        target_id=uuid.uuid4(),
        reason=ComplaintReason.spam,
        description="Спам в описании видео",
    )
    async_session.add(complaint)
    await async_session.commit()

    assert complaint.status == ComplaintStatus.pending
    assert complaint.id is not None

    # Модератор рассматривает жалобу
    complaint.status = ComplaintStatus.resolved
    complaint.moderator_id = moderator.id
    complaint.reviewed_at = datetime.now(timezone.utc)
    await async_session.commit()

    assert complaint.status == ComplaintStatus.resolved
    assert complaint.moderator_id == moderator.id
    assert complaint.reviewed_at is not None