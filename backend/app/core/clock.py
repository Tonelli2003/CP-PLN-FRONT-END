from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo

    _TZ = ZoneInfo("America/Sao_Paulo")
except Exception:  # tzdata ausente
    _TZ = timezone(timedelta(hours=-3))


class Clock:
    def __init__(self, fixed_today: date | None = None):
        self.fixed_today = fixed_today

    def today(self) -> date:
        return self.fixed_today or datetime.now(_TZ).date()

    def now_iso(self) -> str:
        return datetime.now(_TZ).isoformat(timespec="seconds")
