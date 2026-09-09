"""ORM models: Novel, Character, Relation, Chapter (story tree)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Novel(Base):
    __tablename__ = "novels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(255))
    genre: Mapped[str] = mapped_column(String(255), default="")
    premise: Mapped[str] = mapped_column(Text, default="")
    # Legacy free-text settings column; prefer world_setting for new code.
    settings: Mapped[str] = mapped_column(Text, default="")
    world_setting: Mapped[str] = mapped_column(Text, default="")
    style: Mapped[str] = mapped_column(String(255), default="")

    outline: Mapped[str] = mapped_column(Text, default="")
    # Deprecated: path summaries are built from chapter nodes.
    running_summary: Mapped[str] = mapped_column(Text, default="")
    # A copied, high-level profile derived from an optional source document.
    # It intentionally stores analysis rather than raw reference prose.
    style_profile: Mapped[str] = mapped_column(Text, default="")

    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Deprecated auto-continue fields (ignored by app logic).
    auto_continue: Mapped[bool] = mapped_column(default=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=360)

    is_generating: Mapped[bool] = mapped_column(default=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="novel",
        cascade="all, delete-orphan",
        order_by="Chapter.id",
    )
    characters: Mapped[list["Character"]] = relationship(
        back_populates="novel",
        cascade="all, delete-orphan",
        order_by="Character.sort_order, Character.id",
    )
    relations: Mapped[list["Relation"]] = relationship(
        back_populates="novel",
        cascade="all, delete-orphan",
        order_by="Relation.id",
    )
    source_references: Mapped[list["NovelSourceReference"]] = relationship(
        back_populates="novel",
        cascade="all, delete-orphan",
        order_by="NovelSourceReference.id",
    )
    comics: Mapped[list["Comic"]] = relationship(
        back_populates="novel",
        cascade="all, delete-orphan",
        order_by="Comic.created_at.desc()",
    )
    owner: Mapped["User | None"] = relationship(back_populates="novels")

    @property
    def chapter_count(self) -> int:
        return len(self.chapters)

    @property
    def effective_world(self) -> str:
        return (self.world_setting or self.settings or "").strip()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    novels: Mapped[list[Novel]] = relationship(back_populates="owner")
    source_documents: Mapped[list["SourceDocument"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["AuthSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped[User] = relationship(back_populates="sessions")


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    alias: Mapped[str] = mapped_column(String(128), default="")
    role_title: Mapped[str] = mapped_column(String(128), default="")
    personality: Mapped[str] = mapped_column(Text, default="")
    appearance: Mapped[str] = mapped_column(Text, default="")
    background: Mapped[str] = mapped_column(Text, default="")
    speech_style: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    novel: Mapped["Novel"] = relationship(back_populates="characters")


class Relation(Base):
    __tablename__ = "relations"
    __table_args__ = (
        UniqueConstraint(
            "from_character_id",
            "to_character_id",
            "relation_type",
            name="uq_relation_pair_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), index=True
    )
    from_character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), index=True
    )
    to_character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), index=True
    )
    relation_type: Mapped[str] = mapped_column(String(64), default="")
    description: Mapped[str] = mapped_column(Text, default="")

    novel: Mapped["Novel"] = relationship(back_populates="relations")


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        default=None,
    )
    # Legacy linear order; kept for migration / display fallback.
    index: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    plot_directive: Mapped[str] = mapped_column(Text, default="")
    # The default continuation among a chapter's children. Alternative siblings
    # remain available as branches.
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    is_ending: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    novel: Mapped["Novel"] = relationship(back_populates="chapters")
    parent: Mapped["Chapter | None"] = relationship(
        remote_side="Chapter.id",
        back_populates="children",
        foreign_keys=[parent_id],
    )
    children: Mapped[list["Chapter"]] = relationship(
        back_populates="parent",
        foreign_keys=[parent_id],
    )


class SourceDocument(Base):
    """A user-owned imported text plus its derived, bounded AI profiles."""

    __tablename__ = "source_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    original_filename: Mapped[str] = mapped_column(String(512), default="")
    mime_type: Mapped[str] = mapped_column(String(255), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    content_sha256: Mapped[str] = mapped_column(String(64), default="")
    # Normalized source text is retained so the user can reuse the document for
    # continuation, style analysis, and later comic work without re-uploading.
    content: Mapped[str] = mapped_column(Text, default="")
    options_json: Mapped[str] = mapped_column(Text, default="{}")
    story_profile: Mapped[str] = mapped_column(Text, default="")
    style_profile: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="processing", index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_novel_id: Mapped[int | None] = mapped_column(
        ForeignKey("novels.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    owner: Mapped["User"] = relationship(back_populates="source_documents")
    references: Mapped[list["NovelSourceReference"]] = relationship(
        back_populates="source_document", cascade="all, delete-orphan"
    )


class NovelSourceReference(Base):
    """Describes how a reusable source document is used by a novel."""

    __tablename__ = "novel_source_references"
    __table_args__ = (
        UniqueConstraint(
            "novel_id", "source_document_id", "usage", name="uq_novel_source_usage"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), index=True
    )
    source_document_id: Mapped[int] = mapped_column(
        ForeignKey("source_documents.id", ondelete="CASCADE"), index=True
    )
    usage: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    novel: Mapped["Novel"] = relationship(back_populates="source_references")
    source_document: Mapped["SourceDocument"] = relationship(back_populates="references")


class Comic(Base):
    """A background comic generation job for one chapter of a novel."""

    __tablename__ = "comics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), index=True
    )
    source_chapter_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), default="")
    visual_style: Mapped[str] = mapped_column(Text, default="")
    image_model: Mapped[str] = mapped_column(String(128), default="")
    aspect_ratio: Mapped[str] = mapped_column(String(32), default="16:9")
    quality: Mapped[str] = mapped_column(String(32), default="standard")
    panel_count: Mapped[int] = mapped_column(Integer, default=6)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    novel: Mapped["Novel"] = relationship(back_populates="comics")
    panels: Mapped[list["ComicPanel"]] = relationship(
        back_populates="comic",
        cascade="all, delete-orphan",
        order_by="ComicPanel.panel_index",
    )


class ComicPanel(Base):
    """One storyboard panel and, once ready, its durable generated image."""

    __tablename__ = "comic_panels"
    __table_args__ = (
        UniqueConstraint("comic_id", "panel_index", name="uq_comic_panel_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comic_id: Mapped[int] = mapped_column(
        ForeignKey("comics.id", ondelete="CASCADE"), index=True
    )
    panel_index: Mapped[int] = mapped_column(Integer)
    scene_description: Mapped[str] = mapped_column(Text, default="")
    narration: Mapped[str] = mapped_column(Text, default="")
    dialogue: Mapped[str] = mapped_column(Text, default="")
    image_prompt: Mapped[str] = mapped_column(Text, default="")
    image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    comic: Mapped["Comic"] = relationship(back_populates="panels")
