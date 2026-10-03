from fastapi import APIRouter, Depends

from ..deps import Container, get_container, require_api_key
from ..schemas import ErrorResponse, HandoffQueueItem

router = APIRouter(tags=["Handoff"], dependencies=[Depends(require_api_key)], responses={401: {"model": ErrorResponse}})


@router.get("/handoffs", response_model=list[HandoffQueueItem], summary="Fila de conversas transferidas para humano")
def list_handoffs(c: Container = Depends(get_container)) -> list[HandoffQueueItem]:
    """Lista as conversas transferidas (urgentes primeiro, depois as mais recentes), cada uma com o **resumo estruturado**
    para o atendente. É o que permite uma segunda "lente": um painel de atendente."""
    items = []
    for s in c.store.all():
        h = s.handoff
        if h["active"] and h.get("summary"):
            items.append(HandoffQueueItem(session_id=s.session_id, protocol=h["protocol"], reason=h["reason"],
                                          priority=h["priority"], created_at=h["created_at"], summary=h["summary"], notes=h["notes"]))
    items.sort(key=lambda i: i.created_at, reverse=True)
    items.sort(key=lambda i: 0 if i.priority == "alta" else 1)
    return items
