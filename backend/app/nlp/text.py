"""Utilitários de texto: normalização, tokenização e mascaramento de dados pessoais (LGPD)."""
from __future__ import annotations

import re
import unicodedata


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def normalize(text: str) -> str:
    """minúsculas, sem acentos, espaços colapsados. Pontuação é preservada (usamos '?' e '!')."""
    t = strip_accents(text.lower()).replace("’", "'")
    return re.sub(r"\s+", " ", t).strip()


def tokens(norm: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", norm)


# ---------- dados pessoais ----------
CPF_RE = re.compile(r"(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)|(?i:cpf)\D{0,6}\d{11}(?!\d)")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}(?!\d)")
CARD_CAND_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?<![ -])(?!\d)")


def _luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        n = int(ch)
        if alt:
            n *= 2
            if n > 9:
                n -= 9
        total += n
        alt = not alt
    return total % 10 == 0


def find_cards(text: str) -> list[str]:
    out = []
    for m in CARD_CAND_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            out.append(m.group())
    return out


def detect_sensitive(text: str) -> list[str]:
    """Dados que o bot NÃO deve receber nem guardar: CPF e cartão."""
    found = []
    if CPF_RE.search(text):
        found.append("cpf")
    if find_cards(text):
        found.append("cartao")
    return found


def mask_sensitive(text: str) -> str:
    """Máscara aplicada ao histórico guardado na sessão."""
    for card in find_cards(text):
        text = text.replace(card, "[CARTAO]")
    return CPF_RE.sub("[CPF]", text)


def mask_for_log(text: str, known_values: list[str] | None = None, limit: int = 160) -> str:
    """Máscara mais forte, usada no log analítico: remove também e-mail, telefone e nomes já coletados."""
    text = mask_sensitive(text)
    text = EMAIL_RE.sub("[EMAIL]", text)
    text = PHONE_RE.sub("[TELEFONE]", text)
    for v in sorted({v for v in (known_values or []) if v and len(v) >= 2}, key=len, reverse=True):
        text = re.sub(re.escape(v), "[DADO]", text, flags=re.IGNORECASE)
    return text[:limit]


def number_set(text: str) -> set[str]:
    """Conjunto de números do texto (normalizados: '09' == '9'). Base da checagem de 'fatos inventados'."""
    return {str(int(n)) for n in re.findall(r"\d+", text)}
