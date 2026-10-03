"""Integração REAL (opcional): front (cliente HTTP) × backend de verdade. Pulado se a API não estiver no ar.

Com o backend rodando (qualquer provedor de LLM, inclusive LLM_PROVIDER=mock):  python -m pytest tests/test_integracao_api_real.py
"""
from __future__ import annotations

import pytest

from config import get_settings
from services.api_client import ApiClient, ApiError, ErrorKind


@pytest.fixture(scope="module")
def api():
    client = ApiClient(get_settings())
    try:
        client.health()
    except ApiError:
        pytest.skip("backend fora do ar (suba o uvicorn na porta 8000 para rodar a integração)")
    return client


def test_ciclo_completo_sessao_chat_estado_metricas(api):
    s = api.create_session()
    sid = s["session_id"]
    assert s["greeting"] and s["capabilities"]
    x = api.send_message(sid, "Quanto custa a consulta?")
    assert x["intent"] == "faq" and x["turn"] == 1 and x["reply"]
    detail = api.get_session(sid)                      # T8: o estado está no servidor
    assert [m["role"] for m in detail["history"]] == ["assistant", "user", "assistant"]
    assert api.get_metrics()["total_conversas"] >= 1
    assert api.send_feedback(sid, 5)["registered"] is True
    assert isinstance(api.list_handoffs(), list)
    assert api.delete_session(sid)["deleted"] is True
    with pytest.raises(ApiError) as e:
        api.get_session(sid)
    assert e.value.kind is ErrorKind.NOT_FOUND


def test_chat_com_mensagem_invalida_vira_erro_de_validacao(api):
    sid = api.create_session()["session_id"]
    with pytest.raises(ApiError) as e:
        api.send_message(sid, "x" * 1001)
    assert e.value.kind is ErrorKind.VALIDATION
    api.delete_session(sid)


def test_chave_errada_vira_erro_de_autenticacao(api):
    from dataclasses import replace
    bad = ApiClient(replace(get_settings(), api_key="chave-errada"))
    with pytest.raises(ApiError) as e:
        bad.get_metrics()
    # se o backend estiver com a autenticação desligada (API_KEY vazia), não há 401 para testar
    assert e.value.kind is ErrorKind.UNAUTHORIZED


def test_tela_do_chat_inteira_com_backend_real(api):
    """A página Streamlit de ponta a ponta: abre, clica num atalho, a API real responde e o raio-X é desenhado."""
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    pagina = Path(__file__).resolve().parents[1] / "pages" / "chat.py"
    at = AppTest.from_file(str(pagina), default_timeout=60).run()
    assert not at.exception
    sid = at.session_state["session_id"]
    try:
        at.button(key="sugg_2").click().run()          # "Quanto custa a consulta?"
        assert not at.exception
        html = " ".join(m.value for m in at.markdown)
        assert "🎯 faq" in html and "Slots" in html and "R\\$ 150" in html
    finally:
        api.delete_session(sid)
