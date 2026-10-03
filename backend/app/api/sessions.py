from fastapi import APIRouter, Depends, Path

from ..core import responses as R
from ..core.orchestrator import handoff_public
from ..deps import Container, get_container, require_api_key
from ..schemas import (SESSION_ID_PATTERN, ErrorResponse, SessionCreateResponse, SessionDeleteResponse, SessionDetail)

router = APIRouter(tags=["Sessões"], dependencies=[Depends(require_api_key)],
                   responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})


@router.post("/sessions", response_model=SessionCreateResponse, status_code=201, summary="Cria uma sessão de conversa")
def create_session(c: Container = Depends(get_container)) -> SessionCreateResponse:
    """Cria a sessão e devolve o `session_id` e a **saudação**, que declara as capacidades do bot.
    A memória e o estado passam a viver no servidor, indexados por esse `session_id`."""
    s, greeting = c.orchestrator.start_session()
    return SessionCreateResponse(session_id=s.session_id, greeting=greeting, capabilities=R.CAPABILITIES, created_at=s.created_at)


@router.get("/sessions/{session_id}", response_model=SessionDetail, summary="Histórico, slots e situação da conversa")
def get_session(session_id: str = Path(..., pattern=SESSION_ID_PATTERN), c: Container = Depends(get_container)) -> SessionDetail:
    """Devolve histórico, slots, fluxo e situação (inclusive handoff com resumo). **404** se a sessão não existe."""
    s = c.store.snapshot(session_id)
    return SessionDetail(
        session_id=s.session_id, created_at=s.created_at, status=s.status, turn=s.turn, slots=s.slots,
        flow={"state": s.flow, "awaiting": s.awaiting}, handoff=handoff_public(s), booking=s.booking, history=s.history,
    )


@router.delete("/sessions/{session_id}", response_model=SessionDeleteResponse, summary="Apaga a sessão (direito ao esquecimento — LGPD)")
def delete_session(session_id: str = Path(..., pattern=SESSION_ID_PATTERN), c: Container = Depends(get_container)) -> SessionDeleteResponse:
    """Apaga histórico, slots e estado da sessão e **anonimiza o log** (remove os textos e troca o session_id por um hash),
    preservando só os agregados das métricas."""
    c.store.get(session_id)
    with c.store.lock(session_id):
        c.store.delete(session_id)
    c.logger.anonymize_session(session_id)
    return SessionDeleteResponse(session_id=session_id)
