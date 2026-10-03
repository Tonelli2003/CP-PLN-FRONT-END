"""Agenda SIMULADA (data/agenda.json + reservas em runtime/bookings.json). Fluxo 100% determinístico."""
from __future__ import annotations

import json
import threading
import uuid
from datetime import date, timedelta
from pathlib import Path

DAY_KEYS = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]


class Agenda:
    def __init__(self, agenda_path: Path, bookings_path: Path | None = None):
        cfg = json.loads(Path(agenda_path).read_text(encoding="utf-8"))
        self.horarios: dict[str, list[str]] = cfg["horarios_por_dia_semana"]
        self.recorrentes: dict[str, list[str]] = cfg.get("ocupados_recorrentes", {})
        self.ocupados_datas: dict[str, list[str]] = cfg.get("ocupados_datas", {})
        self.feriados: dict[str, str] = cfg.get("feriados", {})
        self.antecedencia: int = cfg.get("antecedencia_minima_dias", 1)
        self.horizonte: int = cfg.get("horizonte_max_dias", 60)
        self._bookings_path = bookings_path
        self._lock = threading.Lock()
        self._bookings: dict[str, dict[str, dict]] = {}
        if bookings_path and Path(bookings_path).exists():
            try:
                self._bookings = json.loads(Path(bookings_path).read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._bookings = {}

    # ---- regras de negócio
    def check_date(self, d: date, today: date) -> tuple[str | None, str | None]:
        """Devolve (código_de_erro, detalhe). None = data aceitável."""
        if d < today:
            return "data_passada", None
        if d == today:
            return "data_hoje", None
        if d > today + timedelta(days=self.horizonte):
            return "data_distante", (today + timedelta(days=self.horizonte)).isoformat()
        iso = d.isoformat()
        if iso in self.feriados:
            return "clinica_fechada", self.feriados[iso]
        if not self.horarios[DAY_KEYS[d.weekday()]]:
            return "clinica_fechada", "domingo"
        if not self.available_times(d):
            return "dia_lotado", None
        return None, None

    def _busy(self, d: date) -> set[str]:
        iso = d.isoformat()
        busy = set(self.recorrentes.get(DAY_KEYS[d.weekday()], []))
        busy |= set(self.ocupados_datas.get(iso, []))
        busy |= set(self._bookings.get(iso, {}).keys())
        return busy

    def available_times(self, d: date, periodo: str | None = None) -> list[str]:
        busy = self._busy(d)
        times = [t for t in self.horarios[DAY_KEYS[d.weekday()]] if t not in busy]
        if periodo == "manha":
            times = [t for t in times if t < "12:00"]
        elif periodo == "tarde":
            times = [t for t in times if "12:00" <= t < "18:00"]
        elif periodo == "noite":
            times = [t for t in times if t >= "18:00"]
        return times

    def is_available(self, d: date, hhmm: str) -> bool:
        return hhmm in self.available_times(d)

    def book(self, d: date, hhmm: str, session_id: str, tutor: str, pet: str) -> str | None:
        """Reserva atomicamente. Retorna o protocolo, ou None se o horário foi tomado."""
        with self._lock:
            if not self.is_available(d, hhmm):
                return None
            protocolo = "PC-" + uuid.uuid4().hex[:6].upper()
            self._bookings.setdefault(d.isoformat(), {})[hhmm] = {
                "protocolo": protocolo, "session_id": session_id, "tutor": tutor, "pet": pet,
            }
            if self._bookings_path:
                tmp = Path(str(self._bookings_path) + ".tmp")
                tmp.write_text(json.dumps(self._bookings, ensure_ascii=False, indent=2), encoding="utf-8")
                tmp.replace(self._bookings_path)
            return protocolo
