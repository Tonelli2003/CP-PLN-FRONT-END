"""Extração e VALIDAÇÃO de slots por código (regex/regras). O LLM nunca decide o valor de um slot."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from .text import normalize

WEEKDAYS = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "domingo": 6}
MONTHS = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7,
          "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
DAYS_IN_MONTH_PT = {1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril", 5: "maio", 6: "junho", 7: "julho",
                    8: "agosto", 9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"}

# ---------------------------------------------------------------- sim / não
YES_RE = re.compile(r"^(sim|s|claro|pode|podemos|confirm\w*|isso|isso mesmo|ok|okay|certo|perfeito|fechado|com certeza|uhum|aham|positivo|bora|beleza|pode ser|tudo certo|correto)\b")
NO_RE = re.compile(r"^(nao|n|negativo|nope|agora nao|melhor nao|errado|incorreto|nada disso|cancel\w*)\b")


def is_yes(norm: str) -> bool:
    return bool(YES_RE.match(norm)) and not NO_RE.match(norm) and "nao" not in norm.split()[:4]


def is_no(norm: str) -> bool:
    return bool(NO_RE.match(norm))


# ---------------------------------------------------------------- nomes
_NAME_CHARS = r"A-Za-zÀ-ÿ'’\-"
STOP_NAME = {
    "sim", "nao", "oi", "ola", "bom", "boa", "dia", "tarde", "noite", "tchau", "obrigado", "obrigada",
    "cliente", "tutor", "tutora", "dono", "dona", "nova", "novo", "daqui", "eu", "voce", "ele", "ela",
    "aqui", "so", "ai", "tudo", "bem", "pode", "ok", "claro", "isso", "nada", "nenhum", "nenhuma",
    "marcar", "agendar", "consulta", "horario", "data", "email", "pular", "cancelar", "atendente", "humano",
    "pro", "pra", "para", "que", "esta", "esse", "essa", "aquele", "um", "uma", "o", "a", "meu", "minha",
    "cachorro", "cachorra", "gato", "gata", "pet", "cao", "amanha", "hoje", "sei", "la", "talvez",
}
STOP_AFTER = {"e", "quero", "preciso", "gostaria", "vim", "estou", "tenho", "queria", "pra", "para", "que",
              "com", "meu", "minha", "mas", "porque", "pois", "desejo", "vou", "fui", "sou", "sera"}
CONNECTORS = {"de", "da", "do", "dos", "das", "e"}
SPECIES = {
    "cachorro": "cachorro", "cachorra": "cachorro", "cao": "cachorro", "caozinho": "cachorro", "cachorrinho": "cachorro",
    "cachorrinha": "cachorro", "cadela": "cachorro", "gato": "gato", "gata": "gato", "gatinho": "gato", "gatinha": "gato",
    "coelho": "coelho", "coelha": "coelho", "passaro": "ave", "ave": "ave", "calopsita": "ave", "papagaio": "ave",
    "hamster": "roedor", "porquinho": "roedor", "tartaruga": "réptil", "cobra": "réptil",
}


@dataclass
class SlotResult:
    value: str | None = None
    error: str | None = None  # código do erro de validação
    raw: str | None = None


def _title(words: list[str]) -> str:
    out = []
    for i, w in enumerate(words):
        out.append(w.lower() if (w.lower() in CONNECTORS and i > 0) else w[:1].upper() + w[1:].lower())
    return " ".join(out)


def _clean_name_tokens(fragment: str, max_tokens: int = 4) -> list[str]:
    toks = [t for t in re.split(r"\s+", fragment.strip()) if t]
    result: list[str] = []
    for t in toks:
        t = t.strip(".,;:!?")
        if not t:
            break
        if normalize(t) in STOP_AFTER and result:
            break
        result.append(t)
        if len(result) >= max_tokens:
            break
    while result and result[-1].lower() in CONNECTORS:
        result.pop()
    return result


def _valid_person_name(words: list[str]) -> bool:
    if not words or len(words) > 4:
        return False
    full = " ".join(words)
    if not re.fullmatch(rf"[{_NAME_CHARS} ]{{2,50}}", full):
        return False
    return not any(normalize(w) in STOP_NAME for w in words if w.lower() not in CONNECTORS)


def extract_nome_tutor(raw: str, bare: bool) -> SlotResult:
    m = re.search(rf"(?i)\b(?:meu nome (?:é|e)|me chamo|meu nome:|sou (?:o |a )?|aqui (?:é|e) (?:o |a )?|nome:)\s*([{_NAME_CHARS} ]{{2,60}})", raw)
    if m:
        words = _clean_name_tokens(m.group(1))
        if _valid_person_name(words):
            return SlotResult(_title(words), raw=m.group(1))
        if bare:
            return SlotResult(error="nome_invalido", raw=m.group(1))
        return SlotResult()
    if not bare:
        return SlotResult()
    cand = re.sub(r"(?i)^\s*(?:é |e |eh |pode chamar de |me chama de |meu nome |nome )", "", raw.strip()).strip(" .!")
    if "?" in raw or not cand:
        return SlotResult()
    if re.search(r"\d", cand):
        return SlotResult(error="nome_invalido", raw=cand)
    words = _clean_name_tokens(cand)
    if _valid_person_name(words) and len(words) == len(cand.split()):
        return SlotResult(_title(words), raw=cand)
    if len(cand.split()) <= 4 and re.fullmatch(rf"[{_NAME_CHARS} ]+", cand) and not any(normalize(w) in STOP_NAME for w in cand.split()):
        return SlotResult(error="nome_invalido", raw=cand)
    return SlotResult()


def extract_especie(norm: str) -> str | None:
    for tok in re.findall(r"[a-z]+", norm):
        if tok in SPECIES:
            return SPECIES[tok]
    return None


_PET_NOUNS = r"(?:cachorr[oa]s?|cachorrinh[oa]|c[aã]o|cadela|gat[oa]s?|gatinh[oa]|pet|coelh[oa]|p[aá]ssaro|hamster|tartaruga|animal|bichinho|filhote|calopsita|papagaio)"


def extract_nome_pet(raw: str, bare: bool) -> SlotResult:
    pats = [
        rf"(?i)\b(?:meu|minha)\s+{_PET_NOUNS}\s+(?:se\s+chama|chama|é|e)\s+(?:o |a )?([{_NAME_CHARS}]{{2,25}})",
        rf"(?i)\b(?:se chama|chama-se|nome (?:dele|dela|do pet|do cachorro|do gato|da pet|da cachorra|da gata) (?:é|e))\s+(?:o |a )?([{_NAME_CHARS}]{{2,25}})",
        rf"(?i)\b(?:pet|cachorro|gato|cachorra|gata)\s*[:\-]\s*([{_NAME_CHARS}]{{2,25}})",
        rf"\b(?:meu|minha|Meu|Minha)\s+{_PET_NOUNS}\s+(?:o |a )?([A-ZÀ-Ý][{_NAME_CHARS}]{{1,24}})",  # exige maiúscula
        rf"\b[Pp]r?a(?:ra)?\s+(?:o |a )?([A-ZÀ-Ý][{_NAME_CHARS}]{{1,24}})",  # "para o Thor"
    ]
    for p in pats:
        m = re.search(p, raw)
        if m:
            name = m.group(1)
            if normalize(name) not in STOP_NAME and normalize(name) not in STOP_AFTER:
                return SlotResult(_title([name]), raw=name)
    if not bare:
        return SlotResult()
    cand = re.sub(r"(?i)^\s*(?:é |e |eh |se chama |chama |o |a |nome )+", "", raw.strip()).strip(" .!")
    if "?" in raw or not cand:
        return SlotResult()
    if re.search(r"\d", cand):
        return SlotResult(error="nome_pet_invalido", raw=cand)
    words = cand.split()
    if 1 <= len(words) <= 2 and re.fullmatch(rf"[{_NAME_CHARS} ]{{2,30}}", cand) and not any(normalize(w) in STOP_NAME for w in words):
        return SlotResult(_title(words), raw=cand)
    if len(words) <= 3 and re.fullmatch(rf"[{_NAME_CHARS} ]+", cand) and not any(normalize(w) in STOP_NAME for w in words):
        return SlotResult(error="nome_pet_invalido", raw=cand)
    return SlotResult()


# ---------------------------------------------------------------- e-mail
EMAIL_STRICT = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
SKIP_EMAIL_RE = re.compile(r"\b(pular|pula|prefiro nao|nao quero informar|nao tenho|sem e-?mail|nao informar|nao precisa)\b")


def parse_email(raw: str, norm: str, awaiting: bool) -> SlotResult:
    m = EMAIL_STRICT.search(raw)
    if m:
        return SlotResult(m.group().lower())
    if awaiting and SKIP_EMAIL_RE.search(norm):
        return SlotResult("nao_informado")
    if "@" in raw or (awaiting and re.search(r"\S+\.\S+", raw) and " " not in raw.strip()):
        return SlotResult(error="email_invalido", raw=raw.strip()[:60])
    return SlotResult()


# ---------------------------------------------------------------- data
def _roll_year(this_year: SlotResult, next_year: SlotResult, today: date) -> SlotResult:
    """Data sem ano: se já passou há MAIS de 30 dias, assume o ano seguinte; se passou há pouco, é data passada."""
    if this_year.value and (today - date.fromisoformat(this_year.value)).days > 30:
        return next_year
    return this_year


def parse_date(norm: str, today: date, bare_number: bool = False) -> SlotResult:
    """Interpreta a data; devolve value=ISO ou error ('data_inexistente'). A regra de negócio fica em Agenda."""
    def build(d: int, m: int, y: int, raw: str) -> SlotResult:
        try:
            return SlotResult(date(y, m, d).isoformat(), raw=raw)
        except ValueError:
            return SlotResult(error="data_inexistente", raw=raw)

    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", norm)
    if m:
        return build(int(m.group(3)), int(m.group(2)), int(m.group(1)), m.group())
    m = re.search(r"(?<![\d:])(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?(?![\d:])", norm)
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        if m.group(3):
            y = int(m.group(3))
            y += 2000 if y < 100 else 0
            return build(d, mo, y, m.group())
        return _roll_year(build(d, mo, today.year, m.group()), build(d, mo, today.year + 1, m.group()), today)
    m = re.search(r"\b(\d{1,2})\s+de\s+(" + "|".join(MONTHS) + r")(?:\s+de\s+(\d{4}))?\b", norm)
    if m:
        d, mo = int(m.group(1)), MONTHS[m.group(2)]
        if m.group(3):
            return build(d, mo, int(m.group(3)), m.group())
        return _roll_year(build(d, mo, today.year, m.group()), build(d, mo, today.year + 1, m.group()), today)
    if re.search(r"\bdepois de amanha\b", norm):
        return SlotResult((today + timedelta(days=2)).isoformat(), raw="depois de amanhã")
    if re.search(r"\bamanha\b", norm):
        return SlotResult((today + timedelta(days=1)).isoformat(), raw="amanhã")
    if re.search(r"\bhoje\b", norm):
        return SlotResult(today.isoformat(), raw="hoje")
    m = re.search(r"\b(?:dia\s+)(\d{1,2})\b(?!\s*(?:h|:|horas))", norm) or (re.fullmatch(r"\s*(?:dia\s+)?(\d{1,2})\s*", norm) if bare_number else None)
    if m:
        d = int(m.group(1))
        mo, y = today.month, today.year
        if d <= today.day:
            mo, y = (1, y + 1) if mo == 12 else (mo + 1, y)
        return build(d, mo, y, f"dia {d}")
    m = re.search(r"\b(?:(proxim[oa])\s+)?(segunda|terca|quarta|quinta|sexta|sabado|domingo)(?:\s*-?\s*feira)?\b", norm)
    if m:
        wd = WEEKDAYS[m.group(2)]
        delta = (wd - today.weekday()) % 7 or 7
        target = today + timedelta(days=delta)
        if re.search(r"semana que vem|proxima semana|semana seguinte", norm):
            next_monday = today + timedelta(days=7 - today.weekday())
            target = next_monday + timedelta(days=wd)
        return SlotResult(target.isoformat(), raw=m.group())
    return SlotResult()


# ---------------------------------------------------------------- horário / período
def parse_periodo(norm: str) -> str | None:
    if re.search(r"\b(manha)\b", norm):
        return "manha"
    if re.search(r"\b(tarde)\b", norm):
        return "tarde"
    if re.search(r"\b(noite)\b", norm):
        return "noite"
    return None


# escolha por ordem ("a primeira", "o segundo", "a segunda opção"). "segunda-feira" NÃO é ordinal.
_OPTION_RE = re.compile(
    r"\b(primeir[oa]|segundo|terceir[oa]|ultim[oa])\b"
    r"|\b(?:a|na)\s+(segunda)\b(?!\s*-?\s*feira)"
    r"|\b(segunda)\s+(?:opcao|horario)\b"
)
_OPTION_IDX = {"primeir": 0, "segund": 1, "terceir": 2, "ultim": -1}


def option_phrase(norm: str) -> tuple[int, str] | None:
    """Se a frase escolhe uma opção por ordem, devolve (índice, trecho)."""
    m = _OPTION_RE.search(norm)
    if m and (len(norm.split()) <= 4 or "opcao" in norm or "horario" in norm):
        word = next(g for g in m.groups() if g)
        idx = _OPTION_IDX[next(k for k in _OPTION_IDX if word.startswith(k))]
        return idx, m.group()
    return None


def parse_time(norm: str, awaiting: bool, offered: list[str]) -> SlotResult:
    """Retorna HH:MM. Aceita 9h30, 09:30, 'às 14', 'meio-dia' e escolha por ordem ('a primeira')."""
    if awaiting and offered:
        opt = option_phrase(norm)
        if opt:
            try:
                return SlotResult(offered[opt[0]], raw=opt[1])
            except IndexError:
                return SlotResult(error="opcao_invalida", raw=opt[1])
    if re.search(r"\bmeio[ -]?dia\b", norm):
        return SlotResult("12:00", raw="meio-dia")
    m = re.search(r"(?<![\d/])(\d{1,2})\s*(?:h|hs|horas?|:)\s*(\d{2})?(?![\d/])", norm)
    if not m:
        m2 = re.search(r"\b(?:as|a)\s+(\d{1,2})\b(?!\s*(?:/|de\b|dias?\b))", norm)
        if m2:
            m = m2
        elif awaiting and re.fullmatch(r"\s*(\d{1,2})\s*", norm):
            m = re.fullmatch(r"\s*(\d{1,2})\s*", norm)
    if not m:
        return SlotResult()
    hh = int(m.group(1))
    mm = int(m.group(2)) if m.lastindex and m.lastindex >= 2 and m.group(2) else 0
    raw = m.group().strip()
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return SlotResult(error="horario_invalido", raw=raw)
    return SlotResult(f"{hh:02d}:{mm:02d}", raw=raw)
