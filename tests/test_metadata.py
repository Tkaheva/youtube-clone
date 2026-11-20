from sqlalchemy import UniqueConstraint

from app.models.base import Base

# Импортируем все модели, чтобы они зарегистрировались в Base.metadata
import app.models.user  # noqa: F401
import app.models.video  # noqa: F401
import app.models.comment  # noqa: F401
import app.models.reaction  # noqa: F401
import app.models.subscription  # noqa: F401
import app.models.complaint  # noqa: F401

EXPECTED_TABLES = {
    "users",
    "videos",
    "video_streams",
    "comments",
    "reactions",
    "subscriptions",
    "complaints",
    "moderation_logs",
}


def test_all_expected_tables_registered():
    registered = set(Base.metadata.tables.keys())
    missing = EXPECTED_TABLES - registered
    assert not missing, f"Отсутствуют таблицы: {missing}"


def test_users_columns_and_unique_constraints():
    table = Base.metadata.tables["users"]
    cols = {c.name for c in table.columns}
    for col in (
        "id",
        "email",
        "username",
        "password_hash",
        "role",
        "is_active",
        "is_verified",
        "created_at",
        "updated_at",
    ):
        assert col in cols, f"Отсутствует колонка {col} в таблице users"

    uniques = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    unique_col_sets = {frozenset(c.columns.keys()) for c in uniques}
    assert frozenset({"email"}) in unique_col_sets
    assert frozenset({"username"}) in unique_col_sets


def test_videos_has_fk_to_users():
    table = Base.metadata.tables["videos"]
    referred = {fk.target_fullname.split(".")[0] for fk in table.foreign_keys}
    assert "users" in referred


def test_comments_self_referential_fk():
    table = Base.metadata.tables["comments"]
    referred = {fk.target_fullname.split(".")[0] for fk in table.foreign_keys}
    assert "comments" in referred  # parent_id -> comments.id (ответы)


def test_reactions_unique_user_target():
    table = Base.metadata.tables["reactions"]
    uniques = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    col_sets = {frozenset(c.columns.keys()) for c in uniques}
    assert frozenset({"user_id", "target_type", "target_id"}) in col_sets


def test_subscriptions_unique_and_check_constraints():
    table = Base.metadata.tables["subscriptions"]
    uniques = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    col_sets = {frozenset(c.columns.keys()) for c in uniques}
    assert frozenset({"subscriber_id", "channel_id"}) in col_sets

    checks = [c for c in table.constraints if c.__class__.__name__ == "CheckConstraint"]
    assert any("subscriber_id <> channel_id" in str(c.sqltext) for c in checks)


def test_complaints_and_moderation_logs_have_fk_to_users():
    for tname in ("complaints", "moderation_logs"):
        table = Base.metadata.tables[tname]
        referred = {fk.target_fullname.split(".")[0] for fk in table.foreign_keys}
        assert "users" in referred, f"{tname}: нет внешнего ключа к таблице users"