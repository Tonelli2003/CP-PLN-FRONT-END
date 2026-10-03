from fastapi import APIRouter, Depends

from ..analytics.metrics import compute_metrics
from ..deps import Container, get_container, require_api_key
from ..schemas import ErrorResponse, MetricsResponse

router = APIRouter(tags=["Analytics"], dependencies=[Depends(require_api_key)], responses={401: {"model": ErrorResponse}})


@router.get("/metrics", response_model=MetricsResponse, summary="Métricas conversacionais calculadas a partir do log")
def metrics(c: Container = Depends(get_container)) -> MetricsResponse:
    """Calcula, a partir do **log por turno (JSONL)**: taxa de contenção, de fallback e de handoff, mensagens por
    conversa, taxa de resolução, conclusão de agendamentos, latência, distribuições (intenção, sentimento, motivo de
    handoff), eventos de guardrail e CSAT. Taxas em fração (0 a 1)."""
    return MetricsResponse(**compute_metrics(c.logger.read_all()))
