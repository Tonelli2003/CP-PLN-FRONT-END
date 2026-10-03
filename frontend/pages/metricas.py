"""Página de MÉTRICAS: lê GET /metrics (calculadas pelo backend a partir do log por turno)."""
from __future__ import annotations

import streamlit as st

from components import state
from components.metrics_view import render_metrics
from components.sidebar import render_api_status
from components.theme import hero
from components.ui import show_api_error
from services.api_client import ApiError

client = state.get_client()
api_up = render_api_status(client)

hero("📊", "Métricas conversacionais", "Lidas de GET /metrics: o backend calcula tudo a partir do log por turno; esta tela só exibe.",
     ["Contenção", "Fallback", "Handoff", "Mensagens por conversa"])

if st.button("🔄 Atualizar métricas"):
    st.rerun()

if not api_up:
    st.error("🔌 Não consigo ler as métricas porque o serviço está indisponível. Veja o aviso na barra lateral.")
    st.stop()

try:
    with st.spinner("Carregando métricas…"):
        metrics = client.get_metrics()
except ApiError as err:
    show_api_error(err)
    st.stop()

render_metrics(metrics)
