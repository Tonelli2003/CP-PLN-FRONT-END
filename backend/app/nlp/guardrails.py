"""Guardrails em código.

ENTRADA : prompt injection · dado sensível (CPF/cartão) · (tema proibido/clínico e fora de escopo ficam no NLU)
SAÍDA   : tamanho máximo · promessas indevidas · orientação clínica/dose · vazamento de persona/prompt ·
          fatos inventados (números que não estão no texto-base) · pergunta única.
Cada disparo vira um evento registrado no log por turno.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .text import normalize, number_set

# ------------------------------------------------------------------ ENTRADA
INJECTION = re.compile("|".join(f"(?:{p})" for p in [
    r"ignor\w*\s+(todas?\s+)?(as\s+|suas\s+|seus\s+|tuas\s+|essas\s+|estas\s+)?(instrucoes|regras|ordens|diretrizes|prompt|comandos)",
    r"(esqueca|desconsidere|desobedeca|descarte|apague)\s+.{0,25}(instrucoes|regras|tudo|prompt|comandos)",
    r"(mostre|revele|exiba|imprima|repita|diga|me passe|me mostre|liste|vaze)\b.{0,30}\b(prompt|instrucoes|regras internas|configuracao|system|diretrizes)",
    r"\bsystem\s*prompt\b", r"prompt (do sistema|inicial|original|secreto)", r"seu prompt", r"suas instrucoes",
    r"(a partir de agora|agora) voce (e|sera|vai ser|vai agir|deve agir)",
    r"\b(finja|aja|atue|haja)\s+(que|como|ser)\b", r"faca de conta que", r"\brole-?play\b",
    r"modo\s+(desenvolvedor|dev|deus|dan|sem restricoes|livre|admin)", r"\bjailbreak\b", r"\bdan\b", r"do anything now",
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", r"reveal\s+(your\s+)?(system\s+)?prompt",
    r"\bdisregard\b", r"you are now", r"\bact as\b", r"pretend to be",
    r"sem\s+(filtros|restricoes|limites|regras)",
    r"</?\s*(system|assistant|instructions?)\s*>", r"\[\s*(system|inst)\s*\]",
    r"(troque|mude|altere) (sua|a sua) (persona|personalidade|funcao)",
]))


def detect_prompt_injection(norm: str) -> str | None:
    m = INJECTION.search(norm)
    return m.group() if m else None


# ------------------------------------------------------------------ SAÍDA
PERSONA_LEAK = re.compile("|".join(f"(?:{p})" for p in [
    r"\bsystem prompt\b", r"meu prompt", r"minhas instrucoes (sao|dizem|incluem)", r"fui (programad[oa]|instruid[oa]) (para|a)",
    r"como (um|uma) (modelo de linguagem|ia|inteligencia artificial)", r"\b(sou|fui criad[oa] (pel[oa])?) (o )?(qwen|llama|gpt|chatgpt|gemma|mistral|claude|openai|alibaba|meta)\b",
    r"camada \d", r"texto-base", r"diretiva do turno", r"<<base>>",
]))
FORBIDDEN_PROMISE = re.compile("|".join(f"(?:{p})" for p in [
    r"\bgaranto\b", r"\bgarantimos\b", r"100 ?%", r"vai (ficar bem|se curar|melhorar)", r"\bcura\b", r"\bprometo\b",
    r"\bdesconto\b", r"\bpromocao\b", r"\bsem custo\b", r"\bgratis\b", r"nao tem risco", r"com certeza (ele|ela|seu|sua)",
]))
CLINICAL = re.compile("|".join(f"(?:{p})" for p in [
    r"\b\d+\s?(mg|ml|mcg|gotas|comprimidos?)\b", r"\b(dipirona|paracetamol|ibuprofeno|amoxicilina|prednisolona|ivermectina|tramadol)\b",
    r"\bdose\b", r"\bdosagem\b", r"(seu|sua) (cachorro|cao|gato|gata|cadela|pet) (tem|esta com|sofre de)",
]))


@dataclass
class OutputCheck:
    ok: bool
    rule: str | None = None


def clean_llm_output(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"<<?/?BASE>>?", "", t)
    t = re.sub(r"^\s*(duda|assistente)\s*:\s*", "", t, flags=re.IGNORECASE)
    t = t.strip().strip('"“”').strip()
    t = re.sub(r"[*#`_]{1,3}", "", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t.strip()


def _shingles(norm: str, n: int = 7) -> set[str]:
    w = norm.split()
    return {" ".join(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}


def check_llm_output(reply: str, base: str, *, max_chars: int = 600, must_question: bool = False,
                     system_prompt: str = "") -> OutputCheck:
    """Valida o texto do LLM contra o texto-base curado. Qualquer falha => o orquestrador usa o texto-base."""
    if not reply or not reply.strip():
        return OutputCheck(False, "resposta_vazia")
    if len(reply) > max_chars:
        return OutputCheck(False, "tamanho_maximo")
    rn, bn = normalize(reply), normalize(base)
    if PERSONA_LEAK.search(rn):
        return OutputCheck(False, "vazamento_persona_ou_prompt")
    # vazamento = trecho do system prompt que NÃO veio do texto-base legítimo
    if system_prompt and (_shingles(rn) - _shingles(bn)) & _shingles(normalize(system_prompt)):
        return OutputCheck(False, "vazamento_de_prompt")
    if FORBIDDEN_PROMISE.search(rn) and not FORBIDDEN_PROMISE.search(bn):
        return OutputCheck(False, "promessa_indevida")
    if CLINICAL.search(rn) and not CLINICAL.search(bn):
        return OutputCheck(False, "orientacao_clinica")
    nr, nb = number_set(reply), number_set(base)
    if nr - nb:
        return OutputCheck(False, "fato_inventado")  # número (horário/preço/data/telefone) que não está no texto-base
    if nb - nr - {"0"}:
        return OutputCheck(False, "fato_omitido")
    if must_question and "?" not in reply:
        return OutputCheck(False, "sem_pergunta")
    if reply.count("?") > 1:
        return OutputCheck(False, "mais_de_uma_pergunta")
    return OutputCheck(True)


def check_final_reply(reply: str, max_chars: int = 600) -> OutputCheck:
    """Checagens baratas aplicadas a QUALQUER resposta final (template ou LLM)."""
    if len(reply) > max_chars:
        return OutputCheck(False, "tamanho_maximo")
    if PERSONA_LEAK.search(normalize(reply)):
        return OutputCheck(False, "vazamento_persona_ou_prompt")
    return OutputCheck(True)


def truncate_sentences(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    idx = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "), cut.rfind("\n"))
    return (cut[: idx + 1] if idx > max_chars * 0.4 else cut.rstrip() + "…").strip()
