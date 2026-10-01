"""Runtime configuration, read from environment variables (or a local .env file)."""
from __future__ import annotations

import os
import tempfile

try:  # optional: lets you keep BOT_TOKEN in a local .env file
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - python-dotenv is optional
    pass


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        raise SystemExit(f"Environment variable {name} must be an integer, got {raw!r}.")


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _id_set(name: str) -> frozenset[int]:
    ids: set[int] = set()
    for part in os.getenv(name, "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            raise SystemExit(f"{name} must be a comma-separated list of numeric Telegram user IDs.")
    return frozenset(ids)


# --- Required -------------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# --- Storage --------------------------------------------------------------
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR") or os.path.join(tempfile.gettempdir(), "downloads")

# --- Limits ---------------------------------------------------------------
MAX_SIZE_MB = _int("MAX_SIZE_MB", 50)                    # Telegram's cap for bot uploads
COOLDOWN_SECONDS = _int("COOLDOWN_SECONDS", 30)          # wait between downloads, per user
MAX_DURATION_SECONDS = _int("MAX_DURATION_SECONDS", 3600)
MAX_CONCURRENT_DOWNLOADS = max(1, _int("MAX_CONCURRENT_DOWNLOADS", 3))

# --- Behaviour ------------------------------------------------------------
AUDIO_BITRATE_KBPS = _int("AUDIO_BITRATE_KBPS", 192)
# yt-dlp's "generic" extractor will fetch arbitrary pages. Off by default so the
# bot only talks to sites that yt-dlp has a dedicated extractor for.
ALLOW_GENERIC_EXTRACTOR = _bool("ALLOW_GENERIC_EXTRACTOR", False)
# Leave empty for a public bot, or list Telegram user IDs to make it private.
ALLOWED_USER_IDS = _id_set("ALLOWED_USER_IDS")
PROGRESS_INTERVAL = 3.0                                  # seconds between status edits

# --- Hosting --------------------------------------------------------------
PORT = _int("PORT", 10000)                               # keepalive / health endpoint
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def require_token() -> str:
    """Return the bot token or exit with a helpful message."""
    if not BOT_TOKEN:
        raise SystemExit(
            "BOT_TOKEN is not set.\n"
            "Create a bot with @BotFather, then run:  export BOT_TOKEN='123456:ABC...'\n"
            "(or put BOT_TOKEN=... in a .env file next to main.py)."
        )
    return BOT_TOKEN
