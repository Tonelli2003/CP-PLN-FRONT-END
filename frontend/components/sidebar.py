"""Barra lateral: marca, estado da API, nova conversa, id da sessão, apagar (LGPD) e nota CSAT."""
from __future__ import annotations

import time
from typing import Optional

import streamlit as st

from components import state
from components.theme import chip, esc, render
from components.ui import show_api_error
from config import get_settings
from services.api_client import ApiClient, ApiError

_HEALTH_TTL_S = 10


def _brand() -> None:
    render('<div class="pb-brand"><div class="pb-brand-logo">🐾</div><div><div class="pb-brand-name">Prosa Bot</div>'
           '<div class="pb-brand-sub">Bot como serviço · lente Streamlit</div></div></div>', container=st.sidebar)


def render_api_status(client: ApiClient) -> bool:
    """Mostra o estado da API (GET /health) e devolve True se ela respondeu. Consulta no máx. a cada 10 s."""
    _brand()
    cached = st.session_state.get("_health")
    if cached and time.time() - cached["at"] < _HEALTH_TTL_S and not cached.get("error"):
        data, err = cached["data"], None
    else:
        try:
            data, err = client.health(), None
        except ApiError as e:
            data, err = None, e
        st.session_state["_health"] = {"at": time.time(), "data": data, "error": err is not None}

    box = st.sidebar.container()
    if err is not None:
        render(chip("● API offline", "danger"), container=box)
        show_api_error(err, container=box)
        if box.button("🔄 Tentar novamente", key="retry_health"):
            st.session_state.pop("_health", None)
            st.rerun()
        box.caption(f"API_URL: {get_settings().api_url}")
        return False

    llm = data["llm"]
    model = f"{llm['provider']} / {llm['model']}"
    if data["status"] == "ok":
        render(chip("● API online", "ok") + f'<div class="pb-note">Modelo: {esc(model)}</div>', container=box)
    else:
        render(chip("● API online · modelo indisponível", "warn") + f'<div class="pb-note">Modelo: {esc(model)}</div>',
               container=box)
        box.caption("Turnos críticos (emergência, handoff, fallback) continuam funcionando.")
        if llm.get("detail"):
            box.caption(llm["detail"])
    return True


def render_session_controls(client: ApiClient, sid: Optional[str]) -> None:
    """Nova conversa, id da sessão (para o T8 no /docs), apagar e CSAT."""
    sb = st.sidebar
    sb.divider()
    if sb.button("➕ Nova conversa", type="primary", key="new_chat"):
        try:
            state.start_new_session(client)
        except ApiError as err:
            show_api_error(err, container=sb)
        else:
            st.rerun()
    if not sid:
        return

    with sb.expander("🔬 Sessão e API (teste T8)"):
        st.caption("ID da sessão: use-o no /docs para provar que o estado vive no servidor.")
        st.code(sid, language=None)
        st.link_button("📖 Abrir /docs da API", get_settings().docs_url)

    sb.divider()
    sb.markdown("**Avalie esta conversa (CSAT)**")
    sent = st.session_state.setdefault(state.FEEDBACK_SENT_KEY, set())
    if sid in sent:
        sb.caption("✅ Avaliação enviada. Obrigado!")
    else:
        stars = sb.feedback("stars", key=f"stars_{sid}")
        if sb.button("Enviar avaliação", key=f"send_fb_{sid}", disabled=stars is None):
            try:
                client.send_feedback(sid, int(stars) + 1)
            except ApiError as err:
                show_api_error(err, container=sb)
            else:
                sent.add(sid)
                st.rerun()

    sb.divider()
    if sb.button("🗑️ Apagar esta conversa (LGPD)", key="delete_chat",
                 help="DELETE /sessions/{id}: apaga o histórico e anonimiza o log."):
        try:
            client.delete_session(sid)
        except ApiError as err:
            if not err.is_session_lost:
                show_api_error(err, container=sb)
                return
        state.forget_session()
        st.toast("Conversa apagada. Começando uma nova.", icon="🗑️")
        st.rerun()
