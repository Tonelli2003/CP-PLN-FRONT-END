"""Estado da TELA (Streamlit). O frontend guarda apenas o `session_id`; histórico, slots e handoff vivem no backend.

O que fica em st.session_state:
  * `session_id`  : a única "memória" da conversa que o front possui (também vai para a URL, `?sid=...`, para
                    sobreviver a um F5 do navegador);
  * `xrays`       : cache de EXIBIÇÃO do raio-X de cada turno (intenção/sentimento/latência), que o GET /sessions
                    não devolve. Perdê-lo não perde a conversa.
"""
from __future__ import annotations

from typing import Optional

import streamlit as st

from config import get_settings
from services.api_client import ApiClient, ApiError

SID_KEY = "session_id"
XRAYS_KEY = "xrays"
FEEDBACK_SENT_KEY = "feedback_sent"
QUEUED_KEY = "queued_prompt"   # mensagem escolhida num botão de sugestão, enviada na próxima execução


@st.cache_resource(show_spinner=False)
def get_client() -> ApiClient:
    """Um único cliente HTTP (com pool de conexões) por processo do Streamlit."""
    return ApiClient(get_settings())


def current_session_id() -> Optional[str]:
    return st.session_state.get(SID_KEY)


def xrays() -> dict[int, dict]:
    return st.session_state.setdefault(XRAYS_KEY, {})


def start_new_session(client: ApiClient) -> str:
    """Cria uma sessão NOVA no backend (POST /sessions) e passa a apontar para ela."""
    data = client.create_session()
    sid = data["session_id"]
    st.session_state[SID_KEY] = sid
    st.session_state[XRAYS_KEY] = {}
    st.query_params["sid"] = sid
    return sid


def ensure_session(client: ApiClient) -> str:
    """Garante um session_id válido: reaproveita o da tela, depois o da URL (F5); senão cria. Levanta ApiError."""
    sid = current_session_id()
    if sid:
        return sid
    from_url = st.query_params.get("sid")
    if from_url:
        try:
            client.get_session(from_url)            # a sessão ainda existe no servidor?
            st.session_state[SID_KEY] = from_url
            st.session_state[XRAYS_KEY] = {}
            return from_url
        except ApiError as err:
            if not err.is_session_lost:
                raise
    return start_new_session(client)


def queue_prompt(text: str) -> None:
    """Callback dos botões de sugestão: guarda o texto para a página enviá-lo como se o usuário o tivesse digitado."""
    st.session_state[QUEUED_KEY] = text


def pop_queued_prompt() -> Optional[str]:
    return st.session_state.pop(QUEUED_KEY, None)


def forget_session() -> None:
    st.session_state.pop(SID_KEY, None)
    st.session_state.pop(XRAYS_KEY, None)
    st.session_state.pop(QUEUED_KEY, None)
    if "sid" in st.query_params:
        del st.query_params["sid"]
