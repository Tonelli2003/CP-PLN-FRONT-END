"""Fixtures dos testes do frontend. Nenhum teste aqui precisa de backend, LLM ou rede (exceto o de integração)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Settings  # noqa: E402
from services.api_client import ApiClient, ApiError, ErrorKind  # noqa: E402

SLOTS = {"nome_tutor": None, "nome_pet": None, "especie": None, "data": None, "horario": None, "email": None}


@pytest.fixture
def settings() -> Settings:
    return Settings(api_url="http://api.test", api_key="k123", timeout_s=5, fast_timeout_s=2)


def make_client(settings: Settings, handler) -> ApiClient:
    import httpx
    return ApiClient(settings, transport=httpx.MockTransport(handler))


class FakeClient:
    """Dublê do ApiClient para testar as TELAS sem backend. Simula um cérebro mínimo com estado por session_id."""

    def __init__(self, *, offline: bool = False, handoff: bool = False, send_error: ApiError | None = None):
        self.offline, self.handoff, self.send_error = offline, handoff, send_error
        self.sessions: dict[str, list[dict]] = {}
        self._seq = 0
        self.calls: list[tuple] = []
        self.metrics = None

    def _guard(self):
        if self.offline:
            raise ApiError(ErrorKind.OFFLINE, "Não consegui falar com o serviço de atendimento agora.", hint="dica técnica")

    def health(self):
        self._guard()
        return {"status": "ok", "app": "fake", "llm": {"provider": "mock", "model": "mock", "available": True, "detail": ""},
                "sessions_in_memory": len(self.sessions)}

    def create_session(self):
        self._guard()
        self._seq += 1
        sid = f"sess{self._seq:04d}"
        self.sessions[sid] = [{"role": "assistant", "content": "Oi! Eu sou a Duda.", "ts": "t0"}]
        self.calls.append(("create_session",))
        return {"session_id": sid, "greeting": "Oi! Eu sou a Duda.", "capabilities": [], "created_at": "t0"}

    def get_session(self, sid):
        self._guard()
        if sid not in self.sessions:
            raise ApiError(ErrorKind.NOT_FOUND, "Sessão não encontrada. Inicie uma nova conversa.", status=404)
        hist = self.sessions[sid]
        h = ({"active": True, "reason": "reclamacao", "priority": "alta", "protocol": "HO-1",
              "summary": {"protocolo": "HO-1", "motivo": "Reclamação", "motivo_codigo": "reclamacao", "prioridade": "alta",
                          "intencao": "reclamacao", "dados_coletados": {}, "pendencias_do_agendamento": [],
                          "relato": "absurdo", "acoes_realizadas": ["Handoff acionado"],
                          "sentimento": {"label": "negativo", "polaridade": -0.9}, "turnos_do_usuario": 1, "criado_em": "t"}}
             if self.handoff else {"active": False, "reason": None, "priority": None, "protocol": None, "summary": None})
        n_user = sum(1 for m in hist if m["role"] == "user")
        return {"session_id": sid, "created_at": "t0", "status": "transferida" if self.handoff else "ativa", "turn": n_user,
                "slots": dict(SLOTS, nome_tutor="Marina" if n_user else None), "flow": {"state": "idle", "awaiting": None},
                "handoff": h, "booking": None, "history": list(hist)}

    def send_message(self, sid, message):
        self._guard()
        self.calls.append(("send_message", sid, message))
        if self.send_error:
            raise self.send_error
        hist = self.sessions[sid]
        hist.append({"role": "user", "content": message, "ts": "t"})
        reply = "Os valores: consulta R$ 150 e retorno R$ 90."
        hist.append({"role": "assistant", "content": reply, "ts": "t"})
        n_user = sum(1 for m in hist if m["role"] == "user")
        return {"session_id": sid, "reply": reply, "intent": "faq", "intent_confidence": 0.9, "slots": dict(SLOTS),
                "sentiment": {"label": "neutro", "score": 0.7, "polarity": 0.0}, "fallback": False, "fallback_type": None,
                "handoff": {"active": False}, "turn": n_user, "latency_ms": 12, "source": "template", "llm_used": False,
                "guardrail_events": [{"stage": "input", "name": "teste", "action": "log", "detail": None}],
                "flow": {"state": "idle", "awaiting": None}}

    def delete_session(self, sid):
        self.calls.append(("delete_session", sid))
        self.sessions.pop(sid, None)
        return {"session_id": sid, "deleted": True}

    def send_feedback(self, sid, rating, comment=None):
        self.calls.append(("send_feedback", sid, rating))
        return {"session_id": sid, "rating": rating, "registered": True}

    def get_metrics(self):
        self._guard()
        return self.metrics

    def list_handoffs(self):
        self._guard()
        return []


EMPTY_METRICS = {
    "periodo": {"inicio": None, "fim": None}, "total_conversas": 0, "total_turnos_usuario": 0, "taxa_contencao": 0.0,
    "taxa_fallback": 0.0, "taxa_handoff": 0.0, "mensagens_por_conversa": 0.0, "taxa_resolucao": 0.0,
    "agendamentos_concluidos": 0, "taxa_conclusao_agendamento": 0.0, "latencia_media_ms": 0, "latencia_p95_ms": 0,
    "distribuicao_intencoes": {}, "distribuicao_sentimento": {}, "fallback_por_tipo": {}, "fallback_por_estado": {},
    "handoff_por_motivo": {}, "erros_validacao": {}, "eventos_guardrail": {}, "turnos_com_tom_de_acolhimento": 0,
    "fonte_da_resposta": {}, "faq_mais_consultadas": {}, "total_feedbacks": 0, "csat_medio": None,
    "csat_medio_conversas_contidas": None, "csat_medio_conversas_transferidas": None,
}

FULL_METRICS = dict(
    EMPTY_METRICS, periodo={"inicio": "2026-10-02", "fim": "2026-10-02"}, total_conversas=23, total_turnos_usuario=88,
    taxa_contencao=0.696, taxa_fallback=0.08, taxa_handoff=0.304, mensagens_por_conversa=3.83, taxa_resolucao=0.435,
    agendamentos_concluidos=4, taxa_conclusao_agendamento=0.4, latencia_media_ms=3417, latencia_p95_ms=8489,
    distribuicao_intencoes={"agendar": 45, "faq": 10}, distribuicao_sentimento={"neutro": 82, "negativo": 3},
    fallback_por_tipo={"nao_entendi": 5, "fora_da_base": 2}, handoff_por_motivo={"falha_repetida": 2, "emergencia": 1},
    eventos_guardrail={"output:fato_omitido": 11}, fonte_da_resposta={"template": 44, "llm": 29, "template_guardrail": 15},
    faq_mais_consultadas={"endereco": 3}, total_feedbacks=8, csat_medio=3.88, csat_medio_conversas_contidas=4.8,
    csat_medio_conversas_transferidas=2.33, turnos_com_tom_de_acolhimento=1,
)
