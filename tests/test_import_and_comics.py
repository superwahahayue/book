"""Regression coverage for source imports and comic storyboard primitives."""
from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from io import BytesIO
from zipfile import ZipFile


class ImportedSourceIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temp_dir = tempfile.TemporaryDirectory()
        os.environ["DB_PATH"] = os.path.join(cls._temp_dir.name, "imports.db")
        os.environ["MEDIA_DIR"] = cls._temp_dir.name

        # Other integration modules may already have imported app.db with a
        # temporary database that they subsequently remove. Rebind the shared
        # session factory here so unittest discovery remains order-independent.
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

        from fastapi.testclient import TestClient

        from app.main import create_app

        cls.client = TestClient(create_app())
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        from app.db import engine

        cls.client.__exit__(None, None, None)
        engine.dispose()
        cls._temp_dir.cleanup()

    def setUp(self) -> None:
        from app.db import Base, engine, init_db

        Base.metadata.drop_all(engine)
        init_db()
        self.client.cookies.clear()
        response = self.client.post(
            "/api/auth/register",
            json={"email": "importer@example.com", "password": "password123"},
        )
        self.assertEqual(response.status_code, 201)

    def _wait_for_import(self, document_id: int) -> dict:
        for _ in range(100):
            response = self.client.get(f"/api/imports/{document_id}")
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            if payload["status"] in {"ready", "failed"}:
                return payload
            time.sleep(0.02)
        self.fail("import worker did not finish in time")

    def test_txt_import_creates_a_primary_chapter_path(self) -> None:
        source = (
            "第一章 雨夜\n"
            "林晚在雨里等了一整夜。\n\n"
            "第二章 来信\n"
            "第二天清晨，她终于收到一封没有署名的信。"
        ).encode("utf-8")
        response = self.client.post(
            "/api/imports/novel",
            data={"title": "导入测试", "genre": "悬疑"},
            files={"file": ("story.txt", source, "text/plain")},
        )
        self.assertEqual(response.status_code, 202, response.text)
        imported = self._wait_for_import(response.json()["id"])
        self.assertEqual(imported["status"], "ready", imported.get("error"))
        self.assertIsNotNone(imported["result_novel_id"])

        novel = self.client.get(f"/api/novels/{imported['result_novel_id']}").json()
        self.assertEqual(novel["title"], "导入测试")
        self.assertEqual(len(novel["chapters"]), 2)
        chapters = sorted(novel["chapters"], key=lambda item: item["index"])
        self.assertIsNone(chapters[0]["parent_id"])
        self.assertEqual(chapters[1]["parent_id"], chapters[0]["id"])
        self.assertTrue(chapters[1]["is_primary"])
        self.assertTrue(chapters[0]["summary"])

    def test_import_document_is_not_visible_to_another_user(self) -> None:
        response = self.client.post(
            "/api/imports/novel",
            files={"file": ("private.md", b"# \xe7\xac\xac\xe4\xb8\x80\xe7\xab\xa0\n\xe6\xad\xa3\xe6\x96\x87", "text/markdown")},
        )
        self.assertEqual(response.status_code, 202, response.text)
        document_id = response.json()["id"]
        self.client.post("/api/auth/logout")
        self.client.post(
            "/api/auth/register",
            json={"email": "other@example.com", "password": "password123"},
        )
        self.assertEqual(self.client.get(f"/api/imports/{document_id}").status_code, 404)

    def test_deleting_retained_source_keeps_the_imported_novel(self) -> None:
        response = self.client.post(
            "/api/imports/novel",
            files={"file": ("keep-novel.txt", "第一章\n正文内容".encode("utf-8"), "text/plain")},
        )
        self.assertEqual(response.status_code, 202, response.text)
        imported = self._wait_for_import(response.json()["id"])
        self.assertEqual(imported["status"], "ready", imported.get("error"))

        deleted = self.client.delete(f"/api/source-documents/{imported['id']}")
        self.assertEqual(deleted.status_code, 204, deleted.text)
        self.assertEqual(self.client.get(f"/api/imports/{imported['id']}").status_code, 404)
        self.assertEqual(
            self.client.get(f"/api/novels/{imported['result_novel_id']}").status_code,
            200,
        )

    def test_docx_with_too_many_archive_members_is_rejected(self) -> None:
        from app.services.import_service import SourceImportError, parse_upload_bytes

        stream = BytesIO()
        with ZipFile(stream, "w") as archive:
            for index in range(2001):
                archive.writestr(f"word/part-{index}.xml", "x")
        with self.assertRaises(SourceImportError):
            parse_upload_bytes("unsafe.docx", stream.getvalue())

    def test_story_profile_samples_middle_chapters_for_long_imports(self) -> None:
        from app.services.import_service import ParsedChapter, _heuristic_story_profile

        chapters = [
            ParsedChapter(title=f"第 {index} 章", content=f"这是第 {index} 章的重要转折。")
            for index in range(1, 101)
        ]
        profile = _heuristic_story_profile(chapters)
        self.assertIn("第 1 章", profile)
        self.assertIn("第 100 章", profile)
        self.assertIn("第 49 章", profile)

    def test_style_reference_requires_authorization_confirmation(self) -> None:
        response = self.client.post(
            "/api/style-references",
            data={"consent": "false"},
            files={"file": ("reference.txt", "示例文本".encode("utf-8"), "text/plain")},
        )
        self.assertEqual(response.status_code, 400)

    def test_storyboard_parser_requires_the_requested_panel_count(self) -> None:
        from app.services.comic_service import _parse_storyboard

        panels = [
            {
                "scene_description": f"场景 {index}",
                "narration": "旁白",
                "dialogue": "对白",
                "image_prompt": f"提示词 {index}",
            }
            for index in range(1, 5)
        ]
        title, parsed = _parse_storyboard(
            json.dumps({"title": "雨夜来信", "panels": panels}, ensure_ascii=False), 4
        )
        self.assertEqual(title, "雨夜来信")
        self.assertEqual(len(parsed), 4)
        with self.assertRaises(ValueError):
            _parse_storyboard(json.dumps({"panels": panels}, ensure_ascii=False), 5)


if __name__ == "__main__":
    unittest.main()
