"""Montagem das mensagens enviadas ao LLM: system + estado + histórico (janela deslizante) + nova fala.

Estratégia de controle de janela (R3):
  • JANELA DESLIZANTE de N turnos (WINDOW_TURNS, padrão 8 = 16 mensagens) — cabe folgado em num_ctx=4096
    (~700 tokens de prompt + ~150 de estado + ~800 de histórico).
  • RESUMO ROLANTE determinístico: o que sai da janela não se perde — slots, horários oferecidos e
    ações já realizadas vivem no ESTADO (estrutura de dados) e são reinjetados em todo turno.
  Memória ≠ estado: o histórico é conversa; o estado é a verdade operacional.
"""
from __future__ import annotations

from .session_store import SessionState

LABELS = {"nome_tutor": "nome do tutor", "nome_pet": "nome do pet", "especie": "espécie", "data": "data",
          "horario": "horário", "email": "e-mail"}


def history_window(history: list[dict], n_turns: int) -> list[dict]:
    return history[-(n_turns * 2):]


def rolling_summary(s: SessionState, n_turns: int) -> str:
    """Resumo do que ficou FORA da janela (vazio se nada foi cortado)."""
    if len(s.history) <= n_turns * 2:
        return ""
    cortadas = len(s.history) - n_turns * 2
    acoes = "; ".join(s.actions[:-4][-6:]) or "nenhuma"
    return f"{cortadas} mensagens antigas saíram da janela. Ações anteriores: {acoes}."


def state_block(s: SessionState, n_turns: int) -> str:
    got = [f"{LABELS[k]} = {v}" for k, v in s.slots.items() if v]
    missing = [LABELS[k] for k in ("nome_tutor", "nome_pet", "data", "horario", "email") if not s.slots.get(k)]
    lines = ["## Estado atual da conversa (fornecido pelo sistema; é a fonte de verdade)"]
    lines.append(f"- Fluxo: {s.flow}; aguardando: {s.awaiting or 'nada'}")
    lines.append(f"- Dados coletados: {'; '.join(got) if got else 'nenhum'}")
    if s.flow == "agendar":
        lines.append(f"- Dados que faltam: {', '.join(missing) if missing else 'nenhum'}")
    if s.offered_times:
        lines.append(f"- Horários já oferecidos para {s.offered_date}: {', '.join(s.offered_times)}")
    summary = rolling_summary(s, n_turns)
    if summary:
        lines.append(f"- {summary}")
    return "\n".join(lines)


def build_messages(system_text: str, history: list[dict], n_turns: int, user_message: str) -> list[dict]:
    msgs = [{"role": "system", "content": system_text}]
    msgs += [{"role": m["role"], "content": m["content"]} for m in history_window(history, n_turns)]
    msgs.append({"role": "user", "content": user_message})
    return msgs
