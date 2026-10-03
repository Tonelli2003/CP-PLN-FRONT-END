"""Métricas conversacionais calculadas A PARTIR DO LOG (nunca de contadores em memória).

Definições (Aula 4):
  taxa_contencao   = conversas sem handoff ÷ total de conversas
  taxa_fallback    = turnos do usuário em fallback ÷ total de turnos do usuário
  taxa_handoff     = conversas com handoff ÷ total de conversas
  mensagens_por_conversa = turnos do usuário ÷ conversas
Extras: taxa_resolucao (contida E com objetivo cumprido — o antídoto do "erro clássico" de contenção alta
com cliente insatisfeito), conversão do fluxo de agendamento, latência, distribuições e CSAT.
"""
from __future__ import annotations

from collections import Counter, defaultdict


def _rate(num: int, den: int) -> float:
    return round(num / den, 4) if den else 0.0


def _p95(values: list[int]) -> int:
    if not values:
        return 0
    v = sorted(values)
    return v[min(len(v) - 1, int(round(0.95 * (len(v) - 1))))]


def compute_metrics(records: list[dict]) -> dict:
    turns = [r for r in records if r.get("type") == "turn"]
    feedbacks = [r for r in records if r.get("type") == "feedback"]

    by_session: dict[str, list[dict]] = defaultdict(list)
    for t in turns:
        by_session[t["session_id"]].append(t)

    total_conv = len(by_session)
    total_turns = len(turns)
    handoff_sessions = {sid for sid, ts in by_session.items() if any(t.get("handoff_active") for t in ts)}
    goal_sessions = {sid for sid, ts in by_session.items() if any(t.get("goal") for t in ts)}
    started = {sid for sid, ts in by_session.items() if any(t.get("flow_started") for t in ts)}
    booked = {sid for sid, ts in by_session.items() if any(t.get("goal") == "agendamento_concluido" for t in ts)}
    fallbacks = [t for t in turns if t.get("fallback")]

    contained = set(by_session) - handoff_sessions
    resolved = contained & goal_sessions

    guard = Counter()
    tom_acolhimento = 0
    for t in turns:
        for ev in t.get("guardrail_events", []):
            if ev.get("stage") in ("input", "output", "llm"):  # guardrails de verdade
                guard[f'{ev.get("stage")}:{ev.get("name")}'] += 1
            elif ev.get("name") == "sentimento_negativo":
                tom_acolhimento += 1

    ratings = {f["session_id"]: f["rating"] for f in feedbacks if "rating" in f}
    ratings_by_group = {"contidas": [], "transferidas": []}
    anon_prefix = "anon-"
    for sid, r in ratings.items():
        if sid in handoff_sessions:
            ratings_by_group["transferidas"].append(r)
        elif sid in by_session or sid.startswith(anon_prefix):
            ratings_by_group["contidas"].append(r)
    avg = lambda xs: round(sum(xs) / len(xs), 2) if xs else None  # noqa: E731
    all_ratings = list(ratings.values())

    ts_list = sorted(t["ts"] for t in turns) if turns else []
    latencies = [t["latency_ms"] for t in turns if isinstance(t.get("latency_ms"), int)]
    handoff_first = {}
    for sid in handoff_sessions:
        for t in by_session[sid]:
            if t.get("handoff_new"):
                handoff_first[sid] = t.get("handoff_reason")
                break

    return {
        "periodo": {"inicio": ts_list[0] if ts_list else None, "fim": ts_list[-1] if ts_list else None},
        "total_conversas": total_conv,
        "total_turnos_usuario": total_turns,
        "taxa_contencao": _rate(len(contained), total_conv),
        "taxa_fallback": _rate(len(fallbacks), total_turns),
        "taxa_handoff": _rate(len(handoff_sessions), total_conv),
        "mensagens_por_conversa": round(total_turns / total_conv, 2) if total_conv else 0.0,
        "taxa_resolucao": _rate(len(resolved), total_conv),
        "agendamentos_concluidos": len(booked),
        "taxa_conclusao_agendamento": _rate(len(booked), len(started)),
        "latencia_media_ms": int(sum(latencies) / len(latencies)) if latencies else 0,
        "latencia_p95_ms": _p95(latencies),
        "distribuicao_intencoes": dict(Counter(t.get("intent", "desconhecido") for t in turns).most_common()),
        "distribuicao_sentimento": dict(Counter(t.get("sentiment_label", "neutro") for t in turns)),
        "fallback_por_tipo": dict(Counter(t.get("fallback_type") for t in fallbacks).most_common()),
        "fallback_por_estado": dict(Counter(t.get("awaiting") or t.get("flow") or "idle" for t in fallbacks).most_common()),
        "handoff_por_motivo": dict(Counter(handoff_first.values()).most_common()),
        "erros_validacao": dict(Counter(t["validation_error"] for t in turns if t.get("validation_error")).most_common()),
        "eventos_guardrail": dict(guard.most_common()),
        "turnos_com_tom_de_acolhimento": tom_acolhimento,
        "fonte_da_resposta": dict(Counter(t.get("source", "template") for t in turns).most_common()),
        "faq_mais_consultadas": dict(Counter(t["faq_id"] for t in turns if t.get("faq_id")).most_common()),
        "total_feedbacks": len(all_ratings),
        "csat_medio": avg(all_ratings),
        "csat_medio_conversas_contidas": avg(ratings_by_group["contidas"]),
        "csat_medio_conversas_transferidas": avg(ratings_by_group["transferidas"]),
    }
