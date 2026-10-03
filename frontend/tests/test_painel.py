"""Segunda lente (painel do atendente, Gradio): lógica de fila e detalhe com um cliente falso — sem backend."""
from __future__ import annotations

import pytest

gr = pytest.importorskip("gradio")

import painel_atendente as painel  # noqa: E402
from services.api_client import ApiError, ErrorKind  # noqa: E402

RESUMO = {"protocolo": "HO-1", "motivo": "Reclamação", "motivo_codigo": "reclamacao", "prioridade": "alta",
          "intencao": "reclamacao", "dados_coletados": {"nome_tutor": "Marina"}, "pendencias_do_agendamento": ["data"],
          "relato": "Isso é um absurdo", "acoes_realizadas": ["Handoff acionado"],
          "sentimento": {"label": "negativo", "polaridade": -0.9}, "turnos_do_usuario": 2, "criado_em": "2026-10-02T10:00:00"}
ITEM = {"session_id": "abc123", "protocol": "HO-1", "reason": "reclamacao", "priority": "alta",
        "created_at": "2026-10-02T10:00:00", "summary": RESUMO, "notes": ["Cliente voltou a escrever"]}


class FakeClient:
    def __init__(self, items=None, error: ApiError | None = None):
        self.items, self.error = items if items is not None else [ITEM], error

    def list_handoffs(self):
        if self.error:
            raise self.error
        return self.items

    def get_session(self, sid):
        return {"history": [{"role": "user", "content": "absurdo"}, {"role": "assistant", "content": "Sinto muito"}]}


def test_fila_lista_atendimentos_e_seleciona_o_primeiro(monkeypatch):
    monkeypatch.setattr(painel, "client", FakeClient())
    status, rows, dropdown, items = painel.load_queue()
    assert "1" in status and "fila" in status
    assert rows[0][1] == "HO-1" and rows[0][5] == 1            # protocolo e nº de mensagens após a transferência
    assert dropdown["value"] == "abc123" and items == [ITEM]


def test_fila_vazia_e_mensagem_amigavel(monkeypatch):
    monkeypatch.setattr(painel, "client", FakeClient(items=[]))
    status, rows, dropdown, _ = painel.load_queue()
    assert "fila vazia" in status and rows == [] and dropdown["value"] is None


def test_api_fora_do_ar_nao_gera_traceback(monkeypatch):
    err = ApiError(ErrorKind.OFFLINE, "Não consegui falar com o serviço de atendimento agora.", hint="suba o backend")
    monkeypatch.setattr(painel, "client", FakeClient(error=err))
    status, rows, _, items = painel.load_queue()
    assert "Não consegui falar" in status and rows == [] and items == []


def test_detalhe_traz_resumo_estruturado_e_transcricao(monkeypatch):
    monkeypatch.setattr(painel, "client", FakeClient())
    resumo, chat = painel.show_case("abc123", [ITEM])
    assert "Protocolo HO-1" in resumo and "Isso é um absurdo" in resumo and "Cliente voltou a escrever" in resumo
    assert [m["role"] for m in chat] == ["user", "assistant"]


def test_a_tela_monta_sem_erro():
    assert isinstance(painel.build(), gr.Blocks)


def test_o_painel_sobe_de_verdade_com_tema_e_css(monkeypatch):
    """Sobe o servidor Gradio com os MESMOS argumentos do `python painel_atendente.py` (numa porta livre) e abre a
    página. Pega erros que só aparecem no launch(), como tema/CSS inválidos."""
    import httpx

    monkeypatch.setenv("GRADIO_ANALYTICS_ENABLED", "False")
    monkeypatch.setattr(painel, "client", FakeClient())
    demo = painel.build()
    demo.launch(**{**painel.LAUNCH_KWARGS, "server_port": None}, prevent_thread_lock=True, quiet=True)
    try:
        resp = httpx.get(demo.local_url, timeout=10)
        assert resp.status_code == 200
    finally:
        demo.close()
