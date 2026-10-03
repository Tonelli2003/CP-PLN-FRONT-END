"""Container de dependências (singletons do app) e autenticação por X-API-Key."""
from __future__ import annotations

import hmac
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from .analytics.logger import TurnLogger
from .config import Settings
from .core.orchestrator import Orchestrator
from .llm.client import LLMClient
from .memory.session_store import SessionStore


@dataclass
class Container:
    settings: Settings
    store: SessionStore
    llm: LLMClient
    logger: TurnLogger
    orchestrator: Orchestrator


def get_container(request: Request) -> Container:
    return request.app.state.container


_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, description="Chave de acesso à API (definida no .env do backend).")


def require_api_key(request: Request, key: str | None = Security(_api_key_header)) -> None:
    expected = request.app.state.container.settings.api_key
    if not expected:  # autenticação desativada (apenas desenvolvimento)
        return
    if not key or not hmac.compare_digest(key.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail={"code": "api_key_invalida", "message": "Chave de API ausente ou inválida (header X-API-Key)."})
