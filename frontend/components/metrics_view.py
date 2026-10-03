"""Painel de métricas: tudo lido de GET /metrics (calculado pelo backend a partir do log por turno)."""
from __future__ import annotations

from typing import Optional

import streamlit as st

from components.theme import ACCENT, INK, PRIMARY, esc, render, section

DANGER = "#DC2626"
SENTIMENT_COLORS = {"positivo": "#16A34A", "neutro": "#94A3B8", "negativo": DANGER}

DEFINITIONS = """
| Métrica | Definição |
|---|---|
| **Taxa de contenção** | conversas encerradas **sem handoff** ÷ total de conversas |
| **Taxa de fallback** | turnos do usuário que caíram em fallback ÷ total de turnos do usuário |
| **Taxa de handoff** | conversas **com handoff** ÷ total de conversas |
| **Mensagens por conversa** | média de turnos do usuário por sessão |
| **Taxa de resolução** | conversas contidas **e** com objetivo cumprido (agendou ou teve a FAQ respondida) |
| **Latência média / p95** | tempo de resposta por turno; p95 = 95% dos turnos foram mais rápidos que isso |

Todas saem do **log por turno** (`turns.jsonl`) calculado pelo backend em `GET /metrics`; esta tela só exibe.
"""


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%".replace(".", ",")


def _ms(x: int) -> str:
    return f"{x / 1000:.1f} s".replace(".", ",")


def _note(text: str) -> None:
    render(f'<div class="pb-kpi-note">{esc(text)}</div>')


def _bar_html(data: dict, color: str, colors: Optional[dict]) -> None:
    """Barras em HTML/CSS puro: plano B quando pandas/altair não carregam (ex.: política de controle de aplicativo
    do Windows bloqueando a DLL do pandas). Mesmo dado, mesmo visual aproximado, zero dependência nativa."""
    top = max(data.values()) or 1
    rows = []
    for name, value in sorted(data.items(), key=lambda kv: kv[1], reverse=True):
        width = max(2.0, 100.0 * value / top)
        fill = (colors or {}).get(name, color)
        rows.append(
            '<div style="display:flex;align-items:center;gap:.6rem;margin:.28rem 0;">'
            f'<div style="flex:0 0 38%;font-size:.85rem;color:{INK};overflow:hidden;text-overflow:ellipsis;'
            f'white-space:nowrap;" title="{esc(str(name))}">{esc(str(name))}</div>'
            '<div style="flex:1;display:flex;align-items:center;gap:.4rem;">'
            f'<div style="height:18px;width:{width:.1f}%;background:{fill};border-radius:0 5px 5px 0;"></div>'
            f'<span style="font-weight:700;color:{INK};font-size:.85rem;">{esc(str(value))}</span></div></div>')
    render("".join(rows))


def _bar(title: str, data: dict, *, color: str = PRIMARY, colors: Optional[dict] = None,
         empty_msg: str = "Sem dados ainda.") -> None:
    """Barras horizontais ordenadas, com o valor na ponta de cada barra."""
    st.markdown(f"**{title}**")
    if not data:
        st.caption(empty_msg)
        return
    try:  # pandas/altair só são carregados aqui: se falharem, a página inteira continua funcionando
        import altair as alt
        import pandas as pd
    except ImportError:
        _bar_html(data, color, colors)
        return
    df = pd.DataFrame({"categoria": list(data), "turnos": list(data.values())}).sort_values("turnos", ascending=False)
    base = alt.Chart(df).encode(
        y=alt.Y("categoria:N", sort="-x", title=None, axis=alt.Axis(labelLimit=280, labelColor=INK, ticks=False, domain=False)),
        x=alt.X("turnos:Q", title=None, axis=alt.Axis(tickMinStep=1, grid=True, gridColor="#E2ECE9", domain=False, labels=False, ticks=False)),
    )
    if colors:
        bars = base.mark_bar(cornerRadiusEnd=5, size=20).encode(
            color=alt.Color("categoria:N", legend=None,
                            scale=alt.Scale(domain=list(colors), range=list(colors.values()))))
    else:
        bars = base.mark_bar(cornerRadiusEnd=5, size=20, color=color)
    labels = base.mark_text(align="left", dx=5, color=INK, fontWeight="bold").encode(text="turnos:Q")
    chart = (bars + labels).properties(height=max(70, 32 * len(df) + 16)).configure_view(strokeWidth=0)
    st.altair_chart(chart)


def _insights(m: dict) -> list[str]:
    out = []
    if m["total_conversas"]:
        gap = m["taxa_contencao"] - m["taxa_resolucao"]
        out.append(f"**Contenção × resolução:** {_pct(m['taxa_contencao'])} das conversas não chamaram humano, mas só "
                   f"{_pct(m['taxa_resolucao'])} cumpriram o objetivo (agendar ou ter a FAQ respondida): "
                   f"{gap * 100:.0f} p.p. de conversas “contidas” não resolveram nada.")
    fonte = m.get("fonte_da_resposta", {})
    llm_calls = fonte.get("llm", 0) + fonte.get("template_guardrail", 0)
    if llm_calls:
        rej = fonte.get("template_guardrail", 0)
        out.append(f"**Guardrail de saída:** rejeitou {rej} de {llm_calls} respostas do LLM ({_pct(rej / llm_calls)}), "
                   "que foram trocadas pelo texto-base curado.")
    if m["fallback_por_tipo"]:
        tipo, n = max(m["fallback_por_tipo"].items(), key=lambda kv: kv[1])
        out.append(f"**Fallback mais comum:** `{tipo}` ({n} de {sum(m['fallback_por_tipo'].values())}).")
    if m["handoff_por_motivo"]:
        motivo, n = max(m["handoff_por_motivo"].items(), key=lambda kv: kv[1])
        out.append(f"**Motivo de handoff mais comum:** `{motivo}` ({n} de {sum(m['handoff_por_motivo'].values())}).")
    return out


def render_metrics(m: dict) -> None:
    periodo = m.get("periodo") or {}
    if not m["total_conversas"]:
        st.info("Ainda não há conversas no log. Converse com a Duda e volte aqui, ou rode "
                "`python backend/scripts/run_scenarios.py` para gerar a amostra de T1–T8 + 16 conversas.")
        return
    total, turnos = m["total_conversas"], m["total_turnos_usuario"]
    st.caption(f"Período do log: {periodo.get('inicio') or '—'} → {periodo.get('fim') or '—'} · "
               f"{total} conversas · {turnos} turnos do usuário")

    section("Indicadores principais")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Taxa de contenção", _pct(m["taxa_contencao"]), help="conversas sem handoff ÷ total de conversas")
    with c1:
        _note(f"{round(total * (1 - m['taxa_handoff']))} de {total} conversas sem handoff")
    c2.metric("Taxa de fallback", _pct(m["taxa_fallback"]), help="turnos em fallback ÷ turnos do usuário")
    with c2:
        _note(f"{round(turnos * m['taxa_fallback'])} de {turnos} turnos do usuário")
    c3.metric("Taxa de handoff", _pct(m["taxa_handoff"]), help="conversas com handoff ÷ total de conversas")
    with c3:
        _note(f"{round(total * m['taxa_handoff'])} de {total} conversas")
    c4.metric("Mensagens por conversa", f"{m['mensagens_por_conversa']:.2f}".replace(".", ","),
              help="média de turnos do usuário por sessão")
    with c4:
        _note(f"{turnos} turnos em {total} conversas")

    section("Qualidade e desempenho")
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Taxa de resolução", _pct(m["taxa_resolucao"]), help="contida e com objetivo cumprido")
    c6.metric("Agendamentos concluídos", m["agendamentos_concluidos"],
              help=f"conclusão sobre fluxos iniciados: {_pct(m['taxa_conclusao_agendamento'])}")
    c7.metric("Latência média", _ms(m["latencia_media_ms"]))
    c8.metric("Latência p95", _ms(m["latencia_p95_ms"]))

    if m["total_feedbacks"]:
        f1, f2, f3 = st.columns(3)
        fmt = lambda v: "—" if v is None else f"{v:.2f}".replace(".", ",")
        f1.metric("CSAT médio", fmt(m["csat_medio"]), help=f"{m['total_feedbacks']} avaliações")
        f2.metric("CSAT · conversas contidas", fmt(m["csat_medio_conversas_contidas"]))
        f3.metric("CSAT · conversas transferidas", fmt(m["csat_medio_conversas_transferidas"]))

    section("💡 Leitura rápida")
    for line in _insights(m):
        st.info(line, icon="💡")

    section("Distribuições")
    tab_conv, tab_qual, tab_aten = st.tabs(["Conversa", "Qualidade do bot", "Atendimento"])
    with tab_conv:
        a, b = st.columns(2)
        with a:
            _bar("Intenções", m["distribuicao_intencoes"])
            _bar("Fallback por tipo", m["fallback_por_tipo"], color=ACCENT, empty_msg="Nenhum fallback no período.")
        with b:
            _bar("Sentimento", m["distribuicao_sentimento"], colors=SENTIMENT_COLORS)
    with tab_qual:
        a, b = st.columns(2)
        with a:
            _bar("Origem da resposta", m["fonte_da_resposta"])
            _bar("Erros de validação de slots", m["erros_validacao"], color=ACCENT, empty_msg="Nenhum erro de validação.")
        with b:
            _bar("Eventos de guardrail (etapa:nome)", m["eventos_guardrail"], color=ACCENT,
                 empty_msg="Nenhum guardrail acionado.")
        st.caption(f"Turnos em que o sentimento negativo mudou o tom do bot (acolhimento): "
                   f"**{m['turnos_com_tom_de_acolhimento']}**")
    with tab_aten:
        a, b = st.columns(2)
        with a:
            _bar("Handoff por motivo", m["handoff_por_motivo"], color=DANGER, empty_msg="Nenhum handoff no período.")
        with b:
            _bar("FAQ mais consultadas", m["faq_mais_consultadas"], empty_msg="Nenhuma FAQ consultada.")

    with st.expander("ℹ️ Como cada métrica é calculada"):
        st.markdown(DEFINITIONS)