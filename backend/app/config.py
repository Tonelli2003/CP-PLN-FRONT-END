"""Configuração central. Tudo vem de variáveis de ambiente (.env) — nada de segredo no código."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


def _int(value: str | None, default: int) -> int:
    try:
        return int(value) if value not in (None, "") else default
    except ValueError:
        return default


def _float(value: str | None, default: float) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    api_key: str = ""
    cors_origins: tuple[str, ...] = ("http://localhost:8501", "http://localhost:7860")

    llm_provider: str = "ollama"
    llm_model: str = "qwen2.5:3b"
    ollama_url: str = "http://localhost:11434"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_timeout_s: float = 60.0
    llm_temperature: float = 0.3
    llm_max_tokens: int = 220
    llm_num_ctx: int = 4096
    llm_verbalize: bool = True
    llm_fail_mode: str = "error"  # error | degrade

    window_turns: int = 8
    session_ttl_minutes: int = 240
    max_sessions: int = 1000
    reply_max_chars: int = 600
    max_message_chars: int = 1000

    fixed_today: date | None = None
    persist_sessions: bool = True

    data_dir: Path = BASE_DIR / "data"
    runtime_dir: Path = BASE_DIR / "data" / "runtime"
    prompts_dir: Path = BASE_DIR / "prompts"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(BASE_DIR / ".env")  # não sobrescreve variáveis já definidas no ambiente
        env = os.environ.get
        fixed = env("FIXED_TODAY", "").strip()
        origins = tuple(o.strip() for o in env("CORS_ORIGINS", "http://localhost:8501,http://localhost:7860").split(",") if o.strip())
        runtime = env("RUNTIME_DIR", "").strip()
        return cls(
            api_key=env("API_KEY", "").strip(),
            cors_origins=origins,
            llm_provider=env("LLM_PROVIDER", "ollama").strip().lower(),
            llm_model=env("LLM_MODEL", "qwen2.5:3b").strip(),
            ollama_url=env("OLLAMA_URL", "http://localhost:11434").rstrip("/"),
            llm_base_url=env("LLM_BASE_URL", "").rstrip("/"),
            llm_api_key=env("LLM_API_KEY", "").strip(),
            llm_timeout_s=_float(env("LLM_TIMEOUT_S"), 60.0),
            llm_temperature=_float(env("LLM_TEMPERATURE"), 0.3),
            llm_max_tokens=_int(env("LLM_MAX_TOKENS"), 220),
            llm_num_ctx=_int(env("LLM_NUM_CTX"), 4096),
            llm_verbalize=_bool(env("LLM_VERBALIZE"), True),
            llm_fail_mode=env("LLM_FAIL_MODE", "error").strip().lower(),
            window_turns=_int(env("WINDOW_TURNS"), 8),
            session_ttl_minutes=_int(env("SESSION_TTL_MINUTES"), 240),
            max_sessions=_int(env("MAX_SESSIONS"), 1000),
            fixed_today=date.fromisoformat(fixed) if fixed else None,
            runtime_dir=Path(runtime) if runtime else BASE_DIR / "data" / "runtime",
        )
