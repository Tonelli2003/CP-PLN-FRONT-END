"""Análise de sentimento por léxico em português (regras) — leve, explicável e sem dependências.

Combina: léxico de palavras e expressões, negação (janela de 2 tokens), intensificadores/atenuadores,
exclamações e CAIXA ALTA. O resultado NÃO é só exibido: o orquestrador muda o comportamento
(tom de acolhimento, antecipação do handoff) a partir de `polarity`.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .text import normalize, tokens

NEG = {
    "pessimo": -1.0, "pessima": -1.0, "horrivel": -1.0, "absurdo": -1.0, "absurda": -1.0,
    "ridiculo": -1.0, "ridicula": -1.0, "inaceitavel": -1.0, "vergonha": -0.9, "vergonhoso": -0.9,
    "descaso": -1.0, "palhacada": -1.0, "lixo": -1.0, "porcaria": -0.9, "incompetente": -1.0,
    "incompetencia": -1.0, "idiota": -1.0, "estupido": -1.0, "burro": -0.9, "inutil": -1.0,
    "raiva": -0.9, "irritado": -0.8, "irritada": -0.8, "furioso": -1.0, "furiosa": -1.0,
    "revoltado": -1.0, "revoltada": -1.0, "decepcionado": -0.8, "decepcionada": -0.8, "decepcao": -0.8,
    "insatisfeito": -0.8, "insatisfeita": -0.8, "ruim": -0.7, "pior": -0.8, "odio": -0.9,
    "detestei": -0.9, "detesto": -0.9, "demora": -0.5, "demorou": -0.5, "demorado": -0.5, "lento": -0.5,
    "cansado": -0.5, "cansada": -0.5, "chateado": -0.6, "chateada": -0.6, "triste": -0.6,
    "preocupado": -0.45, "preocupada": -0.45, "desesperado": -0.8, "desesperada": -0.8,
    "desespero": -0.8, "aflito": -0.6, "aflita": -0.6, "nervoso": -0.5, "nervosa": -0.5,
    "droga": -0.5, "chato": -0.4, "chata": -0.4, "erro": -0.4, "errado": -0.4, "errada": -0.4,
    "mentira": -0.6, "enganado": -0.7, "enganada": -0.7, "problema": -0.3, "sofrendo": -0.6,
    "medo": -0.4, "culpa": -0.3,
}
POS = {
    "otimo": 0.9, "otima": 0.9, "excelente": 1.0, "maravilhoso": 1.0, "maravilhosa": 1.0,
    "perfeito": 0.9, "perfeita": 0.9, "obrigado": 0.5, "obrigada": 0.5, "valeu": 0.5,
    "agradeco": 0.6, "gratidao": 0.7, "legal": 0.5, "bom": 0.5, "boa": 0.5, "adorei": 0.9,
    "gostei": 0.7, "amei": 1.0, "feliz": 0.7, "ajudou": 0.6, "show": 0.6, "top": 0.6,
    "lindo": 0.6, "linda": 0.6, "fofo": 0.5, "rapido": 0.5, "gentil": 0.6,
}
PHRASES = [  # (regex sobre texto normalizado, peso)
    (r"nunca mais", -0.9), (r"nao aguento", -0.9), (r"nao adianta", -0.5), (r"perda de tempo", -0.8),
    (r"ninguem (me )?(responde|atende|retorna|ajuda)", -0.9), (r"(terceira|quarta|quinta) vez", -0.7),
    (r"(nao|nunca) (me )?(entende|entendeu|resolve|resolveu|ajuda)", -0.7), (r"pessimo atendimento", -1.0),
    (r"mau atendimento", -0.9), (r"que (droga|saco|raiva)", -0.8), (r"muito (bom|obrigad[oa])", 0.3),
]
NEGATORS = {"nao", "nunca", "nem", "jamais", "sem"}
BOOST = {"muito", "muita", "super", "extremamente", "bastante", "totalmente", "completamente", "realmente", "demais"}
SOFTEN = {"pouco", "meio", "levemente", "tanto"}

NEG_THRESHOLD = -0.30
POS_THRESHOLD = 0.30
FRUSTRATION_THRESHOLD = -0.70  # abaixo disso o orquestrador antecipa o handoff


@dataclass
class Sentiment:
    label: str  # positivo | neutro | negativo
    score: float  # confiança na etiqueta (0..1)
    polarity: float  # -1..1
    cues: list[str]

    def as_dict(self) -> dict:
        return {"label": self.label, "score": self.score, "polarity": self.polarity}


def analyze_sentiment(raw: str) -> Sentiment:
    norm = normalize(raw)
    total = 0.0
    cues: list[str] = []

    for pattern, weight in PHRASES:
        for m in re.finditer(pattern, norm):
            total += weight
            cues.append(m.group())
        norm = re.sub(pattern, " ", norm)

    toks = tokens(norm)
    for i, tok in enumerate(toks):
        weight = NEG.get(tok, POS.get(tok))
        if weight is None:
            continue
        window = toks[max(0, i - 2): i]
        if any(w in NEGATORS for w in window):
            weight *= -0.8
        if any(w in BOOST for w in window) or (i + 1 < len(toks) and toks[i + 1] == "demais"):
            weight *= 1.4
        if any(w in SOFTEN for w in window):
            weight *= 0.6
        total += weight
        cues.append(tok)

    if total < 0:
        excl = min(raw.count("!"), 3)
        total *= 1 + 0.1 * excl
        letters = [c for c in raw if c.isalpha()]
        if len(letters) >= 8 and sum(c.isupper() for c in letters) / len(letters) > 0.6:
            total *= 1.3

    polarity = round(math.tanh(total), 2)
    if polarity <= NEG_THRESHOLD:
        label, score = "negativo", 0.5 + abs(polarity) / 2
    elif polarity >= POS_THRESHOLD:
        label, score = "positivo", 0.5 + abs(polarity) / 2
    else:
        label, score = "neutro", max(0.5, 1 - abs(polarity))
    return Sentiment(label, round(min(score, 0.99), 2), polarity, cues)
