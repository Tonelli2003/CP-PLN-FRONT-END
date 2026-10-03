"""Página do CHAT com o painel Raio-X.

Esta tela NÃO contém o bot: ela só conversa com a API (services/api_client.py). O histórico, os slots e o handoff
vêm do backend, indexados pelo session_id (a única coisa que a tela guarda).
"""
from __future__ import annotations

import streamlit as st

from components import state
from components.chat import BOT_AVATAR, USER_AVATAR, render_handoff_banner, render_history, render_suggestions
from components.raio_x import render_raio_x
from components.sidebar import render_api_status, render_session_controls
from components.theme import hero
from components.ui import safe_md, show_api_error
from services.api_client import ApiError

client = state.get_client()
api_up = render_api_status(client)

hero("🐾", "Duda · Clínica Veterinária Patas & Cia",
     "Assistente virtual (IA) que agenda consultas, tira dúvidas e chama um atendente humano quando precisa.",
     ["Agendamento", "FAQ da clínica", "Handoff para humano", "Raio-X em tempo real"])

if not api_up:
    st.error("🔌 O serviço de atendimento está indisponível no momento. Veja o aviso na barra lateral e tente novamente.")
    st.stop()

try:
    sid = state.ensure_session(client)
    detail = client.get_session(sid)
except ApiError as err:
    if err.is_session_lost:                      # a sessão expirou ou foi apagada: começa outra
        st.toast("Sua sessão anterior expirou. Começando uma nova conversa.", icon="🔎")
        state.forget_session()
        st.rerun()
    show_api_error(err)
    st.stop()

render_session_controls(client, sid)

# A mensagem vem da caixa de texto ou de um botão de sugestão (que a deixou na fila antes desta execução).
queued = state.pop_queued_prompt()
prompt = st.chat_input("Escreva sua mensagem…", max_chars=1000) or queued
col_chat, col_xray = st.columns([3, 2], gap="large")

with col_chat:
    render_handoff_banner(detail)
    chat_box = st.container(height=520, border=False)   # o chat rola por dentro; o raio-X fica sempre à vista
    with chat_box:
        render_history(detail["history"], state.xrays())

    if prompt:
        with chat_box:
            with st.chat_message("user", avatar=USER_AVATAR):
                st.markdown(safe_md(prompt))
            failure: ApiError | None = None
            with st.chat_message("assistant", avatar=BOT_AVATAR):
                with st.spinner("Duda está pensando…"):
                    try:
                        xray = client.send_message(sid, prompt)
                    except ApiError as err:
                        failure = err
                if failure is not None:
                    show_api_error(failure)
                    if failure.is_session_lost:
                        state.forget_session()
                    else:
                        st.caption("Sua mensagem não foi registrada. Você pode enviá-la novamente.")
            if failure is None:
                state.xrays()[xray["turn"]] = xray
                st.rerun()                           # redesenha a partir do que o servidor gravou
    else:
        render_suggestions(detail)


with col_xray:
    last_turn = max(state.xrays(), default=None)
    with st.container(height=600, border=False):          # rola por dentro: a página inteira não precisa rolar
        render_raio_x(detail, state.xrays().get(last_turn) if last_turn is not None else None)
