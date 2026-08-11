import time

# user_id -> timestamp of last download request
_last_request: dict[int, float] = {}

def check_cooldown(user_id: int, cooldown_seconds: int) -> float:
    """
    Returns 0 if the user is allowed to proceed.
    Otherwise returns the number of seconds they still need to wait.
    """
    now = time.time()
    last = _last_request.get(user_id, 0)
    elapsed = now - last

    if elapsed < cooldown_seconds:
        return round(cooldown_seconds - elapsed, 1)

    _last_request[user_id] = now
    return 0
