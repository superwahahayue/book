"""Integration coverage for account authentication and content isolation."""
from __future__ import annotations

import os
import tempfile
import unittest


class AuthenticationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temp_dir = tempfile.TemporaryDirectory()
        os.environ["DB_PATH"] = os.path.join(cls._temp_dir.name, "test.db")
        os.environ["ADMIN_EMAILS"] = "admin@example.com"

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

    def test_registration_ownership_and_administrator_access(self) -> None:
        from app.db import session_scope
        from app.models import Novel

        with session_scope() as db:
            db.add(Novel(title="Legacy story"))

        response = self.client.post(
            "/api/auth/register",
            json={"email": "ADMIN@example.com", "password": "password123"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["is_admin"])
        self.assertEqual(len(self.client.get("/api/novels").json()), 1)
        self.client.post("/api/auth/logout")

        response = self.client.post(
            "/api/auth/register",
            json={"email": "owner@example.com", "password": "password123"},
        )
        self.assertEqual(response.status_code, 201)
        novel = self.client.post("/api/novels", json={"title": "Owner story"}).json()
        character = self.client.post(
            f"/api/novels/{novel['id']}/characters", json={"name": "Hero"}
        ).json()
        self.client.post("/api/auth/logout")

        self.client.post(
            "/api/auth/register",
            json={"email": "other@example.com", "password": "password123"},
        )
        self.assertEqual(self.client.get(f"/api/novels/{novel['id']}").status_code, 404)
        self.assertEqual(
            self.client.patch(
                f"/api/characters/{character['id']}", json={"name": "Intruder"}
            ).status_code,
            404,
        )
        self.assertEqual(self.client.get("/api/novels").json(), [])
        self.client.post("/api/auth/logout")

        response = self.client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "password123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.client.get("/api/novels").json()), 2)

    def test_logout_revokes_the_current_session(self) -> None:
        self.assertEqual(self.client.get("/api/novels").status_code, 401)
        self.client.post(
            "/api/auth/register",
            json={"email": "user@example.com", "password": "password123"},
        )
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)


if __name__ == "__main__":
    unittest.main()
