"""Identidade visual do frontend: paleta, CSS global e pequenos blocos HTML (hero, chips, cards).

Só apresentação: nada aqui fala com a API. Todo texto dinâmico que entra em HTML passa por `esc()` (o conteúdo vem
do usuário e do backend; nunca é confiável) e o `$` vira entidade para o Markdown do Streamlit não tratá-lo como LaTeX.
"""
from __future__ import annotations

import html
from typing import Iterable

import streamlit as st

# --- paleta (a mesma do .streamlit/config.toml) --------------------------------------------------------------------
PRIMARY = "#0F766E"
DEEP = "#134E4A"
INK = "#10302B"
MUTED = "#5B7470"
ACCENT = "#F59E0B"

CSS = """
:root{--pb-primary:#0F766E;--pb-deep:#134E4A;--pb-ink:#10302B;--pb-muted:#5B7470;--pb-accent:#F59E0B;
      --pb-line:rgba(15,118,110,.18);--pb-soft:#EAF4F1;--pb-card:#FFFFFF;}

/* layout geral */
.block-container{padding-top:2.4rem;padding-bottom:3rem;max-width:1440px;}
footer{visibility:hidden;}
h1,h2,h3{color:var(--pb-deep);letter-spacing:-.01em;}

/* hero */
.pb-hero{background:linear-gradient(120deg,#0F766E 0%,#115E59 55%,#134E4A 100%);color:#fff;border-radius:18px;
         padding:1.15rem 1.5rem 1.2rem;margin:0 0 1.1rem;box-shadow:0 10px 28px rgba(15,118,110,.22);}
.pb-hero-row{display:flex;align-items:center;gap:.9rem;}
.pb-hero-logo{font-size:2rem;line-height:1;background:rgba(255,255,255,.16);border-radius:14px;padding:.55rem .65rem;}
.pb-hero-title{font-size:1.45rem;font-weight:800;line-height:1.2;letter-spacing:-.01em;}
.pb-hero-sub{font-size:.95rem;opacity:.9;margin-top:.15rem;}
.pb-hero-chips{margin-top:.75rem;display:flex;flex-wrap:wrap;gap:.4rem;}

/* chips */
.pb-chip{display:inline-flex;align-items:center;gap:.3rem;padding:.12rem .62rem;border-radius:999px;font-size:.78rem;
         font-weight:650;line-height:1.55;border:1px solid transparent;white-space:nowrap;}
.pb-chip.neutral{color:#334155;background:#F1F5F9;border-color:#E2E8F0;}
.pb-chip.info{color:#075985;background:#E0F2FE;border-color:#BAE6FD;}
.pb-chip.ok{color:#166534;background:#DCFCE7;border-color:#BBF7D0;}
.pb-chip.warn{color:#92400E;background:#FEF3C7;border-color:#FDE68A;}
.pb-chip.danger{color:#991B1B;background:#FEE2E2;border-color:#FECACA;}
.pb-chip.dark{color:#fff;background:rgba(255,255,255,.16);border-color:rgba(255,255,255,.3);}
.pb-chips{display:flex;flex-wrap:wrap;gap:.4rem;margin-bottom:.6rem;}

/* cards do raio-X */
.pb-card{background:var(--pb-card);border:1px solid var(--pb-line);border-radius:14px;padding:.85rem 1rem .75rem;
         margin-bottom:.8rem;box-shadow:0 1px 2px rgba(16,48,43,.05);}
.pb-card-title{font-size:.72rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--pb-muted);
               margin-bottom:.6rem;}
.pb-row{display:flex;justify-content:space-between;align-items:baseline;gap:.75rem;padding:.3rem 0;
        border-bottom:1px dashed rgba(15,118,110,.16);font-size:.88rem;}
.pb-row:last-child{border-bottom:0;}
.pb-row .k{color:var(--pb-muted);}
.pb-row .v{font-weight:650;color:var(--pb-ink);text-align:right;}
.pb-note{font-size:.82rem;color:var(--pb-muted);margin:.2rem 0 0;}

/* slots */
.pb-progress{display:flex;align-items:center;gap:.7rem;margin-bottom:.45rem;}
.pb-bar{flex:1;height:8px;border-radius:99px;background:rgba(15,118,110,.14);overflow:hidden;}
.pb-bar>span{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#14B8A6,#0F766E);}
.pb-progress b{font-size:.85rem;color:var(--pb-deep);min-width:2.6rem;text-align:right;}
.pb-slot{display:flex;align-items:center;gap:.6rem;padding:.28rem 0;font-size:.9rem;color:var(--pb-ink);}
.pb-slot .dot{width:19px;height:19px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;
              font-size:.68rem;font-weight:800;flex:none;}
.pb-slot.done .dot{background:var(--pb-primary);color:#fff;}
.pb-slot.todo .dot{border:2px solid rgba(15,118,110,.28);}
.pb-slot.todo{color:var(--pb-muted);}
.pb-slot.wait .dot{border:2px solid var(--pb-accent);background:#FEF3C7;}
.pb-slot .lbl{min-width:4.8rem;color:var(--pb-muted);}
.pb-slot .val{font-weight:650;}

/* chat */
[data-testid="stChatMessage"]{border-radius:14px;padding:.7rem .95rem;border:1px solid rgba(15,118,110,.10);
                              background:#FFFFFF;margin-bottom:.35rem;}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]){background:var(--pb-soft);}
[data-testid="stChatInput"]{border-radius:14px;}
.pb-welcome{background:var(--pb-soft);border:1px dashed rgba(15,118,110,.35);border-radius:14px;padding:.8rem 1rem;
            margin:.4rem 0 .6rem;color:var(--pb-ink);font-size:.92rem;}

/* métricas */
[data-testid="stMetric"]{background:#FFFFFF;border:1px solid var(--pb-line);border-radius:14px;padding:.8rem 1rem;
                         box-shadow:0 1px 2px rgba(16,48,43,.05);}
[data-testid="stMetricLabel"]{color:var(--pb-muted);}
[data-testid="stMetricValue"]{color:var(--pb-deep);font-weight:800;}
.pb-kpi-note{font-size:.78rem;color:var(--pb-muted);margin:-.35rem 0 .6rem .2rem;}
.pb-section{font-size:.74rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--pb-muted);
            margin:1.1rem 0 .5rem;}

/* controles */
.stButton>button,.stDownloadButton>button,[data-testid="stLinkButton"] a{border-radius:10px;font-weight:650;}
button[data-baseweb="tab"]{font-weight:650;}
[data-testid="stExpander"]{border-radius:12px;border-color:var(--pb-line);background:#FFFFFF;}
.st-key-suggestions .stButton>button{width:100%;text-align:left;justify-content:flex-start;background:#FFFFFF;
                                     border:1px solid var(--pb-line);}
.st-key-suggestions .stButton>button:hover{border-color:var(--pb-primary);color:var(--pb-primary);}

/* barra lateral */
section[data-testid="stSidebar"]{border-right:1px solid var(--pb-line);}
.pb-brand{display:flex;align-items:center;gap:.65rem;margin:.2rem 0 .8rem;}
.pb-brand-logo{font-size:1.5rem;background:var(--pb-primary);border-radius:12px;padding:.35rem .5rem;line-height:1;}
.pb-brand-name{font-weight:800;color:var(--pb-deep);line-height:1.15;}
.pb-brand-sub{font-size:.76rem;color:var(--pb-muted);}
"""


def apply_theme() -> None:
    """Injeta o CSS global. `st.html` só com <style> não ocupa espaço na página."""
    st.html(f"<style>{CSS}</style>")


# --- blocos HTML ----------------------------------------------------------------------------------------------------
def esc(value) -> str:
    """Escapa para HTML e neutraliza `$` (o Markdown do Streamlit transformaria `R$ ... R$` em LaTeX)."""
    return html.escape("" if value is None else str(value), quote=True).replace("$", "&#36;")


def chip(text, tone: str = "neutral") -> str:
    return f'<span class="pb-chip {esc(tone)}">{esc(text)}</span>'


def chips(items: Iterable[str]) -> str:
    return '<div class="pb-chips">' + "".join(items) + "</div>"


def row(label, value_html: str) -> str:
    """Linha chave/valor. `value_html` já deve estar escapado (use `esc`)."""
    return f'<div class="pb-row"><span class="k">{esc(label)}</span><span class="v">{value_html}</span></div>'


def card(title: str, body_html: str) -> str:
    return f'<div class="pb-card"><div class="pb-card-title">{esc(title)}</div>{body_html}</div>'


def render(html_str: str, *, container=None) -> None:
    """Desenha um bloco HTML já montado (sem quebras de linha: o Markdown trataria linhas indentadas como código)."""
    (container or st).markdown(html_str, unsafe_allow_html=True)


def hero(icon: str, title: str, subtitle: str, badges: Iterable[str] = ()) -> None:
    badge_html = "".join(chip(b, "dark") for b in badges)
    chips_html = f'<div class="pb-hero-chips">{badge_html}</div>' if badge_html else ""
    render(f'<div class="pb-hero"><div class="pb-hero-row"><div class="pb-hero-logo">{esc(icon)}</div>'
           f'<div><div class="pb-hero-title">{esc(title)}</div><div class="pb-hero-sub">{esc(subtitle)}</div></div></div>'
           f'{chips_html}</div>')


def section(title: str) -> None:
    render(f'<div class="pb-section">{esc(title)}</div>')
