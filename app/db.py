"""Database engine/session setup (SQLite via SQLAlchemy) + light migrations."""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


_settings = get_settings()

_db_dir = os.path.dirname(os.path.abspath(_settings.db_path))
if _db_dir:
    os.makedirs(_db_dir, exist_ok=True)

engine = create_engine(
    f"sqlite:///{_settings.db_path}",
    echo=False,
    future=True,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record) -> None:  # type: ignore[no-untyped-def]
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create tables and apply idempotent schema migrations."""
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    migrate_schema()
    _reset_stale_generating()
    _reset_stale_background_jobs()


def _table_columns(table: str) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {r[1] for r in rows}


def _table_exists(table: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
            {"n": table},
        ).fetchone()
    return row is not None


def migrate_schema() -> None:
    """Idempotent SQLite upgrades for existing DBs."""
    if not _table_exists("novels"):
        return

    novel_cols = _table_columns("novels")
    with engine.begin() as conn:
        if "owner_id" not in novel_cols:
            conn.execute(text("ALTER TABLE novels ADD COLUMN owner_id INTEGER"))
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_novels_owner_id ON novels (owner_id)")
            )
            logger.info("Migrated: novels.owner_id")
        if "world_setting" not in novel_cols:
            conn.execute(text("ALTER TABLE novels ADD COLUMN world_setting TEXT DEFAULT ''"))
            logger.info("Migrated: novels.world_setting")
            # Copy legacy settings into world_setting where empty.
            conn.execute(
                text(
                    "UPDATE novels SET world_setting = settings "
                    "WHERE (world_setting IS NULL OR world_setting = '') "
                    "AND settings IS NOT NULL AND settings != ''"
                )
            )
        if "style_profile" not in novel_cols:
            conn.execute(text("ALTER TABLE novels ADD COLUMN style_profile TEXT DEFAULT ''"))
            logger.info("Migrated: novels.style_profile")

    if _table_exists("chapters"):
        ch_cols = _table_columns("chapters")
        with engine.begin() as conn:
            if "parent_id" not in ch_cols:
                conn.execute(text("ALTER TABLE chapters ADD COLUMN parent_id INTEGER"))
                logger.info("Migrated: chapters.parent_id")
            if "plot_directive" not in ch_cols:
                conn.execute(
                    text("ALTER TABLE chapters ADD COLUMN plot_directive TEXT DEFAULT ''")
                )
                logger.info("Migrated: chapters.plot_directive")
            if "is_primary" not in ch_cols:
                conn.execute(
                    text(
                        "ALTER TABLE chapters ADD COLUMN is_primary "
                        "INTEGER DEFAULT 0 NOT NULL"
                    )
                )
                logger.info("Migrated: chapters.is_primary")
            if "is_ending" not in ch_cols:
                conn.execute(
                    text(
                        "ALTER TABLE chapters ADD COLUMN is_ending INTEGER DEFAULT 0 NOT NULL"
                    )
                )
                logger.info("Migrated: chapters.is_ending")

        _backfill_chapter_tree()
        _backfill_primary_chapters()

    # Ensure new tables exist (create_all already did; no-op).
    Base.metadata.create_all(bind=engine)
    _migrate_legacy_ollama_provider()


def _migrate_legacy_ollama_provider() -> None:
    """Move historical local-model selections to the configured Gemini default.

    Existing novels persist their provider/model choice.  Without this migration,
    records created before Gemini became the default continue to call Ollama.
    """
    if not _table_exists("novels") or _settings.default_provider != "gemini":
        return

    with engine.begin() as conn:
        result = conn.execute(
            text(
                "UPDATE novels "
                "SET provider = 'gemini', model = :model, last_error = NULL "
                "WHERE provider = 'ollama'"
            ),
            {"model": _settings.gemini_default_model},
        )
    if result.rowcount:
        logger.info("Migrated %s novel(s) from Ollama to Gemini", result.rowcount)


def _backfill_chapter_tree() -> None:
    """Link linear chapters (by index) into a single path per novel when parent_id is unset."""
    with engine.begin() as conn:
        novels = conn.execute(text("SELECT id FROM novels")).fetchall()
        for (novel_id,) in novels:
            rows = conn.execute(
                text(
                    "SELECT id, parent_id, \"index\" FROM chapters "
                    "WHERE novel_id = :nid ORDER BY \"index\" ASC, id ASC"
                ),
                {"nid": novel_id},
            ).fetchall()
            if not rows:
                continue
            # Only backfill if every row has null parent (or all null except we need chain).
            if any(r[1] is not None for r in rows):
                continue
            prev_id = None
            for i, (cid, _pid, _idx) in enumerate(rows):
                if i == 0:
                    prev_id = cid
                    continue
                conn.execute(
                    text("UPDATE chapters SET parent_id = :pid WHERE id = :cid"),
                    {"pid": prev_id, "cid": cid},
                )
                prev_id = cid
            if len(rows) > 1:
                logger.info(
                    "Backfilled chapter tree for novel %s (%s nodes)", novel_id, len(rows)
                )


def _backfill_primary_chapters() -> None:
    """Give each existing branch point one deterministic default continuation."""
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT id, parent_id, is_primary, \"index\" FROM chapters "
                "WHERE parent_id IS NOT NULL "
                "ORDER BY parent_id ASC, \"index\" ASC, id ASC"
            )
        ).fetchall()

        current_parent: int | None = None
        group: list[tuple[int, int, int, int]] = []
        for row in rows:
            parent_id = row[1]
            if current_parent is not None and parent_id != current_parent:
                if not any(item[2] for item in group):
                    conn.execute(
                        text("UPDATE chapters SET is_primary = 1 WHERE id = :id"),
                        {"id": group[0][0]},
                    )
                group = []
            current_parent = parent_id
            group.append(row)

        if group and not any(item[2] for item in group):
            conn.execute(
                text("UPDATE chapters SET is_primary = 1 WHERE id = :id"),
                {"id": group[0][0]},
            )


def _reset_stale_generating() -> None:
    """Clear is_generating left over from a crash."""
    if not _table_exists("novels"):
        return
    with engine.begin() as conn:
        conn.execute(text("UPDATE novels SET is_generating = 0 WHERE is_generating = 1"))


def _reset_stale_background_jobs() -> None:
    """Mark daemon-thread work interrupted by a process restart as retryable.

    Imports and comic rendering use in-process workers.  Those threads cannot
    survive a deployment/restart, so keeping their prior `processing` state
    would make the UI poll forever.  The original source and generated panels
    remain on disk/in SQLite; only the incomplete operation is marked failed.
    """
    has_source_documents = _table_exists("source_documents")
    has_comic_panels = _table_exists("comic_panels")
    has_comics = _table_exists("comics")
    with engine.begin() as conn:
        if has_source_documents:
            conn.execute(
                text(
                    "UPDATE source_documents "
                    "SET status = 'failed', "
                    "error = '服务重启导致导入或文风分析中断，请重新提交该任务。' "
                    "WHERE status IN ('queued', 'processing', 'analyzing', 'importing')"
                )
            )
        if has_comic_panels:
            conn.execute(
                text(
                    "UPDATE comic_panels "
                    "SET status = 'failed', "
                    "error = '服务重启导致图片生成中断，请重试这一格。' "
                    "WHERE status IN ('queued', 'rendering')"
                )
            )
        if has_comics:
            conn.execute(
                text(
                    "UPDATE comics "
                    "SET status = 'failed', "
                    "last_error = '服务重启导致漫画生成中断，请重新生成或重试失败分镜。' "
                    "WHERE status IN ('queued', 'storyboarding', 'rendering')"
                )
            )


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
