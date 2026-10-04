"""Orquestrador / gerenciador de diálogo — o "cérebro" da Prosa.

Princípio central: O CÓDIGO DECIDE, O LLM VERBALIZA.
  • REGRA (código): intenção, sentimento, slots e sua validação, agenda, FAQ, guardrails, handoff, fallback.
  • LLM: dar voz natural ao texto-base curado (FAQ e perguntas do fluxo), sempre validado depois pelos
    guardrails de saída; se o LLM inventar um fato, o texto-base é usado no lugar.
  • Turnos críticos (emergência, handoff, guardrails, fallback, confirmação, erros de validação) NÃO dependem do LLM.

Cada turno é ATÔMICO: trabalhamos numa cópia da sessão e só gravamos se tudo der certo (ex.: se o LLM cair
e o modo for "error", a sessão não é alterada e a API devolve 503).
"""
from __future__ import annotations

import copy
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import date

from ..config import Settings
from ..knowledge.agenda import Agenda
from ..knowledge.faq import FaqKnowledge, FaqMatch
from ..llm.client import LLMClient, LLMUnavailableError
from ..memory.session_store import SessionNotFoundError, SessionState, SessionStore, new_slots
from ..memory.window import build_messages, state_block
from ..nlp import extractors as X
from ..nlp.guardrails import check_final_reply, check_llm_output, clean_llm_output, detect_prompt_injection, truncate_sentences
from ..nlp.nlu import IntentResult, detect_intent, is_info_question, parse_menu_choice
from ..nlp.sentiment import FRUSTRATION_THRESHOLD, Sentiment, analyze_sentiment
from ..nlp.text import detect_sensitive, mask_for_log, mask_sensitive, normalize, tokens
from ..analytics.logger import TurnLogger
from . import responses as R
from .clock import Clock
from .handoff import build_summary, priority_for

SLOT_ORDER = ["nome_tutor", "nome_pet", "data", "horario", "email"]
SLOT_DESC = {
    "nome_tutor": ("o seu nome", "Pode me dizer só o seu nome? (ex.: Marina Alves)"),
    "nome_pet": ("o nome do pet", "Pode digitar só o nome dele? (ex.: Thor)"),
<<<<<<< HEAD
    "data": ("a data", "Pode me dizer o dia? (ex.: sexta, 15/10 ou amanhã)"),
=======
    "data": ("a data", "Pode me dizer o dia? (ex.: sexta ou amanhã)"),
>>>>>>> 124e2bd (Atualizações no frontend e backend)
    "horario": ("o horário", "Pode me dizer qual horário prefere? (ex.: 9h30)"),
    "email": ("o e-mail", "Pode digitar de novo? (ex.: nome@exemplo.com) Ou responda “pular”."),
    "confirmacao": ("a sua resposta", "Responda “sim” para confirmar ou “não” para mudar."),
}
QUESTION_START = re.compile(r"^(voces|vcs|qual|quais|quanto|quando|onde|como|tem|ha|aceitam|aceita|fazem|atendem|existe|posso|da pra)\b")


@dataclass
class Extraction:
    changed: dict = field(default_factory=dict)
    raws: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)  # (slot, code, raw, detail)
    periodo: str | None = None


@dataclass
class Decision:
    user_text: str
    sentiment: Sentiment
    intent: str = "desconhecido"
    confidence: float = 0.2
    reply: str = ""
    source: str = "template"
    llm_used: bool = False
    fallback: bool = False
    fallback_type: str | None = None
    events: list = field(default_factory=list)
    handoff_new: bool = False
    goal: str | None = None
    faq_id: str | None = None
    flow_started: bool = False
    validation_error: str | None = None


@dataclass
class TurnResult:
    session_id: str
    reply: str
    intent: str
    intent_confidence: float
    slots: dict
    sentiment: dict
    fallback: bool
    fallback_type: str | None
    handoff: dict
    turn: int
    latency_ms: int
    source: str
    llm_used: bool
    guardrail_events: list
    flow: dict


def handoff_public(s: SessionState) -> dict:
    h = s.handoff
    return {"active": h["active"], "reason": h["reason"], "priority": h["priority"],
            "protocol": h["protocol"], "summary": h["summary"]}


class Orchestrator:
    def __init__(self, settings: Settings, store: SessionStore, llm: LLMClient, faq: FaqKnowledge,
                 agenda: Agenda, logger: TurnLogger, clock: Clock, system_prompt: str):
        self.cfg, self.store, self.llm, self.faq = settings, store, llm, faq
        self.agenda, self.logger, self.clock, self.system_prompt = agenda, logger, clock, system_prompt

    # ================================================================== API pública
    def start_session(self) -> tuple[SessionState, str]:
        s = self.store.create(self.clock.now_iso())
        greeting = R.greeting()
        s.history.append({"role": "assistant", "content": greeting, "ts": s.created_at})
        s.add_action("Saudação e apresentação das capacidades")
        self.store.save(s)
        return s, greeting

    def handle(self, session_id: str, message: str) -> TurnResult:
        t0 = time.perf_counter()
        self.store.get(session_id)  # 404 cedo
        with self.store.lock(session_id):
            s = copy.deepcopy(self.store.get(session_id))
            sent = analyze_sentiment(message)
            d = Decision(user_text=mask_sensitive(message), sentiment=sent)
            s.closed = False
            self._process(s, d, message)  # pode levantar LLMUnavailableError: nada é gravado
            reply = self._finalize_reply(d)
            now = self.clock.now_iso()
            s.history.append({"role": "user", "content": d.user_text, "ts": now})
            s.history.append({"role": "assistant", "content": reply, "ts": now})
            del s.history[:-400]
            s.turn += 1
            s.last_activity = now
            s.intents_seen.append(d.intent)
            del s.intents_seen[:-60]
            latency = int((time.perf_counter() - t0) * 1000)
            self.store.save(s)
            self._log(s, d, latency, now, message)
        return TurnResult(
            session_id=s.session_id, reply=reply, intent=d.intent, intent_confidence=round(d.confidence, 2),
            slots=dict(s.slots), sentiment=sent.as_dict(), fallback=d.fallback, fallback_type=d.fallback_type,
            handoff=handoff_public(s), turn=s.turn, latency_ms=latency, source=d.source, llm_used=d.llm_used,
            guardrail_events=d.events, flow={"state": s.flow, "awaiting": s.awaiting},
        )

    # ================================================================== pipeline
    def _process(self, s: SessionState, d: Decision, raw: str) -> None:
        norm = normalize(raw)
        today = self.clock.today()
        sent = d.sentiment

        # --- guardrail de entrada: dado sensível (mascara e segue)
        prefix = ""
        sens = detect_sensitive(raw)
        if sens:
            d.events.append({"stage": "input", "name": "dado_sensivel", "action": "mascarar", "detail": ",".join(sens)})
            prefix += R.aviso_dado_sensivel()

        # --- guardrail de entrada: prompt injection
        inj = detect_prompt_injection(norm)
        if inj:
            d.events.append({"stage": "input", "name": "prompt_injection", "action": "bloquear"})
            d.intent, d.confidence = "prompt_injection", 0.95
            d.reply = R.recusa_injection()
            s.add_action("Tentativa de alterar instruções bloqueada")
            return

        faq_hit = self.faq.buscar_faq(raw)
        res = detect_intent(norm, flow_active=(s.flow == "agendar"))
        d.intent, d.confidence = res.label, res.confidence

        # --- modo de espera: já transferido para humano
        if s.handoff["active"]:
            self._waiting_mode(s, d, raw, res)
            return

        # --- bookkeeping de sentimento
        s.consecutive_negative = s.consecutive_negative + 1 if sent.label == "negativo" else 0

        # --- segurança primeiro: situações que SEMPRE vão para humano
        safety = {"emergencia": "emergencia", "tema_sensivel": "tema_sensivel", "humano": "pedido_do_usuario", "reclamacao": "reclamacao"}
        if res.label in safety:
            return self._handoff(s, d, safety[res.label], raw)
        if sent.polarity <= FRUSTRATION_THRESHOLD:
            d.intent, d.confidence = "reclamacao", 0.7
            return self._handoff(s, d, "frustracao", raw)
        if s.consecutive_negative >= 2:
            d.intent, d.confidence = "reclamacao", 0.6
            return self._handoff(s, d, "sentimento_negativo_recorrente", raw)
        empathic = sent.label == "negativo"  # sentimento MUDA o comportamento: tom de acolhimento
        if empathic:
            d.events.append({"stage": "nlu", "name": "sentimento_negativo", "action": "tom_acolhimento"})
            prefix = R.empatia() + prefix

        # --- respostas a perguntas feitas pelo próprio bot (oferta de humano / menu)
        prev = s.awaiting
        if prev == "aceite_humano":
            resume, s.awaiting, s.resume_awaiting = s.resume_awaiting, s.resume_awaiting, None
            if X.is_yes(norm):
                return self._handoff(s, d, "falha_repetida" if s.consecutive_failures >= 2 else "pedido_do_usuario", raw)
            if X.is_no(norm):
                s.consecutive_failures = 0
                d.intent, d.confidence = "negar", 0.9
                d.reply = prefix + (R.recusa_nao_aceite_humano() if s.flow != "agendar" else self._pending_reprompt(s))
                return
        elif prev == "menu":
            s.awaiting = None
            choice = parse_menu_choice(norm)
            if choice == "atendente":
                return self._handoff(s, d, "pedido_do_usuario", raw)
            if choice == "duvidas":
                s.consecutive_failures = 0
                d.intent, d.confidence = "menu_opcao", 0.9
                d.reply = prefix + R.faq_menu(self.faq.topicos)
                return
            if choice == "agendar":
                d.intent, d.confidence = "agendar", 0.9
                return self._start_flow(s, d, raw, norm, today, prefix, empathic)

        # --- guardrails de tema: orientação clínica e fora de escopo
        if res.label == "orientacao_medica":
            d.events.append({"stage": "input", "name": "orientacao_medica", "action": "recusar_e_oferecer_consulta"})
            s.consecutive_failures = 0
            s.awaiting = "menu"
            s.add_action("Pedido de orientação clínica recusado (guardrail)")
            d.reply = prefix + R.recusa_medica()
            return
        if res.label == "fora_de_escopo":
            d.events.append({"stage": "input", "name": "fora_de_escopo", "action": "recusar"})
            s.consecutive_failures = 0
            s.add_action("Pedido fora de escopo recusado (guardrail)")
            d.reply = prefix + R.recusa_fora_escopo() + (" " + self._pending_reprompt(s) if s.flow == "agendar" else "")
            return

        if s.flow == "agendar":
            self._flow_turn(s, d, raw, norm, res, faq_hit, today, prefix, empathic)
        else:
            self._idle_turn(s, d, raw, norm, res, faq_hit, today, prefix, empathic)
        if not d.fallback:
            s.consecutive_failures = 0

    # ================================================================== modo de espera (pós-handoff)
    def _waiting_mode(self, s: SessionState, d: Decision, raw: str, res: IntentResult) -> None:
        h = s.handoff
        if res.label == "emergencia":
            h["priority"] = "alta"
            if h.get("summary"):
                h["summary"]["prioridade"] = "alta"
            d.reply = R.handoff_espera_urgente(h["protocol"])
        else:
            d.reply = R.handoff_espera(h["protocol"])
        h["notes"].append(d.user_text)
        del h["notes"][:-20]
        s.add_action("Mensagem adicional anotada para o atendente")

    # ================================================================== handoff
    def _handoff(self, s: SessionState, d: Decision, reason: str, raw: str) -> None:
        proto = "HO-" + uuid.uuid4().hex[:5].upper()
        now = self.clock.now_iso()
        s.handoff.update(active=True, reason=reason, priority=priority_for(reason), protocol=proto, created_at=now, notes=[])
        s.add_action(f"Handoff acionado: {reason}")
        s.handoff["summary"] = build_summary(s, reason, proto, raw, d.sentiment, now)
        s.awaiting = s.resume_awaiting = None
        d.handoff_new = True
        d.reply = R.handoff_msg(reason, proto)
        d.events.append({"stage": "policy", "name": "handoff", "action": reason})

    # ================================================================== fallback
    def _fallback(self, s: SessionState, d: Decision, raw: str, ftype: str, slot_reply: str | None = None) -> None:
        s.consecutive_failures += 1
        d.fallback, d.fallback_type = True, ftype
        n = s.consecutive_failures
        if n >= 3:
            return self._handoff(s, d, "falha_repetida", raw)
        if n == 2:
            s.resume_awaiting = s.awaiting if s.flow == "agendar" else None
            s.awaiting = "aceite_humano"
            s.add_action("Fallback 2x seguidas: oferta de atendente humano")
            d.reply = R.oferta_humano()
            return
        s.add_action(f"Fallback ({ftype})")
        if slot_reply:
            d.reply = slot_reply
        else:
            d.reply = R.fora_da_base() if ftype == "fora_da_base" else R.fallback_opcoes()
            s.awaiting = "menu"

    # ================================================================== turno ocioso (sem fluxo ativo)
    def _idle_turn(self, s, d, raw, norm, res, faq_hit, today, prefix, empathic) -> None:
        label = res.label
        if label == "agendar" and "need_only" in res.cues and faq_hit and (
                is_info_question(norm) or faq_hit.id == "remarcar_cancelar"):
            label = "faq"  # "quero cancelar/remarcar minha consulta" NÃO abre um novo agendamento
        if label in ("saudacao", "agradecimento", "desconhecido") and faq_hit:
            label = "faq"
        if label == "agendar":
            return self._start_flow(s, d, raw, norm, today, prefix, empathic)
        if label == "faq" or (label == "desconhecido" and faq_hit):
            return self._answer_faq(s, d, faq_hit, prefix, empathic, raw)
        simple = {"saudacao": R.saudacao, "agradecimento": R.agradecimento, "identidade": R.identidade, "ajuda": R.ajuda}
        if label in simple:
            d.intent = label
            d.reply = prefix + simple[label]()
            return
        if label == "despedida":
            s.closed = True
            d.reply = prefix + R.despedida()
            return
        if label == "retomar":
            d.reply = prefix + self._retomar(s, norm)
            return
        # não entendi / fora da base
        d.intent = "desconhecido"
        domain_q = self.faq.topico_fora_da_base(raw) or (
            len(tokens(norm)) >= 3 and ("?" in raw or QUESTION_START.match(norm)))
        ftype = "fora_da_base" if domain_q else "nao_entendi"
        self._fallback(s, d, raw, ftype)
        if not s.handoff["active"]:
            d.reply = prefix + d.reply

    # ================================================================== FAQ
    def _answer_faq(self, s, d, hit: FaqMatch, prefix, empathic, raw, reprompt: str = "") -> None:
        d.intent, d.confidence = "faq", min(0.95, 0.5 + hit.score / 4)
        d.faq_id, d.goal = hit.id, "faq"
        s.add_action(f"FAQ respondida: {hit.topico}")
        body = self._voice(s, d, "RESPONDER_FAQ", hit.resposta, empathic, must_question=False)
        tail = ("\n\n" + reprompt) if reprompt else " Posso ajudar em mais alguma coisa?"
        d.reply = prefix + body + tail

    # ================================================================== início do fluxo de agendamento
    def _start_flow(self, s, d, raw, norm, today, prefix, empathic) -> None:
        d.intent = "agendar"
        d.flow_started = True
        s.flow, s.awaiting = "agendar", None
        keep = {k: s.slots.get(k) for k in ("nome_tutor", "email")} if s.booking else {}
        s.slots = new_slots()
        s.slots.update({k: v for k, v in keep.items() if v})
        s.offered_times, s.offered_date, s.periodo_pref, s.slot_attempts = [], None, None, {}
        s.add_action("Fluxo de agendamento iniciado")
        ex = self._extract(s, raw, norm, today)
        errors = self._apply(s, ex, today)
        self._advance(s, d, list(ex.changed), errors, prefix, empathic)

    # ================================================================== turno dentro do fluxo
    def _flow_turn(self, s, d, raw, norm, res, faq_hit, today, prefix, empathic) -> None:
        d.intent, d.confidence = "agendar", max(res.confidence, 0.7)
        if res.label == "abortar":
            s.flow, s.awaiting, s.offered_times, s.offered_date = "idle", None, [], None
            s.add_action("Agendamento cancelado pelo usuário")
            d.reply = prefix + R.abortado()
            return
        aw = s.awaiting
        ex = self._extract(s, raw, norm, today)
        has_data = bool(ex.changed or ex.errors or (ex.periodo and aw in ("data", "horario")))

        if aw == "confirmacao" and not has_data:
            if X.is_yes(norm):
                return self._finalize_booking(s, d, today, prefix)
            if X.is_no(norm):
                s.slots["data"] = s.slots["horario"] = None
                s.offered_times, s.offered_date, s.awaiting = [], None, "data"
                d.intent = "negar"
                d.reply = prefix + R.reagendar_apos_nao()
                return
        if aw == "email" and not has_data and X.is_no(norm):
            ex.changed["email"] = "nao_informado"
            has_data = True
        if aw == "horario" and not has_data and X.is_no(norm):
            s.slots["data"] = None
            s.offered_times, s.offered_date, s.awaiting = [], None, "data"
<<<<<<< HEAD
            d.reply = prefix + "Sem problema! Qual outra data você prefere? (ex.: sexta, 15/10 ou amanhã)"
=======
            d.reply = prefix + "Sem problema! Qual outra data você prefere? (ex.: sexta ou amanhã)"
>>>>>>> 124e2bd (Atualizações no frontend e backend)
            return

        if has_data:
            errors = self._apply(s, ex, today)
            return self._advance(s, d, list(ex.changed), errors, prefix, empathic)

        # sem dado novo: interrupções (FAQ, retomar, social) e depois reprompt
        label = res.label
        pending = self._pending_reprompt(s)
        if faq_hit and label in ("desconhecido", "agradecimento", "saudacao", "agendar"):
            return self._answer_faq(s, d, faq_hit, prefix, empathic, raw, reprompt=R.flow_repeat_hint(pending))
        if label == "retomar":
            d.intent = "retomar"
            d.reply = prefix + self._retomar(s, norm)
            return
        if label == "agendar":
            d.reply = prefix + R.agendamento_ja_em_andamento(pending)
            return
        simple = {"saudacao": R.saudacao, "agradecimento": R.agradecimento, "identidade": R.identidade, "ajuda": R.ajuda}
        if label in simple:
            d.intent = label
            d.reply = prefix + simple[label]() + "\n\n" + R.flow_repeat_hint(pending)
            return
        if label == "despedida":
            d.intent = "despedida"
            s.closed, s.flow, s.awaiting = True, "idle", None
            d.reply = prefix + R.despedida()
            return
<<<<<<< HEAD
=======
        # pergunta de domínio fora da base no meio do fluxo: admite que não sabe e mantém o agendamento (não é erro de slot)
        if self.faq.topico_fora_da_base(raw) or (
                len(tokens(norm)) >= 3 and ("?" in raw or QUESTION_START.match(norm)) and aw not in ("nome_tutor", "nome_pet")):
            return self._fallback(s, d, raw, "fora_da_base", slot_reply=prefix + R.fora_da_base_no_fluxo(pending))
>>>>>>> 124e2bd (Atualizações no frontend e backend)
        # não entendi o dado esperado
        desc, ex_txt = SLOT_DESC.get(aw or "data")
        s.slot_attempts[aw or "data"] = s.slot_attempts.get(aw or "data", 0) + 1
        self._fallback(s, d, raw, f"slot_{aw or 'data'}", slot_reply=prefix + R.fallback_slot(desc, ex_txt))

    # ================================================================== extração + validação por código
    def _extract(self, s: SessionState, raw: str, norm: str, today: date) -> Extraction:
        ex = Extraction()
        aw = s.awaiting
        r = X.extract_nome_tutor(raw, bare=(aw == "nome_tutor"))
        if r.value:
            ex.changed["nome_tutor"] = r.value
        elif r.error:
            ex.errors.append(("nome_tutor", r.error, r.raw, None))
        r = X.extract_nome_pet(raw, bare=(aw == "nome_pet"))
        if r.value:
            ex.changed["nome_pet"] = r.value
        elif r.error:
            ex.errors.append(("nome_pet", r.error, r.raw, None))
        esp = X.extract_especie(norm)
        if esp and esp != s.slots.get("especie"):
            ex.changed["especie"] = esp
        ex.periodo = X.parse_periodo(norm)
        if aw == "email" or "@" in raw:
            r = X.parse_email(raw, norm, awaiting=(aw == "email"))
            if r.value:
                ex.changed["email"] = r.value
            elif r.error:
                ex.errors.append(("email", r.error, r.raw, None))
        picking_option = aw == "horario" and bool(s.offered_times) and X.option_phrase(norm) is not None
        if "@" not in raw and aw not in ("confirmacao",):
            r = X.parse_date(norm, today, bare_number=(aw == "data")) if not picking_option else X.SlotResult()
            if r.value:
                ex.changed["data"], ex.raws["data"] = r.value, r.raw
            elif r.error:
                ex.errors.append(("data", r.error, r.raw, None))
            t = X.parse_time(norm, awaiting=(aw == "horario"), offered=s.offered_times)
            if t.value:
                ex.changed["horario"] = t.value
            elif t.error:
                ex.errors.append(("horario", t.error, t.raw, None))
        return ex

    def _apply(self, s: SessionState, ex: Extraction, today: date) -> list:
        errors = list(ex.errors)
        for slot, val in ex.changed.items():
            if slot == "data":
                code, detail = self.agenda.check_date(date.fromisoformat(val), today)
                if code:
                    errors.append(("data", code, ex.raws.get("data"), detail))
                    continue
                if s.slots.get("data") != val:
                    s.offered_times, s.offered_date = [], None  # horário (se houver) é reconciliado abaixo
            s.slots[slot] = val
            s.slot_attempts.pop(slot, None)
        if ex.periodo:
            s.periodo_pref = ex.periodo
        # reconcilia horário × agenda quando a data já é conhecida
        if s.slots.get("data") and s.slots.get("horario"):
            d = date.fromisoformat(s.slots["data"])
            if not self.agenda.is_available(d, s.slots["horario"]):
                bad, s.slots["horario"] = s.slots["horario"], None
                alts = (self.agenda.available_times(d, s.periodo_pref) or self.agenda.available_times(d))[:3]
                s.offered_date, s.offered_times = s.slots["data"], alts
                errors.append(("horario", "horario_indisponivel", bad, alts))
        return errors

    # ================================================================== próximo passo do fluxo
    def _pending_reprompt(self, s: SessionState) -> str:
        aw = s.awaiting
        if aw == "nome_tutor":
            return "qual é o seu nome?"
        if aw == "nome_pet":
            return "qual é o nome do seu pet?"
        if aw == "horario" and s.offered_times:
            txt = R.offer_times(s.offered_date, s.offered_times)
            return txt[0].lower() + txt[1:]
        if aw == "email":
            return "qual é o seu e-mail? (ou responda “pular”)"
        if aw == "confirmacao":
            return R.confirm(s.slots)
<<<<<<< HEAD
        return "para qual dia você gostaria da consulta? (ex.: sexta, 15/10 ou amanhã)"
=======
        return "para qual dia você gostaria da consulta? (ex.: sexta ou amanhã)"
>>>>>>> 124e2bd (Atualizações no frontend e backend)

    def _advance(self, s, d, newly: list, errors: list, prefix: str, empathic: bool) -> None:
        ack = f"Prazer, {s.slots['nome_tutor']}! " if "nome_tutor" in newly and s.slots.get("nome_tutor") else ""
        if errors:
            slot, code, raw, detail = errors[0]
            d.validation_error = code
            s.slot_attempts[slot] = s.slot_attempts.get(slot, 0) + 1
            s.awaiting = slot
            s.add_action(f"Validação falhou ({code})")
            if code == "horario_indisponivel":
                msg = R.horario_indisponivel(s.offered_date, raw, detail)
            else:
                msg = R.erro_validacao(code, raw=raw, detail=detail)
            if s.slot_attempts[slot] >= 3:  # mantém o erro específico e acrescenta a oferta de humano
                s.resume_awaiting, s.awaiting = slot, "aceite_humano"
                msg += " " + R.oferta_humano_slot()
            d.reply = prefix + ack + msg
            return

        missing = next((k for k in SLOT_ORDER if not s.slots.get(k)), None)
        s.awaiting = missing or "confirmacao"
        if "data" in newly and s.slots.get("data"):
            s.add_action(f"Data validada: {s.slots['data']}")

        if missing is None:
            d.reply = prefix + R.confirm(s.slots)  # crítico: texto 100% determinístico
            return
        if missing == "nome_tutor":
            action, base = "PEDIR_NOME", R.ask_nome()
        elif missing == "nome_pet":
            action, base = "PEDIR_NOME_DO_PET", R.ask_pet(s.slots["nome_tutor"] if "nome_tutor" in newly else None, s.slots.get("especie"))
        elif missing == "data":
            action, base = "PEDIR_DATA", R.ask_data(s.slots["nome_pet"] if "nome_pet" in newly else None)
        elif missing == "horario":
            dt = date.fromisoformat(s.slots["data"])
            times = (self.agenda.available_times(dt, s.periodo_pref) or self.agenda.available_times(dt))[:3]
            s.offered_date, s.offered_times = s.slots["data"], times
            s.add_action(f"Horários oferecidos: {', '.join(times)}")
            action, base = "OFERECER_HORARIOS", R.offer_times(s.slots["data"], times)
        else:
            action, base = "PEDIR_EMAIL", R.ask_email(s.slots["data"], s.slots["horario"])
        d.reply = prefix + self._voice(s, d, action, base, empathic, must_question=True)

    # ================================================================== confirmação (fluxo determinístico)
    def _finalize_booking(self, s: SessionState, d: Decision, today: date, prefix: str) -> None:
        dt = date.fromisoformat(s.slots["data"])
        hh = s.slots["horario"]
        proto = self.agenda.book(dt, hh, s.session_id, s.slots["nome_tutor"], s.slots["nome_pet"])
        if proto is None:  # alguém tomou o horário nesse meio-tempo
            alts = (self.agenda.available_times(dt, s.periodo_pref) or self.agenda.available_times(dt))[:3]
            s.slots["horario"], s.offered_date, s.offered_times, s.awaiting = None, s.slots["data"], alts, "horario"
            d.validation_error = "horario_indisponivel"
            d.reply = prefix + R.horario_indisponivel(s.slots["data"], hh, alts)
            return
        s.booking = {"protocolo": proto, "data": s.slots["data"], "horario": hh, "pet": s.slots["nome_pet"], "tutor": s.slots["nome_tutor"]}
        s.flow, s.awaiting, s.offered_times, s.offered_date = "idle", None, [], None
        s.add_action(f"Agendamento confirmado ({proto})")
        d.goal = "agendamento_concluido"
        d.intent = "confirmar"
        d.reply = prefix + R.booked(s.slots, proto)

    # ================================================================== memória: retomar o que foi dito
    def _retomar(self, s: SessionState, norm: str) -> str:
        if re.search(r"nome d[oa] (meu |minha )?(pet|cachorr|gat|bichinh|animal)", norm) and s.slots.get("nome_pet"):
            return R.retomar_pet(s.slots["nome_pet"])
        if re.search(r"(meu nome|nome do tutor)", norm) and s.slots.get("nome_tutor"):
            return R.retomar_nome(s.slots["nome_tutor"])
        if s.offered_times and s.offered_date and re.search(r"horario|sugeriu|ofereceu|aquele|opcoes|sugestao|propos|mencionou|falou|disse", norm):
            return R.retomar_horarios(s.offered_date, s.offered_times)
        text = R.lembrete_slots(s.slots)
        if s.offered_times and s.offered_date:
            text += " " + R.retomar_horarios(s.offered_date, s.offered_times)
        return text

    # ================================================================== voz do LLM (com rédea curta)
    def _voice(self, s: SessionState, d: Decision, action: str, base: str, empathic: bool, must_question: bool) -> str:
        if not self.cfg.llm_verbalize:
            d.source = "template"
            return base
        tone = "acolhedor, calmo e com frases curtas" if empathic else "simpático e objetivo"
        directive = (
            "## Diretiva deste turno\n"
            f"Ação: {action}. Tom: {tone}.\n"
            "Reescreva o TEXTO-BASE abaixo com naturalidade, como a Duda falaria, em no máximo 3 frases curtas.\n"
            "NÃO altere nenhum número, data, horário, valor, nome ou telefone. NÃO acrescente fatos novos. "
            "Se houver pergunta, mantenha apenas UMA.\n"
            f"<<BASE>>\n{base}\n<</BASE>>\nResponda somente com o texto final."
        )
        system = f"{self.system_prompt}\n\n{state_block(s, self.cfg.window_turns)}\n\n{directive}"
        messages = build_messages(system, s.history, self.cfg.window_turns, d.user_text)
        try:
            out = self.llm.chat(messages)
        except LLMUnavailableError as e:
            if self.cfg.llm_fail_mode == "error":
                raise
            d.events.append({"stage": "llm", "name": "llm_indisponivel", "action": "usar_texto_base", "detail": str(e)[:120]})
            d.source = "template_degraded"
            return base
        reply = clean_llm_output(out)
        chk = check_llm_output(reply, base, max_chars=self.cfg.reply_max_chars, must_question=must_question,
                               system_prompt=self.system_prompt)
        if not chk.ok:
            d.events.append({"stage": "output", "name": chk.rule, "action": "usar_texto_base"})
            d.source = "template_guardrail"
            return base
        d.source, d.llm_used = "llm", True
        return reply

    # ================================================================== saída
    def _finalize_reply(self, d: Decision) -> str:
        reply = d.reply.strip()
        chk = check_final_reply(reply, self.cfg.reply_max_chars)
        if not chk.ok:
            d.events.append({"stage": "output", "name": chk.rule, "action": "truncar_ou_substituir"})
            reply = R.saudacao() if chk.rule == "vazamento_persona_ou_prompt" else truncate_sentences(reply, self.cfg.reply_max_chars)
        return reply

    def _log(self, s: SessionState, d: Decision, latency: int, now: str, raw: str) -> None:
        known = [s.slots.get("nome_tutor"), s.slots.get("nome_pet"), s.slots.get("email")]
        self.logger.write({
            "type": "turn", "ts": now, "session_id": s.session_id, "turn": s.turn,
            "intent": d.intent, "intent_confidence": round(d.confidence, 2),
            "fallback": d.fallback, "fallback_type": d.fallback_type,
            "handoff_active": s.handoff["active"], "handoff_new": d.handoff_new, "handoff_reason": s.handoff["reason"],
            "sentiment_label": d.sentiment.label, "sentiment_score": d.sentiment.score, "polarity": d.sentiment.polarity,
            "latency_ms": latency, "source": d.source, "llm_used": d.llm_used,
            "guardrail_events": d.events, "flow": s.flow, "awaiting": s.awaiting,
            "faq_id": d.faq_id, "goal": d.goal, "flow_started": d.flow_started, "validation_error": d.validation_error,
            "slots_preenchidos": sum(1 for v in s.slots.values() if v),
            "message_masked": mask_for_log(raw, known),
        })
