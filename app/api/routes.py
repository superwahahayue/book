"""JSON API endpoints and server-side authorization."""
from __future__ import annotations

from hashlib import sha256

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
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
from app.models import AuthSession, Comic, ComicPanel, SourceDocument, User
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
    ComicCreate,
    ComicPanelRead,
    ComicRead,
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
    SourceDocumentRead,
    UserRead,
)
from app.services import novel_service
from app.services import comic_service, import_service
from app.services.comic_service import ComicBusyError
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
        style_profile=novel.style_profile or "",
        outline=novel.outline or "",
        characters=[CharacterRead.model_validate(c) for c in (novel.characters or [])],
        relations=[RelationRead.model_validate(r) for r in (novel.relations or [])],
        chapters=[ChapterRead.model_validate(c) for c in (novel.chapters or [])],
    )


def _comic_read(comic: Comic) -> ComicRead:
    return ComicRead(
        id=comic.id,
        novel_id=comic.novel_id,
        source_chapter_id=comic.source_chapter_id,
        title=comic.title,
        visual_style=comic.visual_style,
        image_model=comic.image_model,
        aspect_ratio=comic.aspect_ratio,
        quality=comic.quality,
        panel_count=comic.panel_count,
        status=comic.status,
        last_error=comic.last_error,
        created_at=comic.created_at,
        updated_at=comic.updated_at,
        panels=[
            ComicPanelRead(
                id=panel.id,
                comic_id=panel.comic_id,
                panel_index=panel.panel_index,
                scene_description=panel.scene_description,
                narration=panel.narration,
                dialogue=panel.dialogue,
                image_prompt=panel.image_prompt,
                image_url=(f"/api/comic-panels/{panel.id}/image" if panel.image_path else None),
                status=panel.status,
                error=panel.error,
                created_at=panel.created_at,
                updated_at=panel.updated_at,
            )
            for panel in (comic.panels or [])
        ],
    )


def _get_novel_or_404(db: Session, user: User, novel_id: int):
    return require_novel_access(db, user, novel_service.get_novel(db, novel_id))


def _get_source_document_or_404(db: Session, user: User, document_id: int) -> SourceDocument:
    document = db.get(SourceDocument, document_id)
    if document is None or (not user.is_admin and document.owner_id != user.id):
        raise HTTPException(status_code=404, detail="导入素材不存在。")
    return document


def _get_comic_or_404(db: Session, user: User, comic_id: int) -> Comic:
    comic = comic_service.get_comic(db, comic_id)
    if comic is None:
        raise HTTPException(status_code=404, detail="漫画不存在。")
    _get_novel_or_404(db, user, comic.novel_id)
    return comic


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


@router.post(
    "/imports/novel",
    response_model=SourceDocumentRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def import_novel_file(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    genre: str | None = Form(default=None),
    style: str | None = Form(default=None),
    provider: str | None = Form(default=None),
    model: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if provider:
        _validate_provider(provider)
    from app.config import get_settings

    # This is deliberately a synchronous endpoint. FastAPI runs it in its
    # worker pool, so document decoding/DOCX parsing cannot block the ASGI
    # event loop serving other requests.
    payload = file.file.read(get_settings().upload_max_bytes + 1)
    try:
        document = import_service.create_novel_import(
            db,
            owner_id=user.id,
            filename=file.filename or "导入小说",
            content_type=file.content_type,
            payload=payload,
            title=title,
            genre=genre,
            style=style,
            provider=provider,
            model=model,
        )
    except import_service.SourceImportBusyError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except import_service.SourceImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SourceDocumentRead.model_validate(document)


@router.get("/imports/{document_id}", response_model=SourceDocumentRead)
def get_novel_import(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = _get_source_document_or_404(db, user, document_id)
    if document.kind != "novel_import":
        raise HTTPException(status_code=404, detail="导入小说不存在。")
    return SourceDocumentRead.model_validate(document)


@router.delete("/source-documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source_document(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete retained source prose without deleting a novel already created from it."""
    import_service.delete_source_document(
        db, _get_source_document_or_404(db, user, document_id)
    )


@router.get("/style-references", response_model=list[SourceDocumentRead])
def list_style_references(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    owner_id = None if user.is_admin else user.id
    return [
        SourceDocumentRead.model_validate(document)
        for document in import_service.list_style_references(db, owner_id)
    ]


@router.post(
    "/style-references",
    response_model=SourceDocumentRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def upload_style_reference(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    consent: bool = Form(default=False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not consent:
        raise HTTPException(
            status_code=400,
            detail="请确认你拥有该文本的版权或已获得用于分析的授权。",
        )
    from app.config import get_settings

    # See import_novel_file: keep CPU-heavy parsing off the ASGI event loop.
    payload = file.file.read(get_settings().upload_max_bytes + 1)
    try:
        document = import_service.create_style_reference(
            db,
            owner_id=user.id,
            filename=file.filename or "文风参考",
            content_type=file.content_type,
            payload=payload,
            title=title,
        )
    except import_service.SourceImportBusyError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except import_service.SourceImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SourceDocumentRead.model_validate(document)


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
    style_reference = None
    if data.style_reference_id is not None:
        style_reference = _get_source_document_or_404(db, user, data.style_reference_id)
        if style_reference.kind != "style_reference" or style_reference.status != "ready":
            raise HTTPException(status_code=400, detail="所选文风参考尚未分析完成。")
    return _novel_detail(
        novel_service.create_novel(
            db, data, user.id, style_reference=style_reference
        )
    )


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


@router.post(
    "/novels/{novel_id}/comics",
    response_model=ComicRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_novel_comic(
    novel_id: int,
    data: ComicCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    novel = _get_novel_or_404(db, user, novel_id)
    try:
        comic = comic_service.create_comic(db, novel, data)
    except ComicBusyError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _comic_read(comic)


@router.get("/comics/{comic_id}", response_model=ComicRead)
def get_comic(
    comic_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return _comic_read(_get_comic_or_404(db, user, comic_id))


@router.post("/comic-panels/{panel_id}/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_comic_panel(
    panel_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    panel = comic_service.get_panel(db, panel_id)
    if panel is None:
        raise HTTPException(status_code=404, detail="漫画分镜不存在。")
    _get_comic_or_404(db, user, panel.comic_id)
    try:
        comic_service.manager.retry_panel(panel.id)
    except ComicBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "started"}


@router.get("/comic-panels/{panel_id}/image")
def get_comic_panel_image(
    panel_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    panel = comic_service.get_panel(db, panel_id)
    if panel is None:
        raise HTTPException(status_code=404, detail="漫画分镜不存在。")
    _get_comic_or_404(db, user, panel.comic_id)
    image = comic_service.panel_image_file(panel)
    if image is None:
        raise HTTPException(status_code=404, detail="该分镜图片尚未生成。")
    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".png": "image/png",
    }.get(image.suffix.lower(), "application/octet-stream")
    return FileResponse(image, media_type=media_type)


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
