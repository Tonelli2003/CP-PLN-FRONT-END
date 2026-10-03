"""SEGUNDA LENTE: painel do atendente (Gradio, porta 7860), consumindo GET /handoffs e GET /sessions/{id}.

É outra aplicação, em outro processo, que fala com o MESMO cérebro pela MESMA API: a prova de que o canal é só uma
lente. Reaproveita apenas o módulo cliente (services/api_client.py); não importa nada do backend.

Executar (dentro de frontend/):  python painel_atendente.py
"""
from __future__ import annotations

import gradio as gr

from config import get_settings
from services.api_client import ApiClient, ApiError

client = ApiClient(get_settings())

# Mesma identidade visual do chat (Streamlit). Não passe `font=[...]` com strings: o launch() do Gradio compara a
# lista com a do tema padrão e quebra com AttributeError.
THEME = gr.themes.Soft(primary_hue="teal", secondary_hue="emerald", neutral_hue="slate")
CSS = """
.pb-hero{background:linear-gradient(120deg,#0F766E 0%,#115E59 55%,#134E4A 100%);color:#fff;border-radius:18px;
         padding:1.1rem 1.5rem;margin-bottom:.6rem;box-shadow:0 10px 28px rgba(15,118,110,.22);}
.pb-hero-row{display:flex;align-items:center;gap:.9rem;}
.pb-hero-logo{font-size:2rem;line-height:1;background:rgba(255,255,255,.16);border-radius:14px;padding:.55rem .65rem;}
.pb-hero-title{font-size:1.45rem;font-weight:800;line-height:1.2;}
.pb-hero-sub{font-size:.95rem;opacity:.9;margin-top:.15rem;}
"""
HERO = ('<div class="pb-hero"><div class="pb-hero-row"><div class="pb-hero-logo">🙋</div><div>'
        '<div class="pb-hero-title">Painel do atendente · Prosa</div>'
        '<div class="pb-hero-sub">Segunda <i>lente</i> do mesmo bot: lê <code>GET /handoffs</code> (urgentes primeiro) '
        'e a transcrição de cada conversa por <code>GET /sessions/{id}</code>.</div></div></div></div>')
PRIORITY_ICON = {"alta": "🔴 alta", "normal": "🟡 normal"}
HEADERS = ["Prioridade", "Protocolo", "Motivo", "Criado em", "Sessão", "Msgs após transferência"]


def _label(item: dict) -> str:
    return f"{PRIORITY_ICON.get(item['priority'], item['priority'])} · {item['protocol']} · {item['reason']}"


def _status_ok(n: int) -> str:
    return f"✅ API online · **{n}** atendimento(s) na fila" if n else "✅ API online · fila vazia"


def load_queue(current=None):
    """Busca a fila e devolve (status, tabela, dropdown, estado). Mantém o atendimento selecionado, se ele ainda
    está na fila. Erros viram mensagem, nunca traceback."""
    try:
        items = client.list_handoffs()
    except ApiError as err:
        hint = f"\n\n_{err.hint}_" if err.hint else ""
        return (f"⚠️ {err.message}{hint}", [], gr.update(choices=[], value=None), [])
    rows = [[PRIORITY_ICON.get(i["priority"], i["priority"]), i["protocol"], i["reason"], i["created_at"],
             i["session_id"], len(i.get("notes", []))] for i in items]
    choices = [(_label(i), i["session_id"]) for i in items]
    ids = [c[1] for c in choices]
    value = current if current in ids else (ids[0] if ids else None)
    return _status_ok(len(items)), rows, gr.update(choices=choices, value=value), items


def _summary_md(item: dict) -> str:
    s = item["summary"]
    dados = "\n".join(f"- **{k}:** {v}" for k, v in s["dados_coletados"].items()) or "- _nenhum dado coletado_"
    pend = ", ".join(s["pendencias_do_agendamento"]) or "—"
    acoes = "\n".join(f"- {a}" for a in s["acoes_realizadas"]) or "- —"
    notes = "\n".join(f"- {n}" for n in item.get("notes", [])) or "- _nenhuma_"
    return (f"## {PRIORITY_ICON.get(item['priority'], item['priority'])} · Protocolo {item['protocol']}\n"
            f"**Motivo:** {s['motivo']}  \n**Intenção:** {s['intencao']}  \n**Criado em:** {s['criado_em']}  \n"
            f"**Sentimento:** {s['sentimento'].get('label')} (polaridade {s['sentimento'].get('polaridade')})  \n"
            f"**Turnos do usuário:** {s['turnos_do_usuario']}\n\n"
            f"### Relato do cliente\n> {s['relato']}\n\n### Dados coletados\n{dados}\n\n"
            f"**Pendências do agendamento:** {pend}\n\n### Ações já realizadas\n{acoes}\n\n"
            f"### Mensagens enviadas após a transferência\n{notes}")


def show_case(session_id, items):
    """Detalha o atendimento escolhido: resumo estruturado (da fila) + transcrição (GET /sessions/{id})."""
    item = next((i for i in items or [] if i["session_id"] == session_id), None)
    if item is None:
        return "_Selecione um atendimento._", []
    chat: list = []
    try:
        for m in client.get_session(session_id)["history"]:
            chat.append({"role": m["role"], "content": m["content"]})
    except ApiError as err:
        return _summary_md(item) + f"\n\n⚠️ Não foi possível carregar a transcrição: {err.message}", []
    return _summary_md(item), chat


def build() -> gr.Blocks:
    with gr.Blocks(title="Painel do atendente · Prosa") as demo:
        gr.HTML(HERO)
        items_state = gr.State([])
        status = gr.Markdown("Carregando…")
        with gr.Row():
            refresh = gr.Button("🔄 Atualizar fila", variant="primary")
            auto = gr.Checkbox(label="Atualizar sozinho a cada 5 s", value=True)
        queue = gr.Dataframe(headers=HEADERS, interactive=False, label="Fila de transferências")
        case = gr.Dropdown(label="Atendimento", choices=[], interactive=True)
        with gr.Row():
            summary = gr.Markdown("_Selecione um atendimento._")
            transcript = gr.Chatbot(label="Transcrição", height=480)

        outs = [status, queue, case, items_state]
        refresh.click(load_queue, [case], outs).then(show_case, [case, items_state], [summary, transcript])
        case.change(show_case, [case, items_state], [summary, transcript])
        timer = gr.Timer(5)
        timer.tick(lambda on, cur: load_queue(cur) if on else (gr.skip(),) * 4, [auto, case], outs) \
             .then(show_case, [case, items_state], [summary, transcript])
        demo.load(load_queue, [case], outs)
    return demo


LAUNCH_KWARGS = dict(server_name="127.0.0.1", server_port=7860, theme=THEME, css=CSS)

if __name__ == "__main__":
    build().launch(**LAUNCH_KWARGS)
