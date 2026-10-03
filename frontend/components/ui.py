"""Pequenos utilitários de apresentação compartilhados pelas páginas."""
from __future__ import annotations

import streamlit as st

from services.api_client import ApiError, ErrorKind

SENTIMENT_EMOJI = {"positivo": "😊", "neutro": "😐", "negativo": "😟"}
SENTIMENT_TONE = {"positivo": "ok", "neutro": "neutral", "negativo": "danger"}
SOURCE_LABEL = {
    "template": "Template (regra)",
    "llm": "LLM (validado pelo guardrail)",
    "template_guardrail": "Template (LLM rejeitado pelo guardrail)",
    "template_degraded": "Template (LLM fora do ar)",
}
ERROR_ICON = {
    ErrorKind.OFFLINE: "🔌", ErrorKind.TIMEOUT: "⏳", ErrorKind.LLM_UNAVAILABLE: "🤖",
    ErrorKind.UNAUTHORIZED: "🔑", ErrorKind.NOT_FOUND: "🔎", ErrorKind.VALIDATION: "✏️",
}


def safe_md(text: str) -> str:
    """Prepara o texto do bot para o st.markdown: escapa `$` (R$ viraria LaTeX) e preserva quebras de linha."""
    return (text or "").replace("$", "\\$").replace("\n", "  \n")


def show_api_error(err: ApiError, *, container=None) -> None:
    """Mostra o erro de forma amigável (mensagem + dica técnica em letra menor), sem traceback."""
    box = container or st
    box.error(f"{ERROR_ICON.get(err.kind, '⚠️')} {err.message}")
    if err.retry_after:
        box.caption(f"Tente novamente em ~{err.retry_after} s.")
    if err.hint:
        box.caption(err.hint)


def turn_caption(xray: dict) -> str:
    s = xray.get("sentiment", {})
    parts = [
        f"🎯 {xray.get('intent', '?')}",
        f"{SENTIMENT_EMOJI.get(s.get('label'), '')} {s.get('label', '')}".strip(),
        f"⏱ {xray.get('latency_ms', 0)} ms",
        SOURCE_LABEL.get(xray.get("source", ""), xray.get("source", "")),
    ]
    if xray.get("fallback"):
        parts.append("↩️ fallback")
    if xray.get("handoff", {}).get("active"):
        parts.append("🙋 handoff")
    return " · ".join(p for p in parts if p)
