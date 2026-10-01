"""Per-user cooldown kept in memory (resets when the process restarts)."""
from __future__ import annotations

import time

# user_id -> monotonic timestamp of the last accepted request
_last_request: dict[int, float] = {}
_PRUNE_THRESHOLD = 1000


def check_cooldown(user_id: int, cooldown_seconds: float, now: float | None = None) -> float:
    """Return 0 if the user may proceed (and start their cooldown), otherwise
    the number of seconds they still have to wait."""
    now = time.monotonic() if now is None else now
    last = _last_request.get(user_id)

    if last is not None and now - last < cooldown_seconds:
        return round(cooldown_seconds - (now - last), 1)

    if len(_last_request) >= _PRUNE_THRESHOLD:  # keep memory bounded
        for uid in [u for u, t in _last_request.items() if now - t >= cooldown_seconds]:
            del _last_request[uid]

    _last_request[user_id] = now
    return 0
