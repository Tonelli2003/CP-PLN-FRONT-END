from fastapi import APIRouter, Depends

from ..deps import Container, get_container, require_api_key
from ..schemas import ChatRequest, ChatResponse, ErrorResponse

router = APIRouter(tags=["Chat"], dependencies=[Depends(require_api_key)])


@router.post(
    "/chat", response_model=ChatResponse, summary="Envia uma mensagem e recebe a resposta + raio-X do turno",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse, "description": "session_id inexistente"},
               503: {"model": ErrorResponse, "description": "Modelo de linguagem indisponível"}},
)
def chat(body: ChatRequest, c: Container = Depends(get_container)) -> ChatResponse:
    """Recebe `{session_id, message}`, delega ao **orquestrador** e devolve a resposta com o *raio-X*:
    intenção, slots, sentimento, fallback, handoff, turno e latência.

    A rota **não contém lógica de PLN** — só valida (Pydantic) e delega.
    Códigos: **200** sucesso · **404** sessão inexistente · **422** requisição inválida · **503** LLM indisponível.
    """
    return ChatResponse(**c.orchestrator.handle(body.session_id, body.message).__dict__)
