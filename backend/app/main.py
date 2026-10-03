"""Ponto de entrada da API (FastAPI). Rotas finas: validam (Pydantic) e delegam ao orquestrador."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .analytics.logger import TurnLogger
from .api import chat, feedback, handoffs, health, metrics, sessions
from .config import Settings
from .core.clock import Clock
from .core.orchestrator import Orchestrator
from .deps import Container
from .knowledge.agenda import Agenda
from .knowledge.faq import FaqKnowledge
from .llm.client import LLMClient, LLMUnavailableError
from .memory.session_store import SessionNotFoundError, SessionStore

DESCRIPTION = """
**Prosa · Bot como Serviço** — o *cérebro* conversacional da Clínica Veterinária Patas & Cia (assistente **Duda**).

Toda a inteligência (memória, estado, regra × LLM, guardrails, handoff, sentimento, analytics) mora aqui;
qualquer tela (Streamlit, Gradio, app, WhatsApp) é só uma *lente* que consome esta API.

**Autenticação:** envie o header `X-API-Key` (clique em *Authorize*). `/health` é público.

**Fluxo típico:** `POST /sessions` → `POST /chat` (repetir) → `GET /sessions/{id}` → `GET /metrics`.
"""

TAGS = [
    {"name": "Saúde", "description": "Estado da API e do modelo."},
    {"name": "Sessões", "description": "Ciclo de vida da sessão (memória e estado no servidor)."},
    {"name": "Chat", "description": "Conversa com o bot."},
    {"name": "Analytics", "description": "Métricas conversacionais e CSAT."},
    {"name": "Handoff", "description": "Fila de transferências para atendente humano."},
]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="Prosa Bot — API do cérebro conversacional", version="1.0.0", description=DESCRIPTION, openapi_tags=TAGS)

    runtime = settings.runtime_dir
    runtime.mkdir(parents=True, exist_ok=True)
    store = SessionStore(runtime, persist=settings.persist_sessions, ttl_minutes=settings.session_ttl_minutes, max_sessions=settings.max_sessions)
    llm = LLMClient(settings)
    logger = TurnLogger(runtime)
    system_prompt = (settings.prompts_dir / "system_prompt.md").read_text(encoding="utf-8")
    orchestrator = Orchestrator(
        settings=settings, store=store, llm=llm, faq=FaqKnowledge(settings.data_dir / "faq.json"),
        agenda=Agenda(settings.data_dir / "agenda.json", runtime / "bookings.json"), logger=logger,
        clock=Clock(settings.fixed_today), system_prompt=system_prompt,
    )
    app.state.container = Container(settings, store, llm, logger, orchestrator)

    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(SessionNotFoundError)
    async def _not_found(_: Request, __: SessionNotFoundError):
        return JSONResponse(status_code=404, content={"detail": {"code": "sessao_nao_encontrada",
                            "message": "Sessão não encontrada. Inicie uma nova conversa."}})

    @app.exception_handler(LLMUnavailableError)
    async def _llm_down(_: Request, exc: LLMUnavailableError):
        return JSONResponse(status_code=503, headers={"Retry-After": "5"}, content={"detail": {
            "code": "llm_indisponivel",
            "message": "Estou com dificuldade para responder agora. Tente novamente em instantes ou peça um atendente."}})

    for r in (health.router, sessions.router, chat.router, metrics.router, handoffs.router, feedback.router):
        app.include_router(r)
    return app


app = create_app()
