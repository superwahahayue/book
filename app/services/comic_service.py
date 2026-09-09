"""Background storyboard and panel-image generation for imported/original novels."""
from __future__ import annotations

import json
import logging
from pathlib import Path
import shutil
import threading

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import prompts
from app.config import get_settings
from app.db import session_scope
from app.models import Chapter, Comic, ComicPanel, Novel
from app.providers.antigravity_image_provider import AntigravityImageProvider
from app.providers.base import ProviderError
from app.providers.registry import get_registry
from app.schemas import ComicCreate

logger = logging.getLogger(__name__)


class ComicBusyError(RuntimeError):
    """Raised when a comic already has an active storyboard/image worker."""


class ComicManager:
    def __init__(self) -> None:
        self._locks: dict[int, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._worker_slots = threading.BoundedSemaphore(
            max(1, get_settings().comic_max_concurrent_jobs)
        )

    def _lock_for(self, comic_id: int) -> threading.Lock:
        with self._locks_guard:
            lock = self._locks.get(comic_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[comic_id] = lock
            return lock

    def start(self, comic_id: int) -> None:
        lock = self._lock_for(comic_id)
        if not lock.acquire(blocking=False):
            raise ComicBusyError("该漫画正在生成中。")
        if not self._worker_slots.acquire(blocking=False):
            lock.release()
            raise ComicBusyError("漫画生成队列已满，请等待当前任务完成后再试。")
        threading.Thread(
            target=self._generate_comic_safe, args=(comic_id, lock), daemon=True
        ).start()

    def retry_panel(self, panel_id: int) -> None:
        with session_scope() as db:
            panel = db.get(ComicPanel, panel_id)
            if panel is None:
                raise ValueError("漫画分镜不存在。")
            comic_id = panel.comic_id
        lock = self._lock_for(comic_id)
        if not lock.acquire(blocking=False):
            raise ComicBusyError("该漫画正在生成中。")
        if not self._worker_slots.acquire(blocking=False):
            lock.release()
            raise ComicBusyError("漫画生成队列已满，请等待当前任务完成后再试。")
        threading.Thread(
            target=self._retry_panel_safe, args=(panel_id, lock), daemon=True
        ).start()

    def _generate_comic_safe(self, comic_id: int, lock: threading.Lock) -> None:
        try:
            self._generate_comic(comic_id)
        except Exception as exc:
            logger.exception("Comic generation failed for %s", comic_id)
            _set_comic_error(comic_id, str(exc))
        finally:
            lock.release()
            self._worker_slots.release()

    def _retry_panel_safe(self, panel_id: int, lock: threading.Lock) -> None:
        try:
            self._retry_panel(panel_id)
        except Exception as exc:
            logger.exception("Comic panel retry failed for %s", panel_id)
            comic_id = _set_panel_error(panel_id, str(exc))
            # A failure before _retry_panel reaches its final refresh used to
            # leave the parent job stuck in "rendering".  Keep the aggregate
            # job state truthful even when the retry itself raises.
            if comic_id is not None:
                _refresh_comic_status(comic_id)
        finally:
            lock.release()
            self._worker_slots.release()

    def _generate_comic(self, comic_id: int) -> None:
        settings = get_settings()
        with session_scope() as db:
            comic = db.get(Comic, comic_id)
            if comic is None:
                return
            novel = db.scalars(
                select(Novel)
                .where(Novel.id == comic.novel_id)
                .options(selectinload(Novel.characters))
            ).first()
            chapter = db.get(Chapter, comic.source_chapter_id)
            if novel is None or chapter is None or chapter.novel_id != comic.novel_id:
                raise ValueError("漫画来源章节不存在或不属于当前小说。")
            comic.status = "storyboarding"
            comic.last_error = None
            prompt = prompts.build_comic_storyboard_prompt(
                novel,
                chapter,
                list(novel.characters),
                comic.visual_style,
                comic.panel_count,
            )
            provider = get_registry().get(novel.provider)
            model = novel.model
            expected_panel_count = comic.panel_count

        raw = provider.generate(
            prompt,
            model=model,
            system=prompts.SYSTEM_PROMPT,
            temperature=min(0.8, settings.temperature),
            timeout=settings.request_timeout,
        )
        title, panel_specs = _parse_storyboard(raw, expected_count=expected_panel_count)

        # The expected count is stored per job, so read it after the slow model call.
        with session_scope() as db:
            comic = db.get(Comic, comic_id)
            if comic is None:
                return
            if len(panel_specs) != comic.panel_count:
                raise ValueError(
                    f"分镜数量不正确：期望 {comic.panel_count} 格，模型返回 {len(panel_specs)} 格。"
                )
            comic.title = title[:255] or comic.title
            comic.status = "rendering"
            comic.last_error = None
            for panel_index, spec in enumerate(panel_specs, start=1):
                db.add(
                    ComicPanel(
                        comic_id=comic.id,
                        panel_index=panel_index,
                        scene_description=spec["scene_description"],
                        narration=spec["narration"],
                        dialogue=spec["dialogue"],
                        image_prompt=spec["image_prompt"],
                        status="queued",
                    )
                )

        with session_scope() as db:
            panel_ids = list(
                db.scalars(
                    select(ComicPanel.id)
                    .where(ComicPanel.comic_id == comic_id)
                    .order_by(ComicPanel.panel_index)
                )
            )
        for panel_id in panel_ids:
            self._render_panel(panel_id)
        _refresh_comic_status(comic_id)

    def _retry_panel(self, panel_id: int) -> None:
        with session_scope() as db:
            panel = db.get(ComicPanel, panel_id)
            if panel is None:
                raise ValueError("漫画分镜不存在。")
            comic = db.get(Comic, panel.comic_id)
            if comic is None:
                raise ValueError("漫画不存在。")
            comic_id = comic.id
            comic.status = "rendering"
            comic.last_error = None
            panel.status = "queued"
            panel.error = None
        self._render_panel(panel_id)
        _refresh_comic_status(comic_id)

    def _render_panel(self, panel_id: int) -> None:
        settings = get_settings()
        with session_scope() as db:
            panel = db.get(ComicPanel, panel_id)
            if panel is None:
                return
            comic = db.get(Comic, panel.comic_id)
            if comic is None:
                return
            panel.status = "rendering"
            panel.error = None
            prompt = panel.image_prompt
            image_model = comic.image_model
            aspect_ratio = comic.aspect_ratio
            quality = comic.quality
            comic_id = comic.id

        image_provider = AntigravityImageProvider(
            get_settings().gemini_base_url, get_settings().gemini_api_key
        )
        try:
            image = image_provider.generate(
                prompt,
                model=image_model,
                size=aspect_ratio,
                quality=quality,
                timeout=settings.request_timeout,
            )
            relative_path = _write_panel_image(comic_id, panel_id, image)
        except Exception as exc:
            _set_panel_error(panel_id, str(exc))
            return

        with session_scope() as db:
            panel = db.get(ComicPanel, panel_id)
            if panel is None:
                _remove_panel_media(relative_path)
                return
            panel.image_path = relative_path
            panel.status = "ready"
            panel.error = None


def create_comic(db: Session, novel: Novel, data: ComicCreate) -> Comic:
    chapter = db.get(Chapter, data.chapter_id)
    if chapter is None or chapter.novel_id != novel.id:
        raise ValueError("请选择当前小说中的一个章节来生成漫画。")
    settings = get_settings()
    if not AntigravityImageProvider(
        settings.gemini_base_url, settings.gemini_api_key
    ).available:
        raise ValueError("未配置 Gemini 图片代理，请检查 GEMINI_BASE_URL 和 GEMINI_API_KEY。")
    active_comic = db.scalars(
        select(Comic.id)
        .where(
            Comic.novel_id == novel.id,
            Comic.status.in_(("queued", "storyboarding", "rendering")),
        )
        .limit(1)
    ).first()
    if active_comic is not None:
        raise ComicBusyError("当前小说已有漫画任务正在生成，请等待其完成。")
    panel_count = data.panel_count or settings.comic_default_panel_count
    if not 4 <= panel_count <= 8:
        raise ValueError("漫画分镜数量必须在 4 到 8 格之间。")
    comic = Comic(
        novel_id=novel.id,
        source_chapter_id=chapter.id,
        title=f"{chapter.title or f'第 {chapter.index} 章'} · 漫画",
        visual_style=data.visual_style.strip() or "彩色日漫风，电影感分镜，角色形象保持一致",
        image_model=(data.image_model or settings.comic_default_image_model).strip(),
        aspect_ratio=(data.aspect_ratio or settings.comic_default_aspect_ratio).strip(),
        quality=(data.quality or settings.comic_default_quality).strip(),
        panel_count=panel_count,
        status="queued",
    )
    db.add(comic)
    db.commit()
    db.refresh(comic)
    try:
        manager.start(comic.id)
    except ComicBusyError:
        # The row was committed so it has an ID for worker scheduling.  Remove
        # it again when admission control rejects the task instead of leaving
        # an invisible queued job in the database.
        db.delete(comic)
        db.commit()
        raise
    return comic


def get_comic(db: Session, comic_id: int) -> Comic | None:
    return db.scalars(
        select(Comic)
        .where(Comic.id == comic_id)
        .options(selectinload(Comic.panels))
    ).first()


def get_panel(db: Session, panel_id: int) -> ComicPanel | None:
    return db.get(ComicPanel, panel_id)


def panel_image_file(panel: ComicPanel) -> Path | None:
    if not panel.image_path:
        return None
    base = Path(get_settings().media_dir).resolve()
    candidate = (base / panel.image_path).resolve()
    if base != candidate and base not in candidate.parents:
        return None
    return candidate if candidate.is_file() else None


def remove_comic_media(comic_ids: list[int]) -> None:
    """Remove only known comic-job directories after their DB rows are gone."""
    base = (Path(get_settings().media_dir).resolve() / "comics").resolve()
    for comic_id in comic_ids:
        target = (base / str(int(comic_id))).resolve()
        if target.parent != base:
            logger.warning("Refused unsafe comic media cleanup target: %s", target)
            continue
        try:
            shutil.rmtree(target, ignore_errors=False)
        except FileNotFoundError:
            continue
        except OSError:
            logger.exception("Could not remove comic media directory %s", target)


def _remove_panel_media(relative_path: str) -> None:
    """Best-effort cleanup for a job deleted while an image request was in flight."""
    base = Path(get_settings().media_dir).resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        return
    try:
        target.unlink(missing_ok=True)
    except OSError:
        logger.exception("Could not remove orphaned panel image %s", target)


def _parse_storyboard(raw: str, expected_count: int) -> tuple[str, list[dict[str, str]]]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    begin, end = text.find("{"), text.rfind("}")
    if begin < 0 or end <= begin:
        raise ValueError("模型没有返回合法的分镜 JSON。")
    try:
        payload = json.loads(text[begin : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("模型返回的分镜 JSON 无法解析。") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("panels"), list):
        raise ValueError("分镜 JSON 缺少 panels 数组。")
    panels: list[dict[str, str]] = []
    for item in payload["panels"]:
        if not isinstance(item, dict):
            continue
        spec = {
            key: str(item.get(key) or "").strip()[:8000]
            for key in ("scene_description", "narration", "dialogue", "image_prompt")
        }
        if not spec["scene_description"] or not spec["image_prompt"]:
            raise ValueError("分镜缺少场景描述或图片提示词。")
        panels.append(spec)
    if len(panels) != expected_count:
        # The caller repeats this check against the persisted job count. This
        # early error makes malformed model replies fail before any DB writes.
        raise ValueError(f"模型返回了 {len(panels)} 格分镜，期望 {expected_count} 格。")
    title = str(payload.get("title") or "").strip()
    return title, panels


def _write_panel_image(comic_id: int, panel_id: int, image: bytes) -> str:
    if not image:
        raise ProviderError("图片服务返回了空图片。")
    extension = _image_extension(image)
    relative = Path("comics") / str(comic_id) / f"{panel_id}.{extension}"
    base = Path(get_settings().media_dir).resolve()
    target = (base / relative).resolve()
    if base != target and base not in target.parents:
        raise ValueError("无效的漫画图片保存路径。")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(image)
    return relative.as_posix()


def _image_extension(image: bytes) -> str:
    if image.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if image.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if image.startswith(b"RIFF") and image[8:12] == b"WEBP":
        return "webp"
    return "png"


def _set_comic_error(comic_id: int, message: str) -> None:
    with session_scope() as db:
        comic = db.get(Comic, comic_id)
        if comic is not None:
            comic.status = "failed"
            comic.last_error = message[:4000]


def _set_panel_error(panel_id: int, message: str) -> int | None:
    with session_scope() as db:
        panel = db.get(ComicPanel, panel_id)
        if panel is not None:
            panel.status = "failed"
            panel.error = message[:4000]
            return panel.comic_id
    return None


def _refresh_comic_status(comic_id: int) -> None:
    with session_scope() as db:
        comic = db.get(Comic, comic_id)
        if comic is None:
            return
        panels = list(
            db.scalars(select(ComicPanel).where(ComicPanel.comic_id == comic_id))
        )
        failed = [panel for panel in panels if panel.status == "failed"]
        if failed:
            comic.status = "partial"
            comic.last_error = failed[0].error or "部分分镜生成失败。"
        elif panels and all(panel.status == "ready" for panel in panels):
            comic.status = "ready"
            comic.last_error = None
        else:
            comic.status = "rendering"


manager = ComicManager()
