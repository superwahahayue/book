"""JSON API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.providers.base import ProviderError
from app.providers.registry import get_registry
from app.schemas import (
    ChapterRead,
    ChapterTreeNode,
    ChapterUpdate,
    CharacterCreate,
    CharacterRead,
    CharacterUpdate,
    GenerateChapterRequest,
    NovelCreate,
    NovelDetail,
    NovelSummary,
    NovelUpdate,
    ProviderInfo,
    RegenerateChapterRequest,
    RelationCreate,
    RelationRead,
    RelationUpdate,
    SuggestOptionsRequest,
    SuggestOptionsResponse,
)
from app.services import novel_service
from app.services.generation import GenerationBusyError, manager

router = APIRouter(prefix="/api", tags=["api"])


def _novel_summary(n) -> NovelSummary:
    return NovelSummary(
        id=n.id,
        title=n.title,
        genre=n.genre or "",
        provider=n.provider,
        model=n.model,
        is_generating=bool(n.is_generating),
        last_error=n.last_error,
        chapter_count=len(n.chapters) if n.chapters is not None else 0,
        character_count=len(n.characters) if n.characters is not None else 0,
        created_at=n.created_at,
        updated_at=n.updated_at,
    )


def _novel_detail(n) -> NovelDetail:
    world = n.world_setting or n.settings or ""
    return NovelDetail(
        **_novel_summary(n).model_dump(),
        premise=n.premise or "",
        world_setting=world,
        settings=n.settings or "",
        style=n.style or "",
        outline=n.outline or "",
        characters=[CharacterRead.model_validate(c) for c in (n.characters or [])],
        relations=[RelationRead.model_validate(r) for r in (n.relations or [])],
        chapters=[ChapterRead.model_validate(c) for c in (n.chapters or [])],
    )


def _get_novel_or_404(db: Session, novel_id: int):
    novel = novel_service.get_novel(db, novel_id)
    if novel is None:
        raise HTTPException(status_code=404, detail="小说不存在")
    return novel


def _validate_provider(name: str) -> None:
    try:
        get_registry().get(name)
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/providers", response_model=list[ProviderInfo])
def list_providers() -> list[ProviderInfo]:
    registry = get_registry()
    return [
        ProviderInfo(
            name=p.name,
            label=p.label,
            default_model=p.default_model,
            available=p.available,
            models=list(p.models),
        )
        for p in registry.list_providers()
    ]


@router.get("/novels", response_model=list[NovelSummary])
def list_novels(db: Session = Depends(get_db)):
    return [_novel_summary(n) for n in novel_service.list_novels(db)]


@router.post("/novels", response_model=NovelDetail, status_code=status.HTTP_201_CREATED)
def create_novel(data: NovelCreate, db: Session = Depends(get_db)):
    if data.provider:
        _validate_provider(data.provider)
    novel = novel_service.create_novel(db, data)
    return _novel_detail(novel)


@router.get("/novels/{novel_id}", response_model=NovelDetail)
def get_novel(novel_id: int, db: Session = Depends(get_db)):
    return _novel_detail(_get_novel_or_404(db, novel_id))


@router.patch("/novels/{novel_id}", response_model=NovelDetail)
def update_novel(novel_id: int, data: NovelUpdate, db: Session = Depends(get_db)):
    novel = _get_novel_or_404(db, novel_id)
    if data.provider:
        _validate_provider(data.provider)
    novel = novel_service.update_novel(db, novel, data)
    return _novel_detail(novel)


@router.delete("/novels/{novel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_novel(novel_id: int, db: Session = Depends(get_db)):
    novel = _get_novel_or_404(db, novel_id)
    novel_service.delete_novel(db, novel)


# ── Characters ──────────────────────────────────────────────


@router.get("/novels/{novel_id}/characters", response_model=list[CharacterRead])
def list_characters(novel_id: int, db: Session = Depends(get_db)):
    novel = _get_novel_or_404(db, novel_id)
    return [CharacterRead.model_validate(c) for c in novel.characters]


@router.post(
    "/novels/{novel_id}/characters",
    response_model=CharacterRead,
    status_code=status.HTTP_201_CREATED,
)
def create_character(
    novel_id: int, data: CharacterCreate, db: Session = Depends(get_db)
):
    _get_novel_or_404(db, novel_id)
    char = novel_service.create_character(db, novel_id, data)
    return CharacterRead.model_validate(char)


@router.patch("/characters/{char_id}", response_model=CharacterRead)
def update_character(
    char_id: int, data: CharacterUpdate, db: Session = Depends(get_db)
):
    char = novel_service.get_character(db, char_id)
    if char is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    char = novel_service.update_character(db, char, data)
    return CharacterRead.model_validate(char)


@router.delete("/characters/{char_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_character(char_id: int, db: Session = Depends(get_db)):
    char = novel_service.get_character(db, char_id)
    if char is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    novel_service.delete_character(db, char)


# ── Relations ───────────────────────────────────────────────


@router.get("/novels/{novel_id}/relations", response_model=list[RelationRead])
def list_relations(novel_id: int, db: Session = Depends(get_db)):
    novel = _get_novel_or_404(db, novel_id)
    return [RelationRead.model_validate(r) for r in novel.relations]


@router.post(
    "/novels/{novel_id}/relations",
    response_model=RelationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_relation(
    novel_id: int, data: RelationCreate, db: Session = Depends(get_db)
):
    _get_novel_or_404(db, novel_id)
    try:
        rel = novel_service.create_relation(db, novel_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RelationRead.model_validate(rel)


@router.patch("/relations/{rel_id}", response_model=RelationRead)
def update_relation(rel_id: int, data: RelationUpdate, db: Session = Depends(get_db)):
    rel = novel_service.get_relation(db, rel_id)
    if rel is None:
        raise HTTPException(status_code=404, detail="关系不存在")
    rel = novel_service.update_relation(db, rel, data)
    return RelationRead.model_validate(rel)


@router.delete("/relations/{rel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relation(rel_id: int, db: Session = Depends(get_db)):
    rel = novel_service.get_relation(db, rel_id)
    if rel is None:
        raise HTTPException(status_code=404, detail="关系不存在")
    novel_service.delete_relation(db, rel)


# ── Chapters / Director ─────────────────────────────────────


@router.get("/novels/{novel_id}/chapters/tree", response_model=list[ChapterTreeNode])
def chapter_tree(novel_id: int, db: Session = Depends(get_db)):
    novel = _get_novel_or_404(db, novel_id)
    return novel_service.build_chapter_tree(list(novel.chapters))


@router.get("/chapters/{chapter_id}", response_model=ChapterRead)
def get_chapter(chapter_id: int, db: Session = Depends(get_db)):
    ch = novel_service.get_chapter(db, chapter_id)
    if ch is None:
        raise HTTPException(status_code=404, detail="章节不存在")
    return ChapterRead.model_validate(ch)


@router.patch("/chapters/{chapter_id}", response_model=ChapterRead)
def update_chapter(
    chapter_id: int, data: ChapterUpdate, db: Session = Depends(get_db)
):
    ch = novel_service.get_chapter(db, chapter_id)
    if ch is None:
        raise HTTPException(status_code=404, detail="章节不存在")
    payload = data.model_dump(exclude_unset=True)
    for k, v in payload.items():
        setattr(ch, k, v)
    db.commit()
    db.refresh(ch)
    return ChapterRead.model_validate(ch)


@router.delete("/chapters/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chapter(chapter_id: int, db: Session = Depends(get_db)):
    ch = novel_service.get_chapter(db, chapter_id)
    if ch is None:
        raise HTTPException(status_code=404, detail="章节不存在")
    novel_service.delete_chapter_subtree(db, ch)


@router.post(
    "/novels/{novel_id}/chapters/generate",
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_chapter(
    novel_id: int, data: GenerateChapterRequest, db: Session = Depends(get_db)
):
    novel = _get_novel_or_404(db, novel_id)
    if data.parent_id is None:
        if any(c.parent_id is None for c in novel.chapters):
            raise HTTPException(status_code=400, detail="已有开篇节点,请选择父节点分叉")
    else:
        parent = next((c for c in novel.chapters if c.id == data.parent_id), None)
        if parent is None:
            raise HTTPException(status_code=400, detail="父节点不存在")
    try:
        novel_service.start_generate(novel_id, data.parent_id, data.plot_directive)
    except GenerationBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    # Mark generating early for UI
    novel.is_generating = True
    novel.last_error = None
    db.commit()
    return {"status": "started"}


@router.post(
    "/chapters/{chapter_id}/regenerate",
    status_code=status.HTTP_202_ACCEPTED,
)
def regenerate_chapter(
    chapter_id: int, data: RegenerateChapterRequest, db: Session = Depends(get_db)
):
    ch = novel_service.get_chapter(db, chapter_id)
    if ch is None:
        raise HTTPException(status_code=404, detail="章节不存在")
    novel = _get_novel_or_404(db, ch.novel_id)
    try:
        novel_service.start_regenerate(ch.novel_id, chapter_id, data.plot_directive)
    except GenerationBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    novel.is_generating = True
    novel.last_error = None
    db.commit()
    return {"status": "started"}


@router.post(
    "/novels/{novel_id}/chapters/suggest-options",
    response_model=SuggestOptionsResponse,
)
def suggest_options(
    novel_id: int, data: SuggestOptionsRequest, db: Session = Depends(get_db)
):
    _get_novel_or_404(db, novel_id)
    try:
        options = manager.suggest_options(novel_id, data.node_id)
    except GenerationBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return SuggestOptionsResponse(options=options)
