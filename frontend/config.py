"""Configuração do frontend. Tudo vem do .env (ou de variáveis de ambiente) — nada de URL ou chave no código."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent


def _float(value: str | None, default: float) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    api_url: str = "http://localhost:8000"
    api_key: str = ""
    timeout_s: float = 75.0       # /chat (LLM local pode demorar)
    fast_timeout_s: float = 5.0   # /health, /metrics, /sessions, /handoffs, /feedback

    @property
    def docs_url(self) -> str:
        return f"{self.api_url}/docs"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(BASE_DIR / ".env")  # não sobrescreve variáveis já definidas no ambiente
        env = os.environ.get
        return cls(
            api_url=env("API_URL", "http://localhost:8000").strip().rstrip("/"),
            api_key=env("API_KEY", "").strip(),
            timeout_s=_float(env("API_TIMEOUT_S"), 75.0),
            fast_timeout_s=_float(env("API_FAST_TIMEOUT_S"), 5.0),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
