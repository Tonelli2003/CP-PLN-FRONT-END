"""Textos-base (templates) da Duda. São a rede de segurança: toda resposta crítica sai daqui, sem LLM."""
from __future__ import annotations

from ..nlp.extractors import DAYS_IN_MONTH_PT

BOT = "Duda"
CLINICA = "Clínica Veterinária Patas & Cia"
TEL = "(11) 5550-0123"
WEEKDAYS_PT = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]

CAPABILITIES = [
    "Agendar uma consulta",
    "Tirar dúvidas: horários, endereço, valores, vacinas, pagamento, remarcação",
    "Chamar um atendente humano",
]


# ----------------------------------------------------------------- formatação
def fmt_time(hhmm: str) -> str:
    h, m = hhmm.split(":")
    return f"{int(h)}h" if m == "00" else f"{int(h)}h{m}"


def fmt_date(iso: str) -> str:
    from datetime import date
    d = date.fromisoformat(iso)
    return f"{WEEKDAYS_PT[d.weekday()]}, {d.day:02d}/{d.month:02d}"


def fmt_date_full(iso: str) -> str:
    from datetime import date
    d = date.fromisoformat(iso)
    return f"{WEEKDAYS_PT[d.weekday()]}, {d.day:02d}/{d.month:02d}/{d.year}"


def join_ou(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " ou " + items[-1]


# ----------------------------------------------------------------- saudação e social
def greeting() -> str:
    return (
        f"Oi! Eu sou a {BOT}, assistente virtual (uma IA) da {CLINICA} 🐾\n"
        "Posso agendar uma consulta, tirar dúvidas (horários, endereço, valores, vacinas, pagamento) "
        "ou chamar um atendente humano. Não faço diagnóstico nem indico remédios: isso é com nossos veterinários.\n"
        "Como posso ajudar você hoje?"
    )


def saudacao() -> str:
    return "Oi! Posso agendar uma consulta, tirar dúvidas sobre a clínica ou chamar um atendente. O que você precisa?"


def ajuda() -> str:
    return ("Eu consigo: 1) agendar uma consulta, 2) responder dúvidas (horários, endereço, valores, vacinas, pagamento, "
            "remarcação) e 3) chamar um atendente humano. Não faço diagnóstico nem indico remédios. Por onde começamos?")


def identidade() -> str:
    return (f"Sou a {BOT}, assistente virtual (uma inteligência artificial, não uma pessoa) da {CLINICA}. "
            "Posso agendar consultas e tirar dúvidas, e chamo um atendente humano quando preciso. No que posso ajudar?")


def agradecimento() -> str:
    return "Por nada! Posso ajudar em mais alguma coisa?"


def despedida() -> str:
    return "Foi um prazer ajudar! Até a próxima, e um carinho no seu pet 🐾"


def faq_menu(topicos: list[str]) -> str:
    return "Claro! Posso falar sobre: " + ", ".join(topicos) + ". Qual dessas dúvidas você tem?"


# ----------------------------------------------------------------- fallback
def fallback_opcoes() -> str:
    return ("Desculpe, não entendi bem o que você precisa. Posso ajudar com:\n"
            "1. Agendar uma consulta\n2. Tirar dúvidas (horários, valores, vacinas, endereço)\n3. Falar com um atendente\n"
            "Qual dessas opções?")


def fora_da_base() -> str:
    return (f"Essa informação eu não tenho com segurança, e prefiro não inventar. Você pode ligar para a recepção em {TEL}, "
            "ou eu posso:\n1. Agendar uma consulta\n2. Responder outra dúvida\n3. Chamar um atendente\nO que prefere?")


def oferta_humano() -> str:
    return ("Ainda não consegui entender, e peço desculpas. Prefere falar com um atendente da clínica? "
            "Responda “sim” e eu transfiro, ou me diga de outro jeito o que precisa (por exemplo: “quero marcar uma consulta”).")


def fallback_slot(descricao: str, exemplo: str) -> str:
    return (f"Não consegui entender {descricao}. {exemplo} "
            "(Se preferir, diga “atendente” para falar com uma pessoa ou “cancelar” para sair.)")


def recusa_nao_aceite_humano() -> str:
    return "Tudo bem! Me conte o que você precisa, por exemplo: “quero marcar uma consulta” ou “qual o valor da consulta?”."


# ----------------------------------------------------------------- guardrails
def recusa_injection() -> str:
    return (f"Sou a {BOT}, assistente da {CLINICA}, e não posso mudar nem compartilhar minhas instruções. "
            "Posso ajudar a agendar uma consulta ou tirar dúvidas sobre a clínica. O que prefere?")


def recusa_medica() -> str:
    return ("Entendo a preocupação com seu pet, mas não posso diagnosticar nem indicar remédios ou doses: isso exige um veterinário "
            "examinando o animal.\n1. Agendar uma consulta\n2. Falar com um atendente\nO que prefere?")


def recusa_fora_escopo() -> str:
    return "Esse assunto foge do que eu faço por aqui: cuido de agendamentos e dúvidas da clínica. Posso ajudar com algum desses?"


def aviso_dado_sensivel() -> str:
    return "Por segurança, não peço nem guardo CPF ou dados de cartão por aqui, e apaguei isso da conversa. "


def empatia() -> str:
    return "Entendo, sinto muito por isso. "


# ----------------------------------------------------------------- handoff
def handoff_msg(reason: str, protocolo: str) -> str:
    base = {
        "emergencia": (f"Sinto muito, isso parece uma emergência. Leve seu pet agora ao hospital veterinário 24h mais próximo e, "
                       f"se puder, ligue para {TEL}. Já registrei o caso como URGENTE para a equipe da clínica. Protocolo: {protocolo}."),
        "tema_sensivel": (f"Sinto muito pelo que você está passando. Um momento assim merece uma conversa com uma pessoa, "
                          f"então estou encaminhando você a um atendente da clínica, com um resumo para você não precisar repetir nada. Protocolo: {protocolo}."),
        "reclamacao": (f"Sinto muito pela experiência, você tem razão em esperar um atendimento melhor. Estou transferindo agora para um atendente humano "
                       f"e já deixei um resumo para você não precisar repetir tudo. Protocolo: {protocolo}."),
        "frustracao": (f"Sinto muito pela frustração, e você tem razão em esperar mais de mim. Vou transferir para um atendente humano "
                       f"com um resumo da conversa. Protocolo: {protocolo}."),
        "sentimento_negativo_recorrente": (f"Percebo que esta conversa não está sendo boa para você, e peço desculpas. Vou transferir para um atendente humano "
                                           f"com um resumo do que já conversamos. Protocolo: {protocolo}."),
        "pedido_do_usuario": (f"Claro! Estou transferindo você para um atendente humano, com um resumo da conversa. Protocolo: {protocolo}."),
        "falha_repetida": (f"Peço desculpas por não ter conseguido ajudar. Vou transferir você para um atendente humano, "
                           f"com um resumo do que conversamos. Protocolo: {protocolo}."),
    }.get(reason, f"Vou transferir você para um atendente humano. Protocolo: {protocolo}.")
    if reason == "emergencia":
        return base
    return base + " A equipe atende de segunda a sexta, das 8h às 18h, e aos sábados, das 8h às 12h; seu caso fica na fila."


def handoff_espera(protocolo: str) -> str:
    return (f"Seu caso já está com a equipe da clínica (protocolo {protocolo}). Posso anotar mais algum detalhe para o atendente? "
            "O que você escrever aqui será anexado ao seu atendimento.")


def handoff_espera_urgente(protocolo: str) -> str:
    return (f"Isso é urgente: leve seu pet agora ao hospital veterinário 24h mais próximo e, se puder, ligue para {TEL}. "
            f"Atualizei o seu caso (protocolo {protocolo}) como URGENTE.")


# ----------------------------------------------------------------- fluxo de agendamento
def ask_nome() -> str:
    return "Vamos agendar! Para começar, qual é o seu nome?"


def ask_pet(nome: str | None, especie: str | None) -> str:
    quem = f"do seu {especie}" if especie in ("cachorro", "gato", "coelho") else "do seu pet"
    pre = f"Prazer, {nome}! " if nome else ""
    return f"{pre}Qual é o nome {quem}?"


def ask_data(pet: str | None) -> str:
    pre = f"Ótimo, {pet}! " if pet else ""
    return f"{pre}Para qual dia você gostaria da consulta? (ex.: sexta, 15/10 ou amanhã)"


def offer_times(iso: str, times: list[str]) -> str:
    return f"Para {fmt_date(iso)}, tenho {join_ou([fmt_time(t) for t in times])}. Qual prefere?"


def ask_email(iso: str, hhmm: str) -> str:
    return (f"Anotei {fmt_date(iso)} às {fmt_time(hhmm)}. Para enviar a confirmação, qual é o seu e-mail? "
            "(se preferir não informar, responda “pular”)")


def confirm(slots: dict) -> str:
    email = slots.get("email")
    email_txt = "não informado" if email in (None, "nao_informado") else email
    return (f"Só confirmando: consulta do {slots['nome_pet']} (tutor(a): {slots['nome_tutor']}), "
            f"{fmt_date_full(slots['data'])} às {fmt_time(slots['horario'])}. E-mail: {email_txt}. Posso confirmar? (sim/não)")


def booked(slots: dict, protocolo: str) -> str:
    return (f"Agendado! Consulta do {slots['nome_pet']} em {fmt_date_full(slots['data'])} às {fmt_time(slots['horario'])}. "
            f"Seu protocolo é {protocolo}. Leve a carteirinha de vacinação, se tiver, e chegue 10 minutos antes. "
            "Posso ajudar em mais alguma coisa?")


def confirm_unclear() -> str:
    return "Só preciso saber se posso confirmar o agendamento: responda “sim” para confirmar ou “não” para escolher outra data ou horário."


def reagendar_apos_nao() -> str:
    return "Sem problema! Vamos escolher outro momento. Para qual dia você prefere?"


def abortado() -> str:
    return "Tudo bem, cancelei o agendamento em andamento. Posso ajudar com outra coisa?"


def flow_repeat_hint(pending: str) -> str:
    return f"Voltando ao agendamento: {pending}"


def agendamento_ja_em_andamento(pending: str) -> str:
    return f"Já estamos agendando! {pending}"


def lembrete_slots(slots: dict) -> str:
    partes = []
    if slots.get("nome_tutor"):
        partes.append(f"seu nome é {slots['nome_tutor']}")
    if slots.get("nome_pet"):
        partes.append(f"seu pet se chama {slots['nome_pet']}")
    if slots.get("data"):
        partes.append(f"a data escolhida é {fmt_date(slots['data'])}")
    if slots.get("horario"):
        partes.append(f"o horário é {fmt_time(slots['horario'])}")
    return "Até agora tenho: " + "; ".join(partes) + "." if partes else "Ainda não tenho nenhum dado seu."


def retomar_horarios(iso: str, times: list[str]) -> str:
    return f"Eu tinha sugerido, para {fmt_date(iso)}: {join_ou([fmt_time(t) for t in times])}. Qual prefere?"


def retomar_pet(nome: str) -> str:
    return f"O nome do seu pet que eu anotei é {nome}."


def retomar_nome(nome: str) -> str:
    return f"O seu nome que eu anotei é {nome}."


# ----------------------------------------------------------------- erros de validação (por código)
def erro_validacao(code: str, **kw) -> str:
    raw = kw.get("raw") or ""
    if code == "data_inexistente":
        return f"A data “{raw}” não existe no calendário. Pode me informar outra data? (ex.: sexta, 15/10 ou amanhã)"
    if code == "data_passada":
        return "Essa data já passou. Para qual dia futuro você gostaria da consulta?"
    if code == "data_hoje":
        return (f"Para o mesmo dia eu não consigo agendar por aqui. Pode escolher a partir de amanhã? "
                f"Se for urgente, ligue para a recepção: {TEL}.")
    if code == "data_distante":
        d = kw["detail"]
        return f"Só consigo agendar até {d[8:10]}/{d[5:7]}/{d[:4]}. Pode escolher uma data mais próxima?"
    if code == "clinica_fechada":
        return f"Nesse dia a clínica está fechada ({kw.get('detail')}). Pode escolher outra data?"
    if code == "dia_lotado":
        return "Esse dia está sem horários livres. Quer tentar outra data?"
    if code == "horario_invalido":
        return f"O horário “{raw}” não é válido. Pode informar de novo? (ex.: 9h30 ou 14h)"
    if code == "opcao_invalida":
        return "Não encontrei essa opção na lista. Pode me dizer o horário que prefere? (ex.: 9h30)"
    if code == "email_invalido":
        return f"Esse e-mail parece incompleto (“{raw}”). Pode digitar de novo? (ex.: nome@exemplo.com) Ou responda “pular”."
    if code == "nome_invalido":
        return "Não consegui entender o nome. Pode me dizer só o seu nome? (ex.: Marina Alves)"
    if code == "nome_pet_invalido":
        return "Não consegui entender o nome do pet. Pode digitar só o nome dele? (ex.: Thor)"
    return "Não consegui validar essa informação. Pode repetir?"


def horario_indisponivel(iso: str, hhmm: str, times: list[str]) -> str:
    if not times:
        return f"Às {fmt_time(hhmm)} não tenho vaga em {fmt_date(iso)}, e o dia está sem outros horários. Quer tentar outra data?"
    return (f"Às {fmt_time(hhmm)} não tenho vaga em {fmt_date(iso)}. Tenho {join_ou([fmt_time(t) for t in times])}. Qual prefere?")


def oferta_humano_slot() -> str:
    return "Se estiver ficando difícil, posso transferir você para um atendente: é só responder “sim”."
