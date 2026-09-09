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
    is_primary: bool
    is_ending: bool
    created_at: datetime


class ChapterTreeNode(BaseModel):
    id: int
    parent_id: int | None
    title: str | None
    plot_directive: str
    is_primary: bool
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
    style_reference_id: int | None = None
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
    style_profile: str = ""
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


# ── Imported source documents ──────────────────────────────


class SourceDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    title: str
    original_filename: str
    mime_type: str
    size_bytes: int
    status: str
    error: str | None
    story_profile: str
    style_profile: str
    result_novel_id: int | None
    created_at: datetime
    updated_at: datetime


# ── Comics ─────────────────────────────────────────────────


class ComicCreate(BaseModel):
    chapter_id: int
    visual_style: str = "彩色日漫风，电影感分镜，角色形象保持一致"
    image_model: str | None = None
    aspect_ratio: str | None = None
    quality: str | None = None
    panel_count: int | None = Field(default=None, ge=4, le=8)


class ComicPanelRead(BaseModel):
    id: int
    comic_id: int
    panel_index: int
    scene_description: str
    narration: str
    dialogue: str
    image_prompt: str
    image_url: str | None = None
    status: str
    error: str | None
    created_at: datetime
    updated_at: datetime


class ComicRead(BaseModel):
    id: int
    novel_id: int
    source_chapter_id: int | None
    title: str
    visual_style: str
    image_model: str
    aspect_ratio: str
    quality: str
    panel_count: int
    status: str
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    panels: list[ComicPanelRead] = Field(default_factory=list)
