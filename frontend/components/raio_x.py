"""Painel Raio-X: o que o cérebro "pensou" no último turno e o estado atual da conversa no servidor."""
from __future__ import annotations

from typing import Optional

import streamlit as st

from components.theme import card, chip, chips, esc, render, row
from components.ui import SENTIMENT_EMOJI, SENTIMENT_TONE, SOURCE_LABEL
from config import get_settings

SLOT_LABELS = [("nome_tutor", "Tutor"), ("nome_pet", "Pet"), ("especie", "Espécie"),
               ("data", "Data"), ("horario", "Horário"), ("email", "E-mail")]
AWAITING_LABEL = {"nome_tutor": "nome do tutor", "nome_pet": "nome do pet", "especie": "espécie", "data": "data",
                  "horario": "horário", "email": "e-mail", "confirmar": "confirmação", "confirmacao": "confirmação"}


def _slots_block(slots: dict, awaiting: Optional[str]) -> None:
    filled = sum(1 for key, _ in SLOT_LABELS if slots.get(key))
    total = len(SLOT_LABELS)
    pct = round(100 * filled / total)
    lines = []
    for key, label in SLOT_LABELS:
        value = slots.get(key)
        if value:
            state, mark, shown = "done", "✓", esc(value)
        elif awaiting == key:
            state, mark, shown = "wait", "", "esperando agora…"
        else:
            state, mark, shown = "todo", "", "—"
        lines.append(f'<div class="pb-slot {state}"><span class="dot">{mark}</span><span class="lbl">{esc(label)}</span>'
                     f'<span class="val">{shown}</span></div>')
    body = (f'<div class="pb-progress"><div class="pb-bar"><span style="width:{pct}%"></span></div>'
            f'<b>{filled}/{total}</b></div>' + "".join(lines))
    render(card("🧩 Slots · estado no servidor", body))


def _handoff_block(handoff: dict) -> None:
    if not handoff.get("active"):
        render(card("🙋 Handoff", chips([chip("● inativo", "ok")]) +
                    '<div class="pb-note">A conversa segue com a Duda.</div>'))
        return
    tone = "danger" if handoff.get("priority") == "alta" else "warn"
    body = (chips([chip("● ATIVO", tone), chip(f"prioridade {handoff.get('priority')}", tone)]) +
            row("Protocolo", esc(handoff.get("protocol"))) + row("Motivo", esc(handoff.get("reason"))))
    render(card("🙋 Handoff", body))
    summary = handoff.get("summary")
    if summary:
        with st.expander("Resumo estruturado para o atendente", expanded=False):
            st.markdown(f"**Motivo:** {summary['motivo']}  \n**Intenção:** {summary['intencao']}  \n"
                        f"**Relato:** {summary['relato']}")
            if summary.get("dados_coletados"):
                st.markdown("**Dados coletados:**")
                st.json(summary["dados_coletados"], expanded=False)
            if summary.get("pendencias_do_agendamento"):
                st.markdown("**Pendências:** " + ", ".join(summary["pendencias_do_agendamento"]))
            st.markdown("**Ações já realizadas:**\n" + "\n".join(f"- {a}" for a in summary["acoes_realizadas"]))
            st.caption(f"Sentimento: {summary['sentimento'].get('label')} · "
                       f"{summary['turnos_do_usuario']} turno(s) do usuário")


def _turn_block(xray: Optional[dict]) -> None:
    if not xray:
        st.info("Envie uma mensagem para ver a intenção, o sentimento e a origem da resposta.")
        return
    sent = xray["sentiment"]
    flow = xray["flow"]
    awaiting = AWAITING_LABEL.get(flow.get("awaiting") or "", flow.get("awaiting") or "—")
    top = [
        chip(f"🎯 {xray['intent']} · {xray['intent_confidence']:.0%}", "info"),
        chip(f"{SENTIMENT_EMOJI.get(sent['label'], '')} {sent['label']} · {sent['polarity']:+.2f}",
             SENTIMENT_TONE.get(sent["label"], "neutral")),
        chip(SOURCE_LABEL.get(xray["source"], xray["source"]), "neutral"),
    ]
    if xray["fallback"]:
        top.append(chip(f"↩️ fallback · {xray.get('fallback_type') or '—'}", "warn"))
    body = chips(top)
    body += row("Fluxo", esc(flow["state"])) + row("Esperando", esc(awaiting))
    body += row("LLM usado", "sim" if xray["llm_used"] else "não")
    body += row("Latência", f"{esc(xray['latency_ms'])} ms · turno {esc(xray['turn'])}")
    events = xray.get("guardrail_events") or []
    if events:
        body += '<div class="pb-card-title" style="margin-top:.7rem">🛡️ Guardrails acionados</div>'
        body += "".join(row(f"{e['stage']}:{e['name']}", esc(e["action"] + (f" ({e['detail']})" if e.get("detail") else "")))
                        for e in events)
    else:
        body += row("Guardrails", chip("nenhum acionado", "ok"))
    render(card("🔬 Último turno", body))


def _server_block(detail: dict) -> None:
    st.caption(f"Situação: **{detail['status']}** · turnos do usuário: **{detail['turn']}** · criada em {detail['created_at']}")
    if detail.get("booking"):
        st.success("Agendamento concluído")
        st.json(detail["booking"], expanded=False)
    st.markdown("Resposta crua de `GET /sessions/{id}` (a verdade fica no servidor):")
    st.json(detail, expanded=False)
    st.info("**Teste T8:** abra o /docs, rode `POST /chat` com **este mesmo session_id** e clique em "
            "**Atualizar** abaixo: a mensagem aparece aqui, porque o estado está no cérebro, não na tela.")
    c1, c2 = st.columns(2)
    c1.link_button("📖 Abrir /docs", get_settings().docs_url)
    if c2.button("🔄 Atualizar", key="refresh_state"):
        st.rerun()


def render_raio_x(detail: dict, xray: Optional[dict]) -> None:
    st.subheader("Raio-X")
    tab_turn, tab_server = st.tabs(["Turno", "Estado no servidor"])
    with tab_turn:
        _turn_block(xray)
        _slots_block(detail["slots"], detail["flow"].get("awaiting"))
        _handoff_block(detail["handoff"])
    with tab_server:
        _server_block(detail)
