from fastapi import APIRouter, Depends

from ..deps import Container, get_container
from ..schemas import HealthResponse

router = APIRouter(tags=["Saúde"])


@router.get("/health", response_model=HealthResponse, summary="Estado da API e do modelo de linguagem")
def health(c: Container = Depends(get_container)) -> HealthResponse:
    """Informa se a API está no ar e qual **provedor/modelo** de LLM está em uso (e se está acessível).
    Não exige X-API-Key. `status = degraded` significa que a API responde, mas o LLM está indisponível
    (turnos críticos — emergência, handoff, guardrails, fallback, confirmação — continuam funcionando)."""
    info = c.llm.health()
    return HealthResponse(status="ok" if info["available"] else "degraded", app="Prosa Bot (backend)",
                          llm=info, sessions_in_memory=len(c.store.all()))
