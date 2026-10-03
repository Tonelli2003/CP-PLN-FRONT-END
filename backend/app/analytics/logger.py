"""Log estruturado por turno em JSONL (append-only, thread-safe). Base do GET /metrics.

LGPD: o log NÃO guarda valores de slots; a mensagem é gravada mascarada (CPF, cartão, e-mail, telefone e
nomes já coletados viram [DADO]). No DELETE /sessions o texto é apagado e o session_id é anonimizado.
"""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path


class TurnLogger:
    def __init__(self, runtime_dir: Path | None):
        self.path = Path(runtime_dir) / "turns.jsonl" if runtime_dir else None
        self._lock = threading.Lock()
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: dict) -> None:
        if not self.path:
            return
        line = json.dumps(record, ensure_ascii=False)
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def read_all(self) -> list[dict]:
        if not self.path or not self.path.exists():
            return []
        out = []
        with self._lock, self.path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return out

    def anonymize_session(self, session_id: str) -> int:
        """Direito ao esquecimento: remove o texto e troca o session_id por um hash. Mantém só o agregado."""
        if not self.path or not self.path.exists():
            return 0
        anon = "anon-" + hashlib.sha256(session_id.encode()).hexdigest()[:10]
        changed = 0
        with self._lock:
            lines = self.path.read_text(encoding="utf-8").splitlines()
            new = []
            for line in lines:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    new.append(line)
                    continue
                if rec.get("session_id") == session_id:
                    rec["session_id"] = anon
                    rec.pop("message_masked", None)
                    rec.pop("comment", None)
                    changed += 1
                new.append(json.dumps(rec, ensure_ascii=False))
            tmp = Path(str(self.path) + ".tmp")
            tmp.write_text("\n".join(new) + ("\n" if new else ""), encoding="utf-8")
            tmp.replace(self.path)
        return changed
