import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

TODAY = date(2026, 10, 2)  # sexta-feira


def make_settings(tmp_path, **kw):
    base = replace(Settings(), llm_provider="mock", fixed_today=TODAY, runtime_dir=tmp_path, api_key="", **kw)
    return base


@pytest.fixture()
def app(tmp_path):
    return create_app(make_settings(tmp_path))


@pytest.fixture()
def client(app):
    return TestClient(app)


class Chat:
    """Ajudante de teste: uma conversa."""
    def __init__(self, client, headers=None):
        self.c, self.h = client, headers or {}
        r = client.post("/sessions", headers=self.h)
        assert r.status_code == 201
        self.sid = r.json()["session_id"]

    def say(self, msg):
        r = self.c.post("/chat", json={"session_id": self.sid, "message": msg}, headers=self.h)
        assert r.status_code == 200, r.text
        return r.json()


@pytest.fixture()
def chat(client):
    return Chat(client)
