"""F3: o módulo cliente único. Timeout, erros amigáveis (offline, 401, 404, 422, 503, 5xx) e contrato das rotas."""
from __future__ import annotations

import json

import httpx
import pytest

from services.api_client import ApiError, ErrorKind
from tests.conftest import make_client


def test_envia_x_api_key_e_usa_a_url_configurada(settings):
    seen = {}

    def handler(req: httpx.Request):
        seen["url"], seen["key"] = str(req.url), req.headers.get("x-api-key")
        return httpx.Response(201, json={"session_id": "abcd1234"})

    out = make_client(settings, handler).create_session()
    assert out["session_id"] == "abcd1234"
    assert seen == {"url": "http://api.test/sessions", "key": "k123"}


def test_chat_envia_session_id_e_message(settings):
    def handler(req: httpx.Request):
        assert req.method == "POST" and req.url.path == "/chat"
        assert json.loads(req.read()) == {"session_id": "abcd1234", "message": "oi"}   # sem comparar bytes: o httpx varia o espaçamento
        return httpx.Response(200, json={"reply": "ola"})

    assert make_client(settings, handler).send_message("abcd1234", "oi") == {"reply": "ola"}


def test_rotas_do_contrato(settings):
    calls = []

    def handler(req: httpx.Request):
        calls.append((req.method, req.url.path))
        return httpx.Response(200, json=[] if req.url.path == "/handoffs" else {})

    c = make_client(settings, handler)
    c.health(); c.get_session("abcd1234"); c.delete_session("abcd1234"); c.get_metrics(); c.list_handoffs()
    c.send_feedback("abcd1234", 5, "ótimo")
    assert calls == [("GET", "/health"), ("GET", "/sessions/abcd1234"), ("DELETE", "/sessions/abcd1234"),
                     ("GET", "/metrics"), ("GET", "/handoffs"), ("POST", "/feedback")]


def test_api_fora_do_ar_vira_erro_amigavel(settings):
    def handler(req):
        raise httpx.ConnectError("recusou")

    with pytest.raises(ApiError) as e:
        make_client(settings, handler).health()
    assert e.value.kind is ErrorKind.OFFLINE
    assert "fora do ar" in e.value.message and "api.test" in e.value.hint
    assert "Traceback" not in e.value.message


def test_timeout_vira_erro_amigavel(settings):
    def handler(req):
        raise httpx.ReadTimeout("lento")

    with pytest.raises(ApiError) as e:
        make_client(settings, handler).send_message("abcd1234", "oi")
    assert e.value.kind is ErrorKind.TIMEOUT and "demorando" in e.value.message


def test_401_chave_invalida(settings):
    def handler(req):
        return httpx.Response(401, json={"detail": {"code": "api_key_invalida", "message": "x"}})

    with pytest.raises(ApiError) as e:
        make_client(settings, handler).get_metrics()
    assert e.value.kind is ErrorKind.UNAUTHORIZED and "API_KEY" in e.value.hint


def test_404_sessao_inexistente_usa_a_mensagem_do_backend(settings):
    def handler(req):
        return httpx.Response(404, json={"detail": {"code": "sessao_nao_encontrada", "message": "Sessão não encontrada. Inicie uma nova conversa."}})

    with pytest.raises(ApiError) as e:
        make_client(settings, handler).get_session("abcd1234")
    assert e.value.kind is ErrorKind.NOT_FOUND and e.value.is_session_lost
    assert e.value.message == "Sessão não encontrada. Inicie uma nova conversa."


def test_422_validacao_pydantic(settings):
    def handler(req):
        return httpx.Response(422, json={"detail": [{"type": "string_too_long", "msg": "String should have at most 1000 characters"}]})

    with pytest.raises(ApiError) as e:
        make_client(settings, handler).send_message("abcd1234", "x")
    assert e.value.kind is ErrorKind.VALIDATION and "1000" in e.value.message and "at most" in e.value.hint


def test_503_llm_indisponivel_mostra_mensagem_pronta_e_retry_after(settings):
    def handler(req):
        return httpx.Response(503, headers={"Retry-After": "5"}, json={"detail": {
            "code": "llm_indisponivel", "message": "Estou com dificuldade para responder agora."}})

    with pytest.raises(ApiError) as e:
        make_client(settings, handler).send_message("abcd1234", "oi")
    assert e.value.kind is ErrorKind.LLM_UNAVAILABLE and e.value.retry_after == 5
    assert e.value.message == "Estou com dificuldade para responder agora."


def test_500_e_corpo_nao_json(settings):
    with pytest.raises(ApiError) as e:
        make_client(settings, lambda r: httpx.Response(500, text="boom")).health()
    assert e.value.kind is ErrorKind.SERVER
    with pytest.raises(ApiError) as e:
        make_client(settings, lambda r: httpx.Response(200, text="<html>")).health()
    assert e.value.kind is ErrorKind.UNKNOWN


def test_nao_envia_header_quando_nao_ha_chave(settings):
    from dataclasses import replace
    seen = {}

    def handler(req):
        seen["k"] = req.headers.get("x-api-key")
        return httpx.Response(200, json={})

    make_client(replace(settings, api_key=""), handler).health()
    assert seen["k"] is None
