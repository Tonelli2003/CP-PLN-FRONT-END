"""ÚNICO ponto do frontend que fala HTTP com a API do bot (o "cérebro").

Regras que este módulo garante (F3):
  * timeout em toda chamada (curto nas rotas rápidas, longo no /chat, que depende do LLM);
  * a URL e a chave vêm da configuração (.env), nunca do código;
  * qualquer falha vira `ApiError`, com uma mensagem amigável pronta para a tela: API fora do ar, timeout,
    401, 404, 422, 503 etc. Nenhuma tela precisa tratar `httpx` nem mostrar traceback;
  * o front não guarda histórico: tudo que a conversa "sabe" é lido do backend por `session_id`.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

import httpx

from config import Settings, get_settings


class ErrorKind(str, Enum):
    OFFLINE = "offline"              # API desligada / URL errada / rede
    TIMEOUT = "timeout"              # a API não respondeu a tempo
    UNAUTHORIZED = "unauthorized"    # 401: X-API-Key ausente ou inválida
    NOT_FOUND = "not_found"          # 404: session_id inexistente (expirou ou foi apagada)
    LLM_UNAVAILABLE = "llm_unavailable"  # 503: modelo de linguagem indisponível
    VALIDATION = "validation"        # 422: requisição inválida (Pydantic)
    SERVER = "server"                # 5xx inesperado
    UNKNOWN = "unknown"              # resposta fora do contrato


class ApiError(Exception):
    """Erro de comunicação com a API, já traduzido para o usuário."""

    def __init__(self, kind: ErrorKind, message: str, *, hint: str = "", status: Optional[int] = None,
                 code: Optional[str] = None, retry_after: Optional[int] = None):
        super().__init__(message)
        self.kind = kind
        self.message = message      # texto amigável (pode ir direto para a tela)
        self.hint = hint            # dica técnica para quem opera o sistema (aparece em letra menor)
        self.status = status
        self.code = code
        self.retry_after = retry_after

    @property
    def is_session_lost(self) -> bool:
        return self.kind is ErrorKind.NOT_FOUND

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


class ApiClient:
    """Cliente HTTP do contrato da API. Um método por rota; devolve os JSONs do contrato como dicts."""

    def __init__(self, settings: Optional[Settings] = None, *, transport: Optional[httpx.BaseTransport] = None):
        self.settings = settings or get_settings()
        headers = {"Accept": "application/json"}
        if self.settings.api_key:
            headers["X-API-Key"] = self.settings.api_key
        self._http = httpx.Client(base_url=self.settings.api_url, headers=headers, transport=transport)

    # ------------------------------------------------------------------ rotas do contrato
    def health(self) -> dict[str, Any]:
        """GET /health: estado da API e do modelo (rota pública)."""
        return self._request("GET", "/health")

    def create_session(self) -> dict[str, Any]:
        """POST /sessions: cria a sessão e devolve {session_id, greeting, capabilities, created_at}."""
        return self._request("POST", "/sessions")

    def send_message(self, session_id: str, message: str) -> dict[str, Any]:
        """POST /chat: devolve a resposta e o raio-X do turno. Usa o timeout longo (LLM)."""
        return self._request("POST", "/chat", json={"session_id": session_id, "message": message},
                             timeout=self.settings.timeout_s)

    def get_session(self, session_id: str) -> dict[str, Any]:
        """GET /sessions/{id}: histórico, slots, fluxo, handoff e situação (a verdade fica no servidor)."""
        return self._request("GET", f"/sessions/{session_id}")

    def delete_session(self, session_id: str) -> dict[str, Any]:
        """DELETE /sessions/{id}: direito ao esquecimento (apaga a sessão e anonimiza o log)."""
        return self._request("DELETE", f"/sessions/{session_id}")

    def get_metrics(self) -> dict[str, Any]:
        """GET /metrics: métricas conversacionais calculadas do log por turno."""
        return self._request("GET", "/metrics")

    def list_handoffs(self) -> list[dict[str, Any]]:
        """GET /handoffs: fila de transferências para o atendente (urgentes primeiro)."""
        return self._request("GET", "/handoffs")

    def send_feedback(self, session_id: str, rating: int, comment: Optional[str] = None) -> dict[str, Any]:
        """POST /feedback: nota CSAT de 1 a 5."""
        body: dict[str, Any] = {"session_id": session_id, "rating": rating}
        if comment:
            body["comment"] = comment
        return self._request("POST", "/feedback", json=body)

    def close(self) -> None:
        self._http.close()

    # ------------------------------------------------------------------ infraestrutura
    def _request(self, method: str, path: str, *, json: Any = None, timeout: Optional[float] = None) -> Any:
        timeout_s = timeout if timeout is not None else self.settings.fast_timeout_s
        try:
            resp = self._http.request(method, path, json=json, timeout=httpx.Timeout(timeout_s, connect=3.0))
        except httpx.ConnectTimeout as exc:
            raise self._offline() from exc
        except httpx.TimeoutException as exc:
            raise ApiError(ErrorKind.TIMEOUT,
                           "A resposta está demorando mais que o esperado. O modelo pode estar carregando; "
                           "tente de novo em alguns instantes.",
                           hint=f"Sem resposta de {self.settings.api_url} em {timeout_s:.0f}s "
                                "(ajuste API_TIMEOUT_S no .env se o modelo for lento).") from exc
        except (httpx.TransportError, httpx.InvalidURL) as exc:
            raise self._offline() from exc
        return self._parse(resp)

    def _offline(self) -> ApiError:
        return ApiError(ErrorKind.OFFLINE,
                        "Não consegui falar com o serviço de atendimento agora. Ele pode estar fora do ar.",
                        hint=f"Confira se o backend está rodando em {self.settings.api_url} "
                             "(cd backend && uvicorn app.main:app --port 8000) e se API_URL está correto no .env.")

    @staticmethod
    def _error_body(resp: httpx.Response) -> tuple[Optional[str], Optional[str]]:
        """Extrai (code, message) de {"detail": {"code", "message"}}; 422 traz uma lista em `detail`."""
        try:
            detail = resp.json().get("detail")
        except Exception:
            return None, None
        if isinstance(detail, dict):
            return detail.get("code"), detail.get("message")
        if isinstance(detail, str):
            return None, detail
        if isinstance(detail, list) and detail:
            first = detail[0] if isinstance(detail[0], dict) else {}
            return "validacao", first.get("msg")
        return None, None

    def _parse(self, resp: httpx.Response) -> Any:
        status = resp.status_code
        if 200 <= status < 300:
            try:
                return resp.json()
            except ValueError as exc:
                raise ApiError(ErrorKind.UNKNOWN, "A API respondeu em um formato inesperado.",
                               hint="O corpo da resposta não é JSON. Confira se API_URL aponta para o backend certo.",
                               status=status) from exc

        code, message = self._error_body(resp)
        if status == 401:
            raise ApiError(ErrorKind.UNAUTHORIZED, "A chave de acesso à API foi recusada.",
                           hint="Use no .env do frontend a mesma API_KEY do .env do backend.", status=status, code=code)
        if status == 404:
            raise ApiError(ErrorKind.NOT_FOUND, message or "Sessão não encontrada. Inicie uma nova conversa.",
                           status=status, code=code or "sessao_nao_encontrada")
        if status == 422:
            raise ApiError(ErrorKind.VALIDATION,
                           "Não consegui enviar essa mensagem. Verifique se ela não está vazia e tem até 1000 caracteres.",
                           hint=message or "", status=status, code=code)
        if status == 503:
            try:
                retry = int(resp.headers.get("Retry-After", ""))
            except ValueError:
                retry = None
            raise ApiError(ErrorKind.LLM_UNAVAILABLE,
                           message or "Estou com dificuldade para responder agora. Tente novamente em instantes "
                                      "ou peça um atendente.",
                           status=status, code=code or "llm_indisponivel", retry_after=retry)
        if status >= 500:
            raise ApiError(ErrorKind.SERVER, "O serviço de atendimento encontrou um erro interno. Tente novamente.",
                           hint=f"HTTP {status}" + (f": {message}" if message else ""), status=status, code=code)
        raise ApiError(ErrorKind.UNKNOWN, message or f"A API respondeu com um erro inesperado (HTTP {status}).",
                       status=status, code=code)
