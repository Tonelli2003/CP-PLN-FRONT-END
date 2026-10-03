"""NLU por regras/regex: classifica a intenção de cada mensagem.

Decisão de projeto (regra × LLM): intenção é decidida por regras — é rápida, determinística, auditável e
não gasta tokens. Casos sensíveis (emergência, humano, reclamação) NÃO podem depender de um LLM pequeno.
Os padrões operam sobre o texto normalizado (minúsculas, sem acento).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

INTENTS = [
    "saudacao", "agendar", "faq", "retomar", "confirmar", "negar", "abortar", "agradecimento", "despedida",
    "identidade", "ajuda", "humano", "emergencia", "tema_sensivel", "reclamacao", "orientacao_medica",
    "fora_de_escopo", "prompt_injection", "menu_opcao", "desconhecido",
]


@dataclass
class IntentResult:
    label: str
    confidence: float
    cues: list[str] = field(default_factory=list)


def _rx(*patterns: str) -> re.Pattern:
    return re.compile("|".join(f"(?:{p})" for p in patterns))


EMERGENCY_STRONG = _rx(
    r"envenen", r"intoxic", r"atropel", r"convuls", r"nao (esta |ta )?respirando", r"nao respira",
    r"sem respirar", r"falta de ar", r"dificuldade (pra|para|de) respirar", r"engasg", r"desmai",
    r"desacordado", r"inconsciente", r"hemorragia", r"sangrando (muito|bastante)", r"muito sangue",
    r"(comeu|ingeriu|engoliu|tomou) .{0,25}(veneno|chumbinho|chocolate|remedio|medicamento|produto de limpeza|raticida|cebola|uva|xilitol)",
    r"(caiu|pulou) .{0,15}(janela|sacada|andar)", r"nao consegue (levantar|andar|ficar em pe)", r"paralis",
    r"gengiva (branca|palida|azul)", r"barriga (dura|inchada)", r"reacao alergica", r"socorro",
)
EMERGENCY_GENERIC = _rx(r"\burgente\b", r"\burgencia\b", r"\bemergencia\b")
QUESTION_FRAME = _rx(
    r"\b(voces|vcs|a clinica|ai)\s+(atendem|tem|tm|fazem|possuem|oferecem|aceitam)\b",
    r"\b(tem|ha|existe)\s+(plantao|urgencia|emergencia)\b", r"\bse (voces|vcs)\b",
)
SENSIVEL = _rx(
    r"\b(morreu|faleceu|falecimento|eutanasi\w*|sacrificar|nao resistiu|luto)\b",
    r"\bperdi (o |a )?(meu|minha) (cachorr\w+|gat\w+|pet|bichinho|cao)\b",
    r"\bmorte (do|da|de) (meu|minha)\b",
)
HUMANO = _rx(
    r"\b(falar|conversar|passar|transferir|chamar|encaminhar|me passa|me passe|me transfere|me transfira)\b.{0,30}\b(atendente|humano|pessoa|gente|alguem|funcionario|funcionaria|recepcao|recepcionista|veterinari[oa]|doutor[a]?|responsavel|gerente|supervisor)\b",
    r"\batendente\b", r"\bhumano\b", r"pessoa de verdade", r"alguem de verdade", r"atendimento humano", r"\brecepcionista\b",
)
RECLAMACAO = _rx(
    r"reclam(ar|acao|ei)", r"\bprocon\b", r"pessimo atendimento", r"mau atendimento", r"descaso",
    r"vou processar", r"\badvogad[oa]\b", r"\bjustica\b", r"cobranca indevida", r"cobraram (a mais|errado|indevid\w+)",
    r"fui cobrad[oa]", r"reembolso", r"estorno", r"devolucao do dinheiro", r"\bqueixa\b", r"denunci",
    r"ninguem (me )?(responde|atende|retorna)", r"maltrat", r"erro medico", r"negligencia", r"machucaram",
)
MEDICO_SINTOMA = _rx(
    r"vomit", r"diarrei", r"\bfebre\b", r"\btosse\b", r"espirr", r"coceira", r"alergia", r"mancan",
    r"nao (quer|esta querendo|quis) comer", r"sem apetite", r"apatic", r"\bcaroco\b", r"\bferidas?\b",
    r"\bdor\b", r"inchad", r"olho (vermelho|inchado)", r"queda de pelo", r"\bpulgas?\b", r"carrapato", r"\bvermes?\b",
    r"sangue (na|no|nas)", r"tremendo", r"manchas? na pele",
)
MEDICO_PEDIDO = _rx(
    r"\b(dipirona|paracetamol|ibuprofeno|dramin|buscopan|tramadol|benzetacil|ivermectina|prednisolona|amoxicilina|rivotril|tylenol|aspirina)\b",
    r"\b(dose|dosagem)\b", r"que remedio", r"qual remedio", r"remedio caseiro", r"posso dar", r"devo dar",
    r"o que (eu )?(posso )?dar", r"diagnostic", r"pode ser (o que|grave)", r"e grave\b",
)
FORA_ESCOPO = _rx(
    r"(receita de|escreva|escrever|crie|criar|faca|fazer).{0,25}(codigo|poema|poesia|texto|redacao|historia|musica|carta|resumo|receita|programa)",
    r"\b(python|javascript|sql|java)\b", r"\b(futebol|politica|eleicao|presidente|bitcoin|criptomoeda|horoscopo|loteria|filme|serie|novela|previsao do tempo)\b",
    r"\bpiada\b", r"\btraduz(a|ir)\b", r"quanto (e|eh|da) \d+ ?[\+\-\*x/] ?\d+", r"capital d[aeo]", r"quem (descobriu|inventou|ganhou)",
    r"\b(imposto de renda|financiamento|emprestimo)\b",
)
ABORTAR = _rx(
    r"deixa (pra|para) la", r"\besquece\b", r"\bdesist\w+", r"nao quero mais", r"cancel\w* (isso|tudo|o agendamento|agendamento)",
    r"recomecar", r"comecar (de novo|do zero)", r"voltar ao inicio", r"^(cancelar?|sair|parar|voltar)\W*$",
)
IDENTIDADE = _rx(
    r"voce (e|eh) (um |uma )?(robo|bot|ia|inteligencia artificial|humano|humana|pessoa|gente|real|maquina)",
    r"(e|eh) (um |uma )?(robo|bot)\b", r"com quem (eu )?(estou|to) falando", r"quem (e|eh) voce", r"qual (e )?(o )?seu nome",
    r"\bvoce (e|eh) de verdade\b",
)
AJUDA = _rx(
    r"o que voce (faz|pode fazer|consegue)", r"como (voce )?(pode|vai) (me )?ajudar", r"\bajuda\b", r"\bmenu\b",
    r"quais (sao )?(as )?(suas )?(opcoes|funcoes)", r"em que (voce )?pode",
)
RETOMAR = _rx(
    r"aquele (horario|dia|dado)", r"e aquele", r"(que|o que) voce (sugeriu|falou|disse|ofereceu|propos|mencionou)",
    r"voce (sugeriu|ofereceu|propos|mencionou)", r"qual (era|foi) (o|a) (horario|data|nome)",
    r"qual (e |era )?(o )?nome d[oa] (meu|minha)", r"nome d[oa] (meu |minha )?(pet|cachorr\w*|gat\w*|bichinh\w*) (mesmo|era|e)\b",
    r"(como|que) (eu )?(disse|falei|informei)", r"qual (e |era )?(o )?meu nome", r"\b(repete|repita)\b",
    r"\blembra\b", r"o que (eu )?(ja )?(informei|passei|falei|disse)", r"quais (sao )?(os )?(horarios|dados) (que )?(voce )?(sugeriu|tem)",
)
DESPEDIDA = _rx(r"\b(tchau|ate (mais|logo|breve|amanha|a proxima)|adeus|flw|era so isso|so isso|nada mais|encerrar|pode encerrar|finalizar)\b")
AGRADECIMENTO = _rx(r"\b(obrigad[oa]|brigad[oa]|valeu|agradec\w+|grato|grata|gratidao)\b")
SAUDACAO = _rx(r"^(oi+|ola|opa|e ai|eai|bom dia|boa tarde|boa noite|hey|hello|hi|salve|oie)\b")
AGENDAR_VERB = _rx(r"(?<![a-z])(marcar|agendar|agendamento|marcacao|reservar)\b")
AGENDAR_NEED = _rx(
    r"\b(quero|queria|gostaria|preciso|precisava|precisamos|desejo)\b.{0,25}\bconsulta\b", r"\bnova consulta\b",
    r"\bconsulta (para|pro|pra) (o |a )?(meu|minha)\b", r"\b(tem|ha|existe)\b.{0,15}\b(horario|vaga|encaixe)\b.{0,20}\b(consulta|atendimento|dia|amanha|semana|sexta|segunda|terca|quarta|quinta|sabado)\b",
    r"\b(levar|trazer) (o |a )?(meu|minha) \w+ (na|ao|a) (veterinari\w+|clinica)\b",
)
INFO_QUESTION = _rx(r"\b(quanto|qual|quais|onde|que horas|aceita\w*|funciona\w*|abre\w*|fecha\w*|custa|valor|preco|endereco)\b", r"\?")


def detect_intent(norm: str, flow_active: bool = False) -> IntentResult:
    """Classifica a mensagem. Ordem = prioridade: segurança primeiro, depois escopo, depois fluxo."""
    if EMERGENCY_STRONG.search(norm):
        return IntentResult("emergencia", 0.95, ["emergencia_forte"])
    if EMERGENCY_GENERIC.search(norm) and not QUESTION_FRAME.search(norm):
        return IntentResult("emergencia", 0.8, ["urgencia"])
    if SENSIVEL.search(norm):
        return IntentResult("tema_sensivel", 0.9, ["luto"])
    if HUMANO.search(norm):
        return IntentResult("humano", 0.9, ["pedido_humano"])
    if RECLAMACAO.search(norm):
        return IntentResult("reclamacao", 0.85, ["reclamacao"])

    agendar_verb = bool(AGENDAR_VERB.search(norm))
    agendar_need = bool(AGENDAR_NEED.search(norm))
    if MEDICO_PEDIDO.search(norm) or (MEDICO_SINTOMA.search(norm) and not agendar_verb):
        if not (agendar_verb or agendar_need) or MEDICO_PEDIDO.search(norm):
            return IntentResult("orientacao_medica", 0.85, ["clinico"])
    if FORA_ESCOPO.search(norm):
        return IntentResult("fora_de_escopo", 0.85, ["fora_escopo"])
    if flow_active and ABORTAR.search(norm):
        return IntentResult("abortar", 0.9, ["abortar"])
    if IDENTIDADE.search(norm):
        return IntentResult("identidade", 0.9, ["identidade"])
    if RETOMAR.search(norm):
        return IntentResult("retomar", 0.85, ["retomar"])
    if DESPEDIDA.search(norm):
        return IntentResult("despedida", 0.9, ["despedida"])
    if AGRADECIMENTO.search(norm):
        return IntentResult("agradecimento", 0.9, ["agradecimento"])
    if AJUDA.search(norm):
        return IntentResult("ajuda", 0.8, ["ajuda"])
    if agendar_verb:
        return IntentResult("agendar", 0.9, ["verbo_agendar"])
    if agendar_need:
        return IntentResult("agendar", 0.7, ["necessidade_consulta", "need_only"])
    if SAUDACAO.search(norm):
        return IntentResult("saudacao", 0.85, ["saudacao"])
    return IntentResult("desconhecido", 0.2, [])


def is_info_question(norm: str) -> bool:
    return bool(INFO_QUESTION.search(norm))


def parse_menu_choice(norm: str) -> str | None:
    """Resposta ao menu do fallback: 1 agendar | 2 dúvidas | 3 atendente (número ou palavra)."""
    n = norm.strip(" .!")
    if re.fullmatch(r"(op[cç]ao )?1", n) or re.search(r"\bagendar\b|\bmarcar\b", n):
        return "agendar"
    if re.fullmatch(r"(opcao )?2", n) or re.search(r"\bduvidas?\b", n):
        return "duvidas"
    if re.fullmatch(r"(opcao )?3", n):
        return "atendente"
    return None
