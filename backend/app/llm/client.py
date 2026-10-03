"""ÚNICO ponto de acesso ao modelo de linguagem. Trocar de provedor = mudar o .env, não o bot.

Provedores: `ollama` (local, recomendado) · `openai_compat` (Groq, OpenRouter, Gemini-OpenAI...) · `mock` (testes/offline).
"""
from __future__ import annotations

import re
import time

import httpx

from ..config import Settings


class LLMUnavailableError(Exception):
    """O modelo não respondeu (fora do ar, timeout, modelo não instalado, chave inválida...)."""


class LLMClient:
    def __init__(self, settings: Settings):
        self.s = settings
        self._health_cache: tuple[float, dict] | None = None

    @property
    def provider(self) -> str:
        return self.s.llm_provider

    @property
    def model(self) -> str:
        return self.s.llm_model if self.provider != "mock" else "mock"

    # ------------------------------------------------------------------ chat
    def chat(self, messages: list[dict]) -> str:
        if self.provider == "mock":
            return self._mock(messages)
        if self.provider == "ollama":
            return self._ollama(messages)
        if self.provider == "openai_compat":
            return self._openai_compat(messages)
        raise LLMUnavailableError(f"Provedor de LLM desconhecido: {self.provider!r}")

    def _ollama(self, messages: list[dict]) -> str:
        payload = {
            "model": self.s.llm_model, "messages": messages, "stream": False, "keep_alive": "10m",
            "options": {"temperature": self.s.llm_temperature, "num_predict": self.s.llm_max_tokens, "num_ctx": self.s.llm_num_ctx},
        }
        try:
            r = httpx.post(f"{self.s.ollama_url}/api/chat", json=payload, timeout=self.s.llm_timeout_s)
            if r.status_code == 404:
                raise LLMUnavailableError(f"Modelo '{self.s.llm_model}' não encontrado no Ollama. Rode: ollama pull {self.s.llm_model}")
            r.raise_for_status()
            return r.json()["message"]["content"]
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise LLMUnavailableError("Não consegui conectar ao Ollama. Ele está rodando (ollama serve)?")
        except httpx.TimeoutException:
            raise LLMUnavailableError("O modelo demorou demais para responder (timeout).")
        except httpx.HTTPError as e:
            raise LLMUnavailableError(f"Erro HTTP do provedor de LLM: {e}")
        except (KeyError, ValueError):
            raise LLMUnavailableError("Resposta inesperada do provedor de LLM.")

    def _openai_compat(self, messages: list[dict]) -> str:
        if not self.s.llm_base_url:
            raise LLMUnavailableError("LLM_BASE_URL não configurada.")
        headers = {"Authorization": f"Bearer {self.s.llm_api_key}"} if self.s.llm_api_key else {}
        payload = {"model": self.s.llm_model, "messages": messages, "temperature": self.s.llm_temperature, "max_tokens": self.s.llm_max_tokens}
        try:
            r = httpx.post(f"{self.s.llm_base_url}/chat/completions", json=payload, headers=headers, timeout=self.s.llm_timeout_s)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except httpx.TimeoutException:
            raise LLMUnavailableError("O provedor de LLM demorou demais para responder (timeout).")
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            hint = " (limite da camada gratuita atingido?)" if code == 429 else ""
            raise LLMUnavailableError(f"Provedor de LLM respondeu HTTP {code}{hint}.")
        except httpx.HTTPError:
            raise LLMUnavailableError("Não consegui conectar ao provedor de LLM.")
        except (KeyError, IndexError, ValueError):
            raise LLMUnavailableError("Resposta inesperada do provedor de LLM.")

    @staticmethod
    def _mock(messages: list[dict]) -> str:
        """Provedor de TESTE: devolve o texto-base. Torna os testes determinísticos e gratuitos."""
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        m = re.search(r"<<BASE>>\s*(.*?)\s*<</BASE>>", system, flags=re.S)
        return m.group(1) if m else "Posso ajudar com agendamentos e dúvidas da clínica."

    # ------------------------------------------------------------------ health
    def health(self) -> dict:
        now = time.time()
        if self._health_cache and now - self._health_cache[0] < 10:
            return self._health_cache[1]
        info = {"provider": self.provider, "model": self.model, "available": False, "detail": ""}
        if self.provider == "mock":
            info.update(available=True, detail="provedor de teste (offline)")
        elif self.provider == "ollama":
            try:
                r = httpx.get(f"{self.s.ollama_url}/api/tags", timeout=2.0)
                names = [m.get("name", "") for m in r.json().get("models", [])]
                ok = any(n == self.s.llm_model or n.startswith(self.s.llm_model + ":") or n.split(":")[0] == self.s.llm_model for n in names)
                info.update(available=ok, detail="ok" if ok else f"modelo ausente; rode: ollama pull {self.s.llm_model}")
            except Exception:
                info["detail"] = "Ollama inacessível"
        else:
            ok = bool(self.s.llm_base_url and self.s.llm_api_key)
            info.update(available=ok, detail="configurado (não testado)" if ok else "LLM_BASE_URL/LLM_API_KEY ausentes")
        self._health_cache = (now, info)
        return info
