"""Memória e estado NO SERVIDOR, indexados por session_id. O frontend guarda apenas o session_id."""
from __future__ import annotations

import copy
import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

SLOT_KEYS = ("nome_tutor", "nome_pet", "especie", "data", "horario", "email")


def new_slots() -> dict:
    return {k: None for k in SLOT_KEYS}


def new_handoff() -> dict:
    return {"active": False, "reason": None, "priority": None, "protocol": None, "created_at": None,
            "summary": None, "notes": []}


class SessionNotFoundError(Exception):
    pass


@dataclass
class SessionState:
    session_id: str
    created_at: str
    last_activity: str
    turn: int = 0  # turnos do usuário
    history: list = field(default_factory=list)  # [{role, content, ts}]
    slots: dict = field(default_factory=new_slots)
    flow: str = "idle"  # idle | agendar
    awaiting: str | None = None  # slot/etapa esperada na próxima mensagem
    resume_awaiting: str | None = None
    offered_date: str | None = None
    offered_times: list = field(default_factory=list)
    periodo_pref: str | None = None
    slot_attempts: dict = field(default_factory=dict)
    consecutive_failures: int = 0
    consecutive_negative: int = 0
    handoff: dict = field(default_factory=new_handoff)
    booking: dict | None = None
    actions: list = field(default_factory=list)  # ações já tomadas (alimenta o resumo do handoff)
    intents_seen: list = field(default_factory=list)
    closed: bool = False
    feedback: dict | None = None

    @property
    def status(self) -> str:
        if self.handoff.get("active"):
            return "transferida"
        if self.closed:
            return "encerrada"
        return "ativa"

    def add_action(self, text: str) -> None:
        if not self.actions or self.actions[-1] != text:
            self.actions.append(text)
            del self.actions[:-30]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SessionState":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


class SessionStore:
    def __init__(self, runtime_dir: Path | None, persist: bool = True, ttl_minutes: int = 240, max_sessions: int = 1000):
        self.persist = persist and runtime_dir is not None
        self.dir = Path(runtime_dir) / "sessions" if runtime_dir else None
        self.ttl = timedelta(minutes=ttl_minutes)
        self.max_sessions = max_sessions
        self._sessions: dict[str, SessionState] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()
        if self.persist:
            self.dir.mkdir(parents=True, exist_ok=True)
            for f in self.dir.glob("*.json"):
                try:
                    s = SessionState.from_dict(json.loads(f.read_text(encoding="utf-8")))
                    self._sessions[s.session_id] = s
                except (json.JSONDecodeError, TypeError):
                    continue

    def lock(self, session_id: str) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(session_id, threading.Lock())

    def create(self, now_iso: str) -> SessionState:
        self._purge(now_iso)
        s = SessionState(session_id=uuid.uuid4().hex[:12], created_at=now_iso, last_activity=now_iso)
        with self._guard:
            self._sessions[s.session_id] = s
        self.save(s)
        return s

    def get(self, session_id: str) -> SessionState:
        with self._guard:
            s = self._sessions.get(session_id)
        if s is None:
            raise SessionNotFoundError(session_id)
        return s

    def snapshot(self, session_id: str) -> SessionState:
        return copy.deepcopy(self.get(session_id))

    def save(self, s: SessionState) -> None:
        with self._guard:
            self._sessions[s.session_id] = s
        if self.persist:
            tmp = self.dir / f"{s.session_id}.json.tmp"
            tmp.write_text(json.dumps(s.to_dict(), ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.dir / f"{s.session_id}.json")

    def delete(self, session_id: str) -> bool:
        with self._guard:
            existed = self._sessions.pop(session_id, None) is not None
            self._locks.pop(session_id, None)
        if self.persist:
            (self.dir / f"{session_id}.json").unlink(missing_ok=True)
        return existed

    def all(self) -> list[SessionState]:
        with self._guard:
            return list(self._sessions.values())

    def _purge(self, now_iso: str) -> None:
        now = datetime.fromisoformat(now_iso)
        for s in list(self.all()):
            try:
                if now - datetime.fromisoformat(s.last_activity) > self.ttl and not s.handoff.get("active"):
                    self.delete(s.session_id)
            except ValueError:
                continue
        extra = len(self._sessions) - self.max_sessions + 1
        if extra > 0:
            for s in sorted(self.all(), key=lambda x: x.last_activity)[:extra]:
                self.delete(s.session_id)
