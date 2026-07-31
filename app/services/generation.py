"""Director-mode generation: root/child chapters, regenerate, suggest options."""
from __future__ import annotations

import logging
import threading

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app import prompts
from app.config import get_settings
from app.db import session_scope
from app.models import Chapter, Character, Novel, Relation
from app.providers.base import ProviderError
from app.providers.registry import get_registry

logger = logging.getLogger(__name__)


class GenerationBusyError(RuntimeError):
    """Raised when a novel is already being generated."""


class GenerationManager:
    def __init__(self) -> None:
        self._locks: dict[int, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def _lock_for(self, novel_id: int) -> threading.Lock:
        with self._locks_guard:
            lock = self._locks.get(novel_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[novel_id] = lock
            return lock

    def is_busy(self, novel_id: int) -> bool:
        return self._lock_for(novel_id).locked()

    def generate_chapter(
        self, novel_id: int, parent_id: int | None, plot_directive: str
    ) -> None:
        """Generate a new root or child chapter (blocking)."""
        lock = self._lock_for(novel_id)
        if not lock.acquire(blocking=False):
            raise GenerationBusyError(f"小说 {novel_id} 正在生成中。")
        try:
            self._generate_chapter(novel_id, parent_id, plot_directive)
        finally:
            lock.release()

    def regenerate_chapter(self, novel_id: int, chapter_id: int, plot_directive: str) -> None:
        lock = self._lock_for(novel_id)
        if not lock.acquire(blocking=False):
            raise GenerationBusyError(f"小说 {novel_id} 正在生成中。")
        try:
            self._regenerate_chapter(novel_id, chapter_id, plot_directive)
        finally:
            lock.release()

    def suggest_options(self, novel_id: int, node_id: int | None) -> list[str]:
        """Synchronous option suggestions (short). Does not take the long generate lock
        exclusivity beyond a soft check — uses same lock to avoid prompt races.
        """
        lock = self._lock_for(novel_id)
        if not lock.acquire(blocking=False):
            raise GenerationBusyError(f"小说 {novel_id} 正在生成中。")
        try:
            return self._suggest_options(novel_id, node_id)
        finally:
            lock.release()

    # ── internals ───────────────────────────────────────────

    def _set_generating(self, novel_id: int, value: bool, error: str | None = None) -> None:
        with session_scope() as db:
            novel = db.get(Novel, novel_id)
            if novel:
                novel.is_generating = value
                if error is not None:
                    novel.last_error = error
                elif value:
                    novel.last_error = None

    def _load_bundle(self, db, novel_id: int) -> Novel:
        novel = db.scalars(
            select(Novel)
            .where(Novel.id == novel_id)
            .options(
                selectinload(Novel.characters),
                selectinload(Novel.relations),
                selectinload(Novel.chapters),
            )
        ).first()
        if novel is None:
            raise ValueError(f"小说 {novel_id} 不存在。")
        return novel

    def _path_to(self, chapters: list[Chapter], node: Chapter | None) -> list[Chapter]:
        if node is None:
            return []
        by_id = {c.id: c for c in chapters}
        path: list[Chapter] = []
        cur: Chapter | None = node
        seen: set[int] = set()
        while cur is not None and cur.id not in seen:
            seen.add(cur.id)
            path.append(cur)
            cur = by_id.get(cur.parent_id) if cur.parent_id else None
        path.reverse()
        return path

    def _generate_chapter(
        self, novel_id: int, parent_id: int | None, plot_directive: str
    ) -> None:
        settings = get_settings()
        registry = get_registry()

        with session_scope() as db:
            novel = self._load_bundle(db, novel_id)
            parent: Chapter | None = None
            if parent_id is not None:
                parent = next((c for c in novel.chapters if c.id == parent_id), None)
                if parent is None:
                    raise ValueError("父节点不存在")
                if parent.novel_id != novel_id:
                    raise ValueError("父节点不属于该小说")
            else:
                # Only one root allowed.
                if any(c.parent_id is None for c in novel.chapters):
                    raise ValueError("已有开篇节点,请从已有节点分叉生成")

            path = self._path_to(list(novel.chapters), parent)
            sibling_count = sum(
                1
                for c in novel.chapters
                if (c.parent_id == parent_id)
                or (c.parent_id is None and parent_id is None)
            )
            node_label = "开篇" if parent is None else f"分支{sibling_count + 1}"
            next_index = (max((c.index for c in novel.chapters), default=0) or 0) + 1

            characters = list(novel.characters)
            relations = list(novel.relations)
            prompt = prompts.build_chapter_prompt(
                novel,
                characters,
                relations,
                path,
                parent,
                plot_directive,
                settings.chapter_target_chars,
                node_label,
            )
            provider = registry.get(novel.provider)
            model = novel.model
            novel.is_generating = True
            novel.last_error = None

        try:
            raw = provider.generate(
                prompt,
                model=model,
                system=prompts.SYSTEM_PROMPT,
                temperature=settings.temperature,
                timeout=settings.request_timeout,
            )
            title, body = prompts.parse_chapter(raw, node_label)
            chapter_summary = self._summarize(provider, model, body, settings)
        except ProviderError as exc:
            self._set_generating(novel_id, False, str(exc))
            raise
        except Exception as exc:
            self._set_generating(novel_id, False, str(exc))
            raise

        with session_scope() as db:
            novel = db.get(Novel, novel_id)
            if novel is None:
                return
            chapter = Chapter(
                novel_id=novel_id,
                parent_id=parent_id,
                index=next_index,
                title=title,
                content=body,
                summary=chapter_summary,
                plot_directive=plot_directive.strip(),
                is_ending=False,
            )
            db.add(chapter)
            novel.is_generating = False
            novel.last_error = None
        logger.info(
            "Novel %s: generated chapter under parent=%s", novel_id, parent_id
        )

    def _regenerate_chapter(
        self, novel_id: int, chapter_id: int, plot_directive: str
    ) -> None:
        settings = get_settings()
        registry = get_registry()

        with session_scope() as db:
            novel = self._load_bundle(db, novel_id)
            chapter = next((c for c in novel.chapters if c.id == chapter_id), None)
            if chapter is None:
                raise ValueError("章节不存在")
            parent = (
                next((c for c in novel.chapters if c.id == chapter.parent_id), None)
                if chapter.parent_id
                else None
            )
            path = self._path_to(list(novel.chapters), parent)
            node_label = chapter.title or "节点"
            prompt = prompts.build_chapter_prompt(
                novel,
                list(novel.characters),
                list(novel.relations),
                path,
                parent,
                plot_directive,
                settings.chapter_target_chars,
                node_label,
            )
            provider = registry.get(novel.provider)
            model = novel.model
            novel.is_generating = True
            novel.last_error = None

        try:
            raw = provider.generate(
                prompt,
                model=model,
                system=prompts.SYSTEM_PROMPT,
                temperature=settings.temperature,
                timeout=settings.request_timeout,
            )
            title, body = prompts.parse_chapter(raw, node_label)
            chapter_summary = self._summarize(provider, model, body, settings)
        except ProviderError as exc:
            self._set_generating(novel_id, False, str(exc))
            raise
        except Exception as exc:
            self._set_generating(novel_id, False, str(exc))
            raise

        with session_scope() as db:
            novel = db.get(Novel, novel_id)
            chapter = db.get(Chapter, chapter_id)
            if novel is None or chapter is None:
                return
            chapter.title = title
            chapter.content = body
            chapter.summary = chapter_summary
            chapter.plot_directive = plot_directive.strip()
            novel.is_generating = False
            novel.last_error = None
        logger.info("Novel %s: regenerated chapter %s", novel_id, chapter_id)

    def _suggest_options(self, novel_id: int, node_id: int | None) -> list[str]:
        settings = get_settings()
        registry = get_registry()
        with session_scope() as db:
            novel = self._load_bundle(db, novel_id)
            current = None
            if node_id is not None:
                current = next((c for c in novel.chapters if c.id == node_id), None)
            path = self._path_to(list(novel.chapters), current)
            prompt = prompts.build_suggest_options_prompt(
                novel,
                list(novel.characters),
                list(novel.relations),
                path,
                current,
            )
            provider = registry.get(novel.provider)
            model = novel.model

        raw = provider.generate(
            prompt,
            model=model,
            system=prompts.SYSTEM_PROMPT,
            temperature=min(1.0, settings.temperature + 0.1),
            timeout=min(120, settings.request_timeout),
        )
        options = prompts.parse_options(raw)
        if not options:
            options = [
                "角色之间发生意外冲突,关系出现裂痕",
                "引入新线索,把故事推向未知方向",
                "给主角一次艰难但关键的选择",
            ]
        return options

    def _summarize(self, provider, model, body: str, settings) -> str:
        summary_prompt = prompts.build_summary_prompt(body)
        try:
            return provider.generate(
                summary_prompt,
                model=model,
                system=prompts.SYSTEM_PROMPT,
                temperature=0.3,
                timeout=settings.request_timeout,
            ).strip()
        except ProviderError:
            return body[:150]


manager = GenerationManager()
