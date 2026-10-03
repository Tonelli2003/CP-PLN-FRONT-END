"""FAQ curada (data/faq.json) consultada por REGRA — sem embeddings, sem banco vetorial.

`buscar_faq(pergunta)` é a única porta de entrada: quando o RAG chegar (próximo módulo), basta
substituir esta função mantendo a assinatura — o contrato da API não muda.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from ..nlp.text import normalize


@dataclass
class FaqMatch:
    id: str
    topico: str
    pergunta: str
    resposta: str
    score: float


def _stem(tok: str) -> str:
    return tok[:-1] if len(tok) > 4 and tok.endswith("s") else tok


def _stem_text(norm: str) -> str:
    return " ".join(_stem(t) for t in re.findall(r"[a-z0-9]+", norm))


class FaqKnowledge:
    def __init__(self, path: Path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.clinica: str = data["clinica"]
        self.telefone: str = data["telefone"]
        self.itens: list[dict] = data["itens"]
        self.fora_da_base: list[str] = [_stem_text(normalize(t)) for t in data.get("topicos_fora_da_base", [])]
        self._kw: dict[str, list[str]] = {
            it["id"]: [_stem_text(normalize(k)) for k in it["palavras_chave"]] for it in self.itens
        }

    @property
    def topicos(self) -> list[str]:
        return [it["topico"] for it in self.itens]

    @staticmethod
    def _has(text_stem: str, phrase_stem: str) -> bool:
        return re.search(rf"(?<![a-z0-9]){re.escape(phrase_stem)}(?![a-z0-9])", text_stem) is not None

    def topico_fora_da_base(self, pergunta: str) -> str | None:
        """Há na pergunta um assunto que SABEMOS não estar coberto (ex.: cirurgia, ultrassom)?"""
        t = _stem_text(normalize(pergunta))
        for term in self.fora_da_base:
            if self._has(t, term):
                return term
        return None

    def buscar_faq(self, pergunta: str) -> FaqMatch | None:
        t = _stem_text(normalize(pergunta))
        best: tuple[float, dict] | None = None
        for it in self.itens:
            score = 0.0
            for kw in self._kw[it["id"]]:
                if self._has(t, kw):
                    score += 1 + 0.5 * (len(kw.split()) - 1)
            if score > 0 and (best is None or score > best[0]):
                best = (score, it)
        if not best:
            return None
        score, it = best
        # guarda de precisão: assunto sabidamente fora da base não pode ser respondido por item "parecido"
        blocked = self.topico_fora_da_base(pergunta)
        if blocked and not any(blocked in kw for kw in self._kw[it["id"]]):
            return None
        return FaqMatch(it["id"], it["topico"], it["pergunta"], it["resposta"], score)


def buscar_faq(faq: FaqKnowledge, pergunta: str) -> FaqMatch | None:
    return faq.buscar_faq(pergunta)
