"""Novel / character / relation / chapter CRUD and generation orchestration."""
from __future__ import annotations

import logging
import threading

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Chapter, Character, Novel, Relation
from app.schemas import (
    CharacterCreate,
    CharacterSeed,
    CharacterUpdate,
    NovelCreate,
    NovelUpdate,
    RelationCreate,
    RelationUpdate,
)
from app.services.generation import GenerationBusyError, manager

logger = logging.getLogger(__name__)


def _run_in_thread(target, *args) -> None:
    threading.Thread(target=target, args=args, daemon=True).start()


def _novel_query():
    return select(Novel).options(
        selectinload(Novel.characters),
        selectinload(Novel.relations),
        selectinload(Novel.chapters),
    )


def list_novels(db: Session, owner_id: int | None = None) -> list[Novel]:
    query = (
        select(Novel)
        .options(selectinload(Novel.characters), selectinload(Novel.chapters))
        .order_by(Novel.updated_at.desc())
    )
    if owner_id is not None:
        query = query.where(Novel.owner_id == owner_id)
    return list(db.scalars(query))


def get_novel(db: Session, novel_id: int) -> Novel | None:
    return db.scalars(_novel_query().where(Novel.id == novel_id)).first()


def create_novel(db: Session, data: NovelCreate, owner_id: int) -> Novel:
    world = data.world_setting or data.settings or ""
    novel = Novel(
        owner_id=owner_id,
        title=data.title,
        genre=data.genre,
        premise=data.premise,
        settings=data.settings or world,
        world_setting=world,
        style=data.style,
        outline=data.outline,
        provider=data.provider,
        model=data.model,
        auto_continue=False,
        is_generating=False,
    )
    db.add(novel)
    db.flush()

    for i, seed in enumerate(data.characters or []):
        db.add(_character_from_seed(novel.id, seed, i))

    db.commit()
    return get_novel(db, novel.id)  # type: ignore[return-value]


def _character_from_seed(novel_id: int, seed: CharacterSeed, order: int) -> Character:
    return Character(
        novel_id=novel_id,
        name=seed.name,
        alias=seed.alias,
        role_title=seed.role_title,
        personality=seed.personality,
        appearance=seed.appearance,
        background=seed.background,
        speech_style=seed.speech_style,
        notes=seed.notes,
        sort_order=order,
    )


def update_novel(db: Session, novel: Novel, data: NovelUpdate) -> Novel:
    payload = data.model_dump(exclude_unset=True)
    if "world_setting" in payload and payload["world_setting"] is not None:
        novel.world_setting = payload["world_setting"]
        if "settings" not in payload:
            novel.settings = payload["world_setting"]
    if "settings" in payload and payload["settings"] is not None:
        novel.settings = payload["settings"]
        if "world_setting" not in payload:
            novel.world_setting = payload["settings"]
    for field in (
        "title",
        "genre",
        "premise",
        "style",
        "outline",
        "provider",
        "model",
    ):
        if field in payload and payload[field] is not None:
            setattr(novel, field, payload[field])
    db.commit()
    return get_novel(db, novel.id)  # type: ignore[return-value]


def delete_novel(db: Session, novel: Novel) -> None:
    db.delete(novel)
    db.commit()


# ── Characters ──────────────────────────────────────────────


def create_character(db: Session, novel_id: int, data: CharacterCreate) -> Character:
    char = Character(novel_id=novel_id, **data.model_dump())
    db.add(char)
    db.commit()
    db.refresh(char)
    return char


def update_character(db: Session, char: Character, data: CharacterUpdate) -> Character:
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(char, k, v)
    db.commit()
    db.refresh(char)
    return char


def delete_character(db: Session, char: Character) -> None:
    # Relations cascade via FK if configured; also clean explicitly for SQLite.
    db.execute(
        Relation.__table__.delete().where(
            (Relation.from_character_id == char.id)
            | (Relation.to_character_id == char.id)
        )
    )
    db.delete(char)
    db.commit()


def get_character(db: Session, char_id: int) -> Character | None:
    return db.get(Character, char_id)


# ── Relations ───────────────────────────────────────────────


def create_relation(db: Session, novel_id: int, data: RelationCreate) -> Relation:
    if data.from_character_id == data.to_character_id:
        raise ValueError("不能与自己建立关系")
    chars = list(
        db.scalars(
            select(Character).where(
                Character.novel_id == novel_id,
                Character.id.in_([data.from_character_id, data.to_character_id]),
            )
        )
    )
    if len(chars) != 2:
        raise ValueError("角色不存在或不属于该小说")
    rel = Relation(novel_id=novel_id, **data.model_dump())
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return rel


def update_relation(db: Session, rel: Relation, data: RelationUpdate) -> Relation:
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(rel, k, v)
    db.commit()
    db.refresh(rel)
    return rel


def delete_relation(db: Session, rel: Relation) -> None:
    db.delete(rel)
    db.commit()


def get_relation(db: Session, rel_id: int) -> Relation | None:
    return db.get(Relation, rel_id)


# ── Chapters ────────────────────────────────────────────────


def get_chapter(db: Session, chapter_id: int) -> Chapter | None:
    return db.get(Chapter, chapter_id)


def update_chapter(db: Session, chapter: Chapter, **fields) -> Chapter:
    for k, v in fields.items():
        if v is not None or k in ("title", "content", "plot_directive"):
            if k in fields:
                setattr(chapter, k, fields[k])
    db.commit()
    db.refresh(chapter)
    return chapter


def delete_chapter_subtree(db: Session, chapter: Chapter) -> None:
    """Delete chapter and all descendants (DB cascade on parent_id)."""
    db.delete(chapter)
    db.commit()


def build_chapter_tree(chapters: list[Chapter]) -> list[dict]:
    """Return list of root tree nodes as nested dicts."""
    nodes: dict[int, dict] = {}
    for c in chapters:
        nodes[c.id] = {
            "id": c.id,
            "parent_id": c.parent_id,
            "index": c.index,
            "title": c.title,
            "plot_directive": c.plot_directive or "",
            "is_primary": bool(c.is_primary),
            "is_ending": bool(c.is_ending),
            "summary": c.summary or "",
            "created_at": c.created_at,
            "children": [],
        }
    roots: list[dict] = []
    for c in chapters:
        node = nodes[c.id]
        if c.parent_id and c.parent_id in nodes:
            nodes[c.parent_id]["children"].append(node)
        else:
            roots.append(node)
    sort_key = lambda item: (not item["is_primary"], item["index"], item["id"])
    for node in nodes.values():
        node["children"].sort(key=sort_key)
    roots.sort(key=lambda item: item["id"])
    return roots


def set_primary_chapter(db: Session, chapter: Chapter) -> Chapter:
    """Select one child as its parent's default continuation."""
    if chapter.parent_id is None:
        raise ValueError("开篇章节不能设为下一章。")

    db.query(Chapter).filter(Chapter.parent_id == chapter.parent_id).update(
        {Chapter.is_primary: False}, synchronize_session=False
    )
    chapter.is_primary = True
    db.commit()
    db.refresh(chapter)
    return chapter


def start_generate(novel_id: int, parent_id: int | None, plot_directive: str) -> None:
    if manager.is_busy(novel_id):
        raise GenerationBusyError(f"小说 {novel_id} 正在生成中。")
    # Pre-validate quickly on a short path — full validation in worker.
    _run_in_thread(_generate_safe, novel_id, parent_id, plot_directive)


def _generate_safe(novel_id: int, parent_id: int | None, plot_directive: str) -> None:
    try:
        manager.generate_chapter(novel_id, parent_id, plot_directive)
    except GenerationBusyError:
        pass
    except Exception:
        logger.exception("Generation failed for novel %s", novel_id)


def start_regenerate(novel_id: int, chapter_id: int, plot_directive: str) -> None:
    if manager.is_busy(novel_id):
        raise GenerationBusyError(f"小说 {novel_id} 正在生成中。")
    _run_in_thread(_regenerate_safe, novel_id, chapter_id, plot_directive)


def _regenerate_safe(novel_id: int, chapter_id: int, plot_directive: str) -> None:
    try:
        manager.regenerate_chapter(novel_id, chapter_id, plot_directive)
    except GenerationBusyError:
        pass
    except Exception:
        logger.exception("Regenerate failed for novel %s chapter %s", novel_id, chapter_id)
