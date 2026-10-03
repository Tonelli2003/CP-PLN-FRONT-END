from fastapi import APIRouter, Depends

from ..deps import Container, get_container, require_api_key
from ..schemas import ErrorResponse, FeedbackRequest, FeedbackResponse

router = APIRouter(tags=["Analytics"], dependencies=[Depends(require_api_key)],
                   responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})


@router.post("/feedback", response_model=FeedbackResponse, status_code=201, summary="Registra a nota (CSAT) da conversa")
def feedback(body: FeedbackRequest, c: Container = Depends(get_container)) -> FeedbackResponse:
    """Registra a nota de 1 a 5. O `/metrics` cruza o CSAT com a **contenção** (conversas contidas × transferidas),
    evitando o "erro clássico": contenção alta com cliente insatisfeito."""
    with c.store.lock(body.session_id):
        s = c.store.get(body.session_id)
        s.feedback = {"rating": body.rating, "comment": body.comment}
        c.store.save(s)
    c.logger.write({"type": "feedback", "ts": c.orchestrator.clock.now_iso(), "session_id": body.session_id,
                    "rating": body.rating, "comment": (body.comment or "")[:200]})
    return FeedbackResponse(session_id=body.session_id, rating=body.rating)
