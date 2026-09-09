"""Offline service coverage for comic storyboard and panel rendering jobs."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
import base64
from unittest.mock import patch


PNG_BYTES = b"\x89PNG\r\n\x1a\nminimal-test-image"


def _storyboard(panel_count: int = 4) -> str:
    """Return the exact JSON contract expected from the text provider."""
    return json.dumps(
        {
            "title": "雨夜来信",
            "panels": [
                {
                    "scene_description": f"场景 {index}",
                    "narration": f"旁白 {index}",
                    "dialogue": f"对白 {index}",
                    "image_prompt": f"prompt-{index}",
                }
                for index in range(1, panel_count + 1)
            ],
        },
        ensure_ascii=False,
    )


class _FakeTextProvider:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def generate(self, prompt: str, **kwargs: object) -> str:
        self.calls.append({"prompt": prompt, **kwargs})
        return self.response


class _FakeRegistry:
    def __init__(self, provider: _FakeTextProvider) -> None:
        self.provider = provider
        self.requested_provider_names: list[str | None] = []

    def get(self, name: str | None) -> _FakeTextProvider:
        self.requested_provider_names.append(name)
        return self.provider


class ComicServiceTests(unittest.TestCase):
    """Use a temporary SQLite database and MEDIA_DIR without network calls."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._temp_dir = tempfile.TemporaryDirectory()
        cls._old_env = {
            name: os.environ.get(name)
            for name in ("DB_PATH", "MEDIA_DIR", "GEMINI_BASE_URL", "GEMINI_API_KEY")
        }
        os.environ["DB_PATH"] = os.path.join(cls._temp_dir.name, "comics.db")
        os.environ["MEDIA_DIR"] = cls._temp_dir.name
        os.environ["GEMINI_BASE_URL"] = "http://offline-image-proxy:8045"
        os.environ["GEMINI_API_KEY"] = "offline-test-key"

        # Other unittest modules may dispose their own temporary engine.  Rebind
        # the shared SQLAlchemy factory so this module stays discovery-order safe.
        from sqlalchemy import create_engine, event

        from app.config import get_settings
        import app.db as db_module

        get_settings.cache_clear()
        db_module.engine.dispose()
        engine = create_engine(
            f"sqlite:///{os.environ['DB_PATH']}",
            future=True,
            connect_args={"check_same_thread": False},
        )
        event.listen(engine, "connect", db_module._set_sqlite_pragma)
        db_module.engine = engine
        db_module.SessionLocal.configure(bind=engine)

    @classmethod
    def tearDownClass(cls) -> None:
        from app.config import get_settings
        from app.db import engine

        engine.dispose()
        for name, value in cls._old_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        get_settings.cache_clear()
        cls._temp_dir.cleanup()

    def setUp(self) -> None:
        from app.db import Base, engine, init_db

        Base.metadata.drop_all(engine)
        init_db()

    def _create_comic(self, panel_count: int = 4) -> tuple[int, int]:
        from app.db import session_scope
        from app.models import Chapter, Comic, Novel

        with session_scope() as db:
            novel = Novel(
                title="测试小说",
                genre="悬疑",
                world_setting="一座总在下雨的海边城市。",
                provider="gemini",
                model="gemini-test",
            )
            db.add(novel)
            db.flush()
            chapter = Chapter(
                novel_id=novel.id,
                index=1,
                title="雨夜来信",
                content="林晚在雨里收到一封没有署名的信。",
            )
            db.add(chapter)
            db.flush()
            comic = Comic(
                novel_id=novel.id,
                source_chapter_id=chapter.id,
                title="雨夜来信 · 漫画",
                visual_style="彩色日漫风",
                image_model="gemini-3-pro-image",
                aspect_ratio="16:9",
                quality="standard",
                panel_count=panel_count,
                status="queued",
            )
            db.add(comic)
            db.flush()
            return comic.id, chapter.id

    def _read_comic(self, comic_id: int):
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.db import session_scope
        from app.models import Comic

        with session_scope() as db:
            return db.scalars(
                select(Comic)
                .where(Comic.id == comic_id)
                .options(selectinload(Comic.panels))
            ).one()

    def test_storyboard_and_each_panel_image_are_persisted_when_job_succeeds(self) -> None:
        from app.services.comic_service import ComicManager

        comic_id, _chapter_id = self._create_comic()
        text_provider = _FakeTextProvider(_storyboard())
        registry = _FakeRegistry(text_provider)

        class RecordingImageProvider:
            calls: list[dict[str, object]] = []

            def __init__(self, _base_url: str, _api_key: str) -> None:
                pass

            def generate(self, prompt: str, **kwargs: object) -> bytes:
                self.__class__.calls.append({"prompt": prompt, **kwargs})
                return PNG_BYTES

        with (
            patch("app.services.comic_service.get_registry", return_value=registry),
            patch("app.services.comic_service.AntigravityImageProvider", RecordingImageProvider),
        ):
            ComicManager()._generate_comic(comic_id)

        comic = self._read_comic(comic_id)
        self.assertEqual(comic.status, "ready")
        self.assertIsNone(comic.last_error)
        self.assertEqual(comic.title, "雨夜来信")
        self.assertEqual(registry.requested_provider_names, ["gemini"])
        self.assertEqual(len(text_provider.calls), 1)
        self.assertIn("必须正好输出 4 个 panels", str(text_provider.calls[0]["prompt"]))
        self.assertEqual([panel.status for panel in comic.panels], ["ready"] * 4)
        self.assertEqual([panel.panel_index for panel in comic.panels], [1, 2, 3, 4])
        self.assertEqual(len(RecordingImageProvider.calls), 4)

        media_root = Path(os.environ["MEDIA_DIR"])
        for panel in comic.panels:
            self.assertEqual(panel.scene_description, f"场景 {panel.panel_index}")
            self.assertEqual(panel.image_prompt, f"prompt-{panel.panel_index}")
            self.assertEqual(
                panel.image_path,
                f"comics/{comic_id}/{panel.id}.png",
            )
            self.assertEqual((media_root / panel.image_path).read_bytes(), PNG_BYTES)

    def test_failed_panel_marks_job_partial_then_retry_makes_it_ready(self) -> None:
        from app.providers.base import ProviderError
        from app.services.comic_service import ComicManager

        comic_id, _chapter_id = self._create_comic()
        text_provider = _FakeTextProvider(_storyboard())

        class FlakyImageProvider:
            fail_second_panel_once = True
            calls: list[str] = []

            def __init__(self, _base_url: str, _api_key: str) -> None:
                pass

            def generate(self, prompt: str, **_kwargs: object) -> bytes:
                self.__class__.calls.append(prompt)
                if prompt == "prompt-2" and self.__class__.fail_second_panel_once:
                    self.__class__.fail_second_panel_once = False
                    raise ProviderError("temporary image provider failure")
                return PNG_BYTES

        manager = ComicManager()
        with (
            patch(
                "app.services.comic_service.get_registry",
                return_value=_FakeRegistry(text_provider),
            ),
            patch("app.services.comic_service.AntigravityImageProvider", FlakyImageProvider),
        ):
            manager._generate_comic(comic_id)

            comic = self._read_comic(comic_id)
            self.assertEqual(comic.status, "partial")
            failed = next(panel for panel in comic.panels if panel.status == "failed")
            self.assertEqual(failed.panel_index, 2)
            self.assertIn("temporary image provider failure", failed.error or "")
            self.assertIn("temporary image provider failure", comic.last_error or "")
            self.assertIsNone(failed.image_path)

            manager._retry_panel(failed.id)

        comic = self._read_comic(comic_id)
        self.assertEqual(comic.status, "ready")
        self.assertIsNone(comic.last_error)
        self.assertEqual([panel.status for panel in comic.panels], ["ready"] * 4)
        self.assertEqual(FlakyImageProvider.calls.count("prompt-2"), 2)
        self.assertTrue(
            all((Path(os.environ["MEDIA_DIR"]) / panel.image_path).is_file() for panel in comic.panels)
        )

    def test_removing_comic_media_only_deletes_requested_job_directory(self) -> None:
        from app.services.comic_service import remove_comic_media

        media_root = Path(os.environ["MEDIA_DIR"])
        target = media_root / "comics" / "101"
        sibling = media_root / "comics" / "202"
        unrelated = media_root / "unrelated.txt"
        (target / "nested").mkdir(parents=True)
        sibling.mkdir(parents=True)
        (target / "nested" / "panel.png").write_bytes(PNG_BYTES)
        (sibling / "panel.png").write_bytes(PNG_BYTES)
        unrelated.write_text("keep", encoding="utf-8")

        remove_comic_media([101])

        self.assertFalse(target.exists())
        self.assertTrue((sibling / "panel.png").is_file())
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "keep")

    def test_image_provider_decodes_openai_compatible_base64_payload(self) -> None:
        from app.providers.antigravity_image_provider import AntigravityImageProvider

        class FakeResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return {
                    "data": [
                        {"b64_json": base64.b64encode(PNG_BYTES).decode("ascii")}
                    ]
                }

        with patch("httpx.post", return_value=FakeResponse()) as post:
            image = AntigravityImageProvider(
                "http://offline-image-proxy:8045", "offline-test-key"
            ).generate(
                "雨夜，远景",
                model="gemini-3-pro-image",
                size="16:9",
                quality="standard",
                timeout=10,
            )

        self.assertEqual(image, PNG_BYTES)
        self.assertEqual(post.call_args.args[0], "http://offline-image-proxy:8045/v1/images/generations")
        self.assertEqual(post.call_args.kwargs["json"]["response_format"], "b64_json")


if __name__ == "__main__":
    unittest.main()
