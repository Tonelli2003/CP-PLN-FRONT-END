"""Área do chat: banner de handoff, boas-vindas com sugestões e histórico (lido do servidor, nunca guardado na tela)."""
from __future__ import annotations

import streamlit as st

from components import state
from components.theme import render
from components.ui import safe_md, turn_caption

BOT_AVATAR = "🐾"
USER_AVATAR = "🧑"

# Atalhos de início de conversa: cada um dispara uma mensagem real para a API (nada é respondido na tela).
SUGGESTIONS = [
    ("📅 Agendar uma consulta", "Oi, quero marcar uma consulta pro meu cachorro"),
    ("🕘 Horário de funcionamento", "Qual o horário de funcionamento?"),
    ("💰 Valores da consulta", "Quanto custa a consulta?"),
    ("🙋 Falar com um atendente", "Quero falar com um atendente"),
]


def render_handoff_banner(detail: dict) -> None:
    h = detail.get("handoff") or {}
    if h.get("active"):
        urgent = h.get("priority") == "alta"
        box = st.error if urgent else st.warning
        box(f"🙋 **Conversa transferida para um atendente humano** · protocolo **{h.get('protocol')}**"
            f"{' · prioridade ALTA' if urgent else ''}. "
            "O que você escrever agora será anexado ao atendimento.")


def has_user_messages(detail: dict) -> bool:
    return any(m["role"] == "user" for m in detail.get("history", []))


def render_suggestions(detail: dict) -> None:
    """Mostra atalhos só no começo da conversa (antes da 1ª mensagem do usuário) e enquanto não há handoff."""
    if has_user_messages(detail) or (detail.get("handoff") or {}).get("active"):
        return
    render('<div class="pb-welcome">👋 <b>Comece por aqui:</b> escolha um atalho ou escreva a sua mensagem abaixo.</div>')
    with st.container(key="suggestions"):
        for start in range(0, len(SUGGESTIONS), 2):
            cols = st.columns(2)
            for offset, (label, text) in enumerate(SUGGESTIONS[start:start + 2]):
                cols[offset].button(label, key=f"sugg_{start + offset}", on_click=state.queue_prompt, args=(text,))


def render_history(history: list[dict], xrays: dict[int, dict]) -> None:
    """Desenha o histórico vindo de GET /sessions/{id}. O raio-X de cada resposta vem do cache de exibição."""
    turn = 0  # a saudação é o turno 0; cada mensagem do usuário abre o turno seguinte
    for item in history:
        if item["role"] == "user":
            turn += 1
            with st.chat_message("user", avatar=USER_AVATAR):
                st.markdown(safe_md(item["content"]))
        else:
            with st.chat_message("assistant", avatar=BOT_AVATAR):
                st.markdown(safe_md(item["content"]))
                xray = xrays.get(turn)
                if xray:
                    st.caption(turn_caption(xray))
