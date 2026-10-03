"""F4: as telas (Streamlit AppTest) com um cliente de API falso — sem backend e sem LLM."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from components import state
from services.api_client import ApiError, ErrorKind
from tests.conftest import EMPTY_METRICS, FULL_METRICS, FakeClient

ROOT = Path(__file__).resolve().parents[1]


def run_app(monkeypatch, fake, page="pages/chat.py") -> AppTest:
    monkeypatch.setattr(state, "get_client", lambda: fake)
    at = AppTest.from_file(str(ROOT / page), default_timeout=20)
    return at.run()


def texts(at: AppTest) -> str:
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption] + [e.value for e in at.error] + \
            [w.value for w in at.warning] + [s.value for s in at.success] + [i.value for i in at.info]
    return "\n".join(parts)


def test_abre_cria_sessao_e_mostra_saudacao_do_servidor(monkeypatch):
    fake = FakeClient()
    at = run_app(monkeypatch, fake)
    assert not at.exception
    assert ("create_session",) in fake.calls
    assert at.session_state[state.SID_KEY] == "sess0001"
    assert "Oi! Eu sou a Duda." in texts(at)
    assert "Envie uma mensagem para ver a intenção" in texts(at)


def test_enviar_mensagem_atualiza_chat_e_raio_x(monkeypatch):
    fake = FakeClient()
    at = run_app(monkeypatch, fake)
    at.chat_input[0].set_value("quanto custa a consulta?").run()
    assert not at.exception
    assert ("send_message", "sess0001", "quanto custa a consulta?") in fake.calls
    out = texts(at)
    assert "quanto custa a consulta?" in out
    assert "R\\$ 150" in out                      # `$` escapado: não vira LaTeX
    assert "🎯 faq · 90%" in out                  # raio-X: intenção e confiança
    assert "😐 neutro" in out                      # raio-X: sentimento
    assert "Marina" in out and "1/6" in out        # slot vindo de GET /sessions e progresso dos slots
    assert "input:teste" in out                    # evento de guardrail


def test_historico_vem_do_servidor_e_nao_da_tela(monkeypatch):
    """T8 em miniatura: uma mensagem inserida direto no servidor (como no /docs) aparece na tela ao recarregar."""
    fake = FakeClient()
    at = run_app(monkeypatch, fake)
    fake.sessions["sess0001"] += [{"role": "user", "content": "mensagem via /docs", "ts": "t"},
                                  {"role": "assistant", "content": "resposta via /docs", "ts": "t"}]
    at.run()
    out = texts(at)
    assert "mensagem via /docs" in out and "resposta via /docs" in out
    assert fake.calls.count(("create_session",)) == 1   # reaproveitou o mesmo session_id


def test_nova_conversa_cria_outra_sessao(monkeypatch):
    fake = FakeClient()
    at = run_app(monkeypatch, fake)
    next(b for b in at.sidebar.button if "Nova conversa" in b.label).click().run()
    assert at.session_state[state.SID_KEY] == "sess0002"
    assert fake.calls.count(("create_session",)) == 2


def test_apagar_conversa_chama_delete_e_comeca_outra(monkeypatch):
    fake = FakeClient()
    at = run_app(monkeypatch, fake)
    next(b for b in at.sidebar.button if "Apagar" in b.label).click().run()
    assert ("delete_session", "sess0001") in fake.calls
    assert at.session_state[state.SID_KEY] != "sess0001"


def test_api_fora_do_ar_mostra_mensagem_amigavel_sem_traceback(monkeypatch):
    at = run_app(monkeypatch, FakeClient(offline=True))
    assert not at.exception
    out = texts(at)
    assert "Não consegui falar com o serviço de atendimento" in out and "indisponível" in out
    assert not at.chat_input                      # sem API, sem chat


def test_erro_503_no_chat_e_amigavel_e_nao_perde_a_conversa(monkeypatch):
    fake = FakeClient(send_error=ApiError(ErrorKind.LLM_UNAVAILABLE, "Estou com dificuldade para responder agora.", status=503, retry_after=5))
    at = run_app(monkeypatch, fake)
    at.chat_input[0].set_value("oi").run()
    assert not at.exception
    out = texts(at)
    assert "Estou com dificuldade para responder agora." in out and "não foi registrada" in out
    assert at.session_state[state.SID_KEY] == "sess0001"


def test_sessao_expirada_no_envio_comeca_nova_conversa(monkeypatch):
    fake = FakeClient(send_error=ApiError(ErrorKind.NOT_FOUND, "Sessão não encontrada. Inicie uma nova conversa.", status=404))
    at = run_app(monkeypatch, fake)
    at.chat_input[0].set_value("oi").run()
    assert not at.exception
    assert "Sessão não encontrada" in texts(at)
    assert state.SID_KEY not in at.session_state or at.session_state[state.SID_KEY] != "sess0001"


def test_handoff_ativo_aparece_no_banner_e_no_raio_x(monkeypatch):
    at = run_app(monkeypatch, FakeClient(handoff=True))
    assert not at.exception
    out = texts(at)
    assert "Conversa transferida para um atendente humano" in out and "HO-1" in out
    assert "prioridade ALTA" in out


def test_pagina_de_metricas_com_dados(monkeypatch):
    fake = FakeClient()
    fake.metrics = FULL_METRICS
    at = run_app(monkeypatch, fake, "pages/metricas.py")
    assert not at.exception
    labels = {m.label: m.value for m in at.metric}
    assert labels["Taxa de contenção"] == "69,6%" and labels["Taxa de handoff"] == "30,4%"
    assert labels["Latência média"] == "3,4 s"
    assert "Guardrail de saída" in texts(at)


def test_pagina_de_metricas_vazia_nao_quebra(monkeypatch):
    fake = FakeClient()
    fake.metrics = EMPTY_METRICS
    at = run_app(monkeypatch, fake, "pages/metricas.py")
    assert not at.exception and "Ainda não há conversas" in texts(at)


def test_pagina_de_metricas_com_api_fora_do_ar(monkeypatch):
    at = run_app(monkeypatch, FakeClient(offline=True), "pages/metricas.py")
    assert not at.exception and "indisponível" in texts(at)


def test_ponto_de_entrada_app_py_navega_para_o_chat(monkeypatch):
    """`streamlit run app.py` (st.navigation) abre direto na página do chat."""
    at = run_app(monkeypatch, FakeClient(), "app.py")
    assert not at.exception
    assert "Oi! Eu sou a Duda." in texts(at)


def test_atalhos_aparecem_no_inicio_e_enviam_a_mensagem_pela_api(monkeypatch):
    fake = FakeClient()
    at = run_app(monkeypatch, fake)
    keys = [b.key for b in at.button if b.key and b.key.startswith("sugg_")]
    assert keys == ["sugg_0", "sugg_1", "sugg_2", "sugg_3"]
    at.button(key="sugg_1").click().run()
    assert not at.exception
    assert ("send_message", "sess0001", "Qual o horário de funcionamento?") in fake.calls
    # depois da primeira mensagem os atalhos somem
    assert not [b for b in at.button if b.key and b.key.startswith("sugg_")]


def test_conteudo_do_servidor_e_escapado_no_html_do_raio_x(monkeypatch):
    """Segurança: o raio-X monta HTML; texto vindo do usuário/backend nunca pode virar tag."""
    fake = FakeClient()
    original = fake.get_session

    def malicioso(sid):
        d = original(sid)
        d["slots"]["nome_tutor"] = "<img src=x onerror=alert(1)>"
        return d
    fake.get_session = malicioso
    at = run_app(monkeypatch, fake)
    out = texts(at)
    assert "<img src=x" not in out and "&lt;img src=x" in out


def test_metricas_tem_abas_e_definicoes(monkeypatch):
    fake = FakeClient()
    fake.metrics = FULL_METRICS
    at = run_app(monkeypatch, fake, "pages/metricas.py")
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Conversa", "Qualidade do bot", "Atendimento"]
    assert any("Como cada métrica é calculada" in e.label for e in at.expander)


class _Balanceado(HTMLParser):
    """Confere se toda tag aberta foi fechada (tags void ignoradas)."""
    VOID = {"br", "hr", "img", "input", "meta", "link"}

    def __init__(self):
        super().__init__()
        self.pilha: list[str] = []
        self.erros: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.pilha.append(tag)

    def handle_endtag(self, tag):
        if not self.pilha or self.pilha[-1] != tag:
            self.erros.append(f"</{tag}> sem par (topo: {self.pilha[-1] if self.pilha else None})")
        else:
            self.pilha.pop()


def _html_blocos(at: AppTest) -> list[str]:
    return [m.value for m in at.markdown if "pb-" in m.value]


def test_html_gerado_tem_tags_balanceadas_em_todas_as_telas(monkeypatch):
    """Não dá para ver o layout no teste, mas dá para garantir que nenhum bloco HTML ficou com tag aberta."""
    cenarios = [(FakeClient(), "pages/chat.py"), (FakeClient(handoff=True), "pages/chat.py")]
    fake = FakeClient()
    fake.metrics = FULL_METRICS
    cenarios.append((fake, "pages/metricas.py"))
    for fake_client, page in cenarios:
        at = run_app(monkeypatch, fake_client, page)
        if page.endswith("chat.py"):
            at.chat_input[0].set_value("oi").run()
        blocos = _html_blocos(at)
        assert blocos, f"nenhum bloco HTML em {page}"
        for bloco in blocos:
            parser = _Balanceado()
            parser.feed(bloco)
            assert not parser.erros and not parser.pilha, (page, parser.erros, parser.pilha, bloco[:120])
