"""Pydantic request/response models."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuthCredentials(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=255)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    is_admin: bool


# ── Characters ──────────────────────────────────────────────


class CharacterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    alias: str = ""
    role_title: str = ""
    personality: str = ""
    appearance: str = ""
    background: str = ""
    speech_style: str = ""
    notes: str = ""
    sort_order: int = 0


class CharacterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    alias: str | None = None
    role_title: str | None = None
    personality: str | None = None
    appearance: str | None = None
    background: str | None = None
    speech_style: str | None = None
    notes: str | None = None
    sort_order: int | None = None


class CharacterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    novel_id: int
    name: str
    alias: str
    role_title: str
    personality: str
    appearance: str
    background: str
    speech_style: str
    notes: str
    sort_order: int
    created_at: datetime


# ── Relations ───────────────────────────────────────────────


class RelationCreate(BaseModel):
    from_character_id: int
    to_character_id: int
    relation_type: str = ""
    description: str = ""


class RelationUpdate(BaseModel):
    from_character_id: int | None = None
    to_character_id: int | None = None
    relation_type: str | None = None
    description: str | None = None


class RelationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    novel_id: int
    from_character_id: int
    to_character_id: int
    relation_type: str
    description: str


# ── Chapters ────────────────────────────────────────────────


class ChapterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    novel_id: int
    parent_id: int | None
    index: int
    title: str | None
    content: str
    summary: str
    plot_directive: str
    is_ending: bool
    created_at: datetime


class ChapterTreeNode(BaseModel):
    id: int
    parent_id: int | None
    title: str | None
    plot_directive: str
    is_ending: bool
    summary: str
    created_at: datetime
    children: list["ChapterTreeNode"] = Field(default_factory=list)


class ChapterUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    is_ending: bool | None = None
    plot_directive: str | None = None


class GenerateChapterRequest(BaseModel):
    parent_id: int | None = None
    plot_directive: str = Field(min_length=1, max_length=4000)


class RegenerateChapterRequest(BaseModel):
    plot_directive: str = Field(min_length=1, max_length=4000)


class SuggestOptionsRequest(BaseModel):
    node_id: int | None = None


class SuggestOptionsResponse(BaseModel):
    options: list[str]


# ── Novels ──────────────────────────────────────────────────


class CharacterSeed(BaseModel):
    """Optional character created with a new novel."""

    name: str = Field(min_length=1, max_length=128)
    alias: str = ""
    role_title: str = ""
    personality: str = ""
    appearance: str = ""
    background: str = ""
    speech_style: str = ""
    notes: str = ""


class NovelCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    genre: str = ""
    premise: str = ""
    world_setting: str = ""
    # Back-compat alias
    settings: str = ""
    style: str = ""
    outline: str = ""
    provider: str | None = None
    model: str | None = None
    characters: list[CharacterSeed] = Field(default_factory=list)


class NovelUpdate(BaseModel):
    title: str | None = None
    genre: str | None = None
    premise: str | None = None
    world_setting: str | None = None
    settings: str | None = None
    style: str | None = None
    outline: str | None = None
    provider: str | None = None
    model: str | None = None


class NovelSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    genre: str
    provider: str | None
    model: str | None
    is_generating: bool
    last_error: str | None
    chapter_count: int
    character_count: int = 0
    created_at: datetime
    updated_at: datetime


class NovelDetail(NovelSummary):
    premise: str
    world_setting: str
    settings: str
    style: str
    outline: str
    characters: list[CharacterRead] = Field(default_factory=list)
    relations: list[RelationRead] = Field(default_factory=list)
    chapters: list[ChapterRead] = Field(default_factory=list)


class ProviderInfo(BaseModel):
    name: str
    label: str
    default_model: str
    available: bool
    models: list[str] = Field(default_factory=list)
