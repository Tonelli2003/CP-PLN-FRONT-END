"""Handoff: motivo, prioridade e RESUMO ESTRUTURADO para o atendente (dados, intenção, relato, ações)."""
from __future__ import annotations

from ..memory.session_store import SessionState
from ..nlp.sentiment import Sentiment
from ..nlp.text import mask_sensitive

REASON_TEXT = {
    "emergencia": "Possível emergência/urgência com o pet",
    "tema_sensivel": "Tema sensível (luto/eutanásia): requer acolhimento humano",
    "reclamacao": "Reclamação ou problema de cobrança/atendimento",
    "frustracao": "Cliente muito frustrado (sentimento fortemente negativo)",
    "sentimento_negativo_recorrente": "Sentimento negativo em mensagens seguidas",
    "pedido_do_usuario": "Cliente pediu atendimento humano",
    "falha_repetida": "Bot não conseguiu entender após falhas repetidas",
}
URGENT = {"emergencia"}


def priority_for(reason: str) -> str:
    return "alta" if reason in URGENT else "normal"


def build_summary(s: SessionState, reason: str, protocolo: str, current_text: str, sent: Sentiment, now_iso: str) -> dict:
    user_msgs = [m["content"] for m in s.history if m["role"] == "user"][-2:]
    user_msgs.append(mask_sensitive(current_text))
    relato = " | ".join(m.strip() for m in user_msgs if m.strip())[-600:]
    intents = [i for i in s.intents_seen if i not in ("desconhecido", "saudacao", "agradecimento")]
    faltam = []
    if s.flow == "agendar":
        faltam = [k for k in ("nome_tutor", "nome_pet", "data", "horario", "email") if not s.slots.get(k)]
    return {
        "protocolo": protocolo,
        "motivo": REASON_TEXT.get(reason, reason),
        "motivo_codigo": reason,
        "prioridade": priority_for(reason),
        "intencao": intents[-1] if intents else "indefinida",
        "dados_coletados": {k: v for k, v in s.slots.items() if v},
        "pendencias_do_agendamento": faltam,
        "relato": relato,
        "acoes_realizadas": list(s.actions[-10:]),
        "sentimento": {"label": sent.label, "polaridade": sent.polarity},
        "turnos_do_usuario": s.turn + 1,
        "criado_em": now_iso,
    }
