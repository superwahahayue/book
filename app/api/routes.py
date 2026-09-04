"""JSON API endpoints and server-side authorization."""
from __future__ import annotations

from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    SESSION_COOKIE,
    claim_legacy_novels,
    clear_session_cookie,
    create_session,
    get_current_user,
    hash_password,
    invalid_credentials,
    normalize_email,
    require_novel_access,
    set_session_cookie,
    sync_admin_role,
    verify_password,
)
from app.db import get_db
from app.models import AuthSession, User
from app.providers.base import ProviderError
from app.providers.registry import get_registry
from app.schemas import (
    AuthCredentials,
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
    UserRead,
)
from app.services import novel_service
from app.services.generation import GenerationBusyError, manager

router = APIRouter(prefix="/api", tags=["api"])


def _novel_summary(novel) -> NovelSummary:
    return NovelSummary(
        id=novel.id,
        title=novel.title,
        genre=novel.genre or "",
        provider=novel.provider,
        model=novel.model,
        is_generating=bool(novel.is_generating),
        last_error=novel.last_error,
        chapter_count=len(novel.chapters) if novel.chapters is not None else 0,
        character_count=len(novel.characters) if novel.characters is not None else 0,
        created_at=novel.created_at,
        updated_at=novel.updated_at,
    )


def _novel_detail(novel) -> NovelDetail:
    world = novel.world_setting or novel.settings or ""
    return NovelDetail(
        **_novel_summary(novel).model_dump(),
        premise=novel.premise or "",
        world_setting=world,
        settings=novel.settings or "",
        style=novel.style or "",
        outline=novel.outline or "",
        characters=[CharacterRead.model_validate(c) for c in (novel.characters or [])],
        relations=[RelationRead.model_validate(r) for r in (novel.relations or [])],
        chapters=[ChapterRead.model_validate(c) for c in (novel.chapters or [])],
    )


def _get_novel_or_404(db: Session, user: User, novel_id: int):
    return require_novel_access(db, user, novel_service.get_novel(db, novel_id))


def _get_character_or_404(db: Session, user: User, char_id: int):
    character = novel_service.get_character(db, char_id)
    if character is None:
        raise HTTPException(status_code=404, detail="角色不存在。")
    _get_novel_or_404(db, user, character.novel_id)
    return character


def _get_relation_or_404(db: Session, user: User, rel_id: int):
    relation = novel_service.get_relation(db, rel_id)
    if relation is None:
        raise HTTPException(status_code=404, detail="关系不存在。")
    _get_novel_or_404(db, user, relation.novel_id)
    return relation


def _get_chapter_or_404(db: Session, user: User, chapter_id: int):
    chapter = novel_service.get_chapter(db, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail="章节不存在。")
    _get_novel_or_404(db, user, chapter.novel_id)
    return chapter


def _validate_provider(name: str) -> None:
    try:
        get_registry().get(name)
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(data: AuthCredentials, response: Response, db: Session = Depends(get_db)):
    email = normalize_email(data.email)
    if db.scalars(select(User).where(User.email == email)).first() is not None:
        raise HTTPException(status_code=409, detail="该邮箱已注册。")
    user = User(email=email, password_hash=hash_password(data.password))
    db.add(user)
    db.flush()
    sync_admin_role(db, user)
    claim_legacy_novels(db, user)
    token = create_session(db, user)
    db.commit()
    db.refresh(user)
    set_session_cookie(response, token)
    return user


@router.post("/auth/login", response_model=UserRead)
def login(data: AuthCredentials, response: Response, db: Session = Depends(get_db)):
    email = normalize_email(data.email)
    user = db.scalars(select(User).where(User.email == email)).first()
    if user is None:
        invalid_credentials(db, data.password)
    if not verify_password(data.password, user.password_hash):
        invalid_credentials(db, data.password)
    sync_admin_role(db, user)
    claim_legacy_novels(db, user)
    token = create_session(db, user)
    db.commit()
    db.refresh(user)
    set_session_cookie(response, token)
    return user


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db.query(AuthSession).filter(
            AuthSession.token_hash == sha256(token.encode()).hexdigest()
        ).delete()
        db.commit()
    clear_session_cookie(response)


@router.get("/auth/me", response_model=UserRead)
def current_user(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.commit()
    return user


@router.get("/providers", response_model=list[ProviderInfo])
def list_providers() -> list[ProviderInfo]:
    registry = get_registry()
    return [
        ProviderInfo(
            name=provider.name,
            label=provider.label,
            default_model=provider.default_model,
            available=provider.available,
            models=list(provider.models),
        )
        for provider in registry.list_providers()
    ]


@router.get("/novels", response_model=list[NovelSummary])
def list_novels(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owner_id = None if user.is_admin else user.id
    return [_novel_summary(novel) for novel in novel_service.list_novels(db, owner_id)]


@router.post("/novels", response_model=NovelDetail, status_code=status.HTTP_201_CREATED)
def create_novel(
    data: NovelCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if data.provider:
        _validate_provider(data.provider)
    return _novel_detail(novel_service.create_novel(db, data, user.id))


@router.get("/novels/{novel_id}", response_model=NovelDetail)
def get_novel(
    novel_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return _novel_detail(_get_novel_or_404(db, user, novel_id))


@router.patch("/novels/{novel_id}", response_model=NovelDetail)
def update_novel(
    novel_id: int,
    data: NovelUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    novel = _get_novel_or_404(db, user, novel_id)
    if data.provider:
        _validate_provider(data.provider)
    return _novel_detail(novel_service.update_novel(db, novel, data))


@router.delete("/novels/{novel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_novel(
    novel_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    novel_service.delete_novel(db, _get_novel_or_404(db, user, novel_id))


@router.get("/novels/{novel_id}/characters", response_model=list[CharacterRead])
def list_characters(
    novel_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    novel = _get_novel_or_404(db, user, novel_id)
    return [CharacterRead.model_validate(character) for character in novel.characters]


@router.post(
    "/novels/{novel_id}/characters",
    response_model=CharacterRead,
    status_code=status.HTTP_201_CREATED,
)
def create_character(
    novel_id: int,
    data: CharacterCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_novel_or_404(db, user, novel_id)
    return CharacterRead.model_validate(novel_service.create_character(db, novel_id, data))


@router.patch("/characters/{char_id}", response_model=CharacterRead)
def update_character(
    char_id: int,
    data: CharacterUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return CharacterRead.model_validate(
        novel_service.update_character(db, _get_character_or_404(db, user, char_id), data)
    )


@router.delete("/characters/{char_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_character(
    char_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    novel_service.delete_character(db, _get_character_or_404(db, user, char_id))


@router.get("/novels/{novel_id}/relations", response_model=list[RelationRead])
def list_relations(
    novel_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    novel = _get_novel_or_404(db, user, novel_id)
    return [RelationRead.model_validate(relation) for relation in novel.relations]


@router.post(
    "/novels/{novel_id}/relations",
    response_model=RelationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_relation(
    novel_id: int,
    data: RelationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_novel_or_404(db, user, novel_id)
    try:
        relation = novel_service.create_relation(db, novel_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RelationRead.model_validate(relation)


@router.patch("/relations/{rel_id}", response_model=RelationRead)
def update_relation(
    rel_id: int,
    data: RelationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return RelationRead.model_validate(
        novel_service.update_relation(db, _get_relation_or_404(db, user, rel_id), data)
    )


@router.delete("/relations/{rel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relation(
    rel_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    novel_service.delete_relation(db, _get_relation_or_404(db, user, rel_id))


@router.get("/novels/{novel_id}/chapters/tree", response_model=list[ChapterTreeNode])
def chapter_tree(
    novel_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    novel = _get_novel_or_404(db, user, novel_id)
    return novel_service.build_chapter_tree(list(novel.chapters))


@router.get("/chapters/{chapter_id}", response_model=ChapterRead)
def get_chapter(
    chapter_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return ChapterRead.model_validate(_get_chapter_or_404(db, user, chapter_id))


@router.patch("/chapters/{chapter_id}", response_model=ChapterRead)
def update_chapter(
    chapter_id: int,
    data: ChapterUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chapter = _get_chapter_or_404(db, user, chapter_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(chapter, field, value)
    db.commit()
    db.refresh(chapter)
    return ChapterRead.model_validate(chapter)


@router.post("/chapters/{chapter_id}/set-primary", response_model=ChapterRead)
def set_primary_chapter(
    chapter_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chapter = _get_chapter_or_404(db, user, chapter_id)
    try:
        return ChapterRead.model_validate(novel_service.set_primary_chapter(db, chapter))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/chapters/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chapter(
    chapter_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    novel_service.delete_chapter_subtree(db, _get_chapter_or_404(db, user, chapter_id))


@router.post("/novels/{novel_id}/chapters/generate", status_code=status.HTTP_202_ACCEPTED)
def generate_chapter(
    novel_id: int,
    data: GenerateChapterRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    novel = _get_novel_or_404(db, user, novel_id)
    if data.parent_id is None:
        if any(chapter.parent_id is None for chapter in novel.chapters):
            raise HTTPException(status_code=400, detail="请先选择父章节以创建分支。")
    elif not any(chapter.id == data.parent_id for chapter in novel.chapters):
        raise HTTPException(status_code=400, detail="父章节不存在。")
    try:
        novel_service.start_generate(novel_id, data.parent_id, data.plot_directive)
    except GenerationBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    novel.is_generating = True
    novel.last_error = None
    db.commit()
    return {"status": "started"}


@router.post("/chapters/{chapter_id}/regenerate", status_code=status.HTTP_202_ACCEPTED)
def regenerate_chapter(
    chapter_id: int,
    data: RegenerateChapterRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chapter = _get_chapter_or_404(db, user, chapter_id)
    try:
        novel_service.start_regenerate(chapter.novel_id, chapter_id, data.plot_directive)
    except GenerationBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    novel = _get_novel_or_404(db, user, chapter.novel_id)
    novel.is_generating = True
    novel.last_error = None
    db.commit()
    return {"status": "started"}


@router.post(
    "/novels/{novel_id}/chapters/suggest-options",
    response_model=SuggestOptionsResponse,
)
def suggest_options(
    novel_id: int,
    data: SuggestOptionsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    novel = _get_novel_or_404(db, user, novel_id)
    if data.node_id is not None:
        chapter = _get_chapter_or_404(db, user, data.node_id)
        if chapter.novel_id != novel.id:
            raise HTTPException(status_code=400, detail="章节不属于当前小说。")
    try:
        options = manager.suggest_options(novel_id, data.node_id)
    except GenerationBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return SuggestOptionsResponse(options=options)
