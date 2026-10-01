"""Small, dependency-free helpers: URL extraction, formatting, error messages."""
from __future__ import annotations

import html
import re

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_TRAILING = ".,;:!?'\""
_PAIRS = {")": "(", "]": "[", "}": "{"}


def extract_url(text: str | None) -> str | None:
    """Return the first http(s) URL in `text`, without trailing punctuation."""
    if not text:
        return None
    match = _URL_RE.search(text)
    if not match:
        return None

    url = match.group(0)
    while url:
        stripped = url.rstrip(_TRAILING)
        if stripped and stripped[-1] in _PAIRS:
            closer, opener = stripped[-1], _PAIRS[stripped[-1]]
            if stripped.count(closer) > stripped.count(opener):  # unbalanced -> not part of URL
                stripped = stripped[:-1]
        if stripped == url:
            break
        url = stripped
    return url or None


def format_duration(seconds: float | int | None) -> str:
    """65 -> '1:05', 3725 -> '1:02:05', None/0 -> ''."""
    if not seconds:
        return ""
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def format_size(num_bytes: float | int | None) -> str:
    """1536 -> '1.5 KB'."""
    if not num_bytes:
        return "0 B"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} B" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"  # pragma: no cover


def truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def build_caption(title: str, uploader: str | None, duration: int | None,
                  url: str | None, audio: bool = False, limit: int = 1024) -> str:
    """HTML caption for the uploaded file (Telegram caps captions at 1024 chars)."""
    icon = "🎵" if audio else "🎬"
    lines = [f"{icon} <b>{html.escape(truncate(title or 'Untitled', 200))}</b>"]

    meta = []
    if uploader:
        meta.append(f"👤 {html.escape(truncate(uploader, 80))}")
    if duration:
        meta.append(f"⏱ {format_duration(duration)}")
    if meta:
        lines.append(" · ".join(meta))

    caption = "\n".join(lines)
    if url:
        with_link = caption + f'\n🔗 <a href="{html.escape(url, quote=True)}">Source</a>'
        if len(with_link) <= limit:
            caption = with_link
    return caption


# (substrings to look for in the lower-cased error, message for the user) - first match wins
_ERROR_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("unsupported url",),
     "I don't know how to download from that link."),
    (("sign in", "log in", "login", "cookies", "members-only", "private video",
      "age-restricted", "confirm your age", "not a bot"),
     "That content is private, age-restricted or needs a login, so I can't access it."),
    (("not available in your country", "in your country", "geo-restricted", "geo restricted"),
     "That content isn't available from my server's region."),
    (("max-filesize", "file is larger", "too large"),
     "That file is too big to send through Telegram."),
    (("http error 429", "too many requests", "rate limit", "rate-limit"),
     "The site is rate-limiting me right now. Please try again in a few minutes."),
    (("video unavailable", "has been removed", "no longer available", "does not exist",
      "http error 404", "deleted"),
     "That content is unavailable or has been removed."),
    (("no video formats", "no video could be found", "there is no video"),
     "I couldn't find any downloadable media in that link."),
    (("timed out", "timeout", "connection", "unable to download webpage"),
     "I couldn't reach that site. Please try again in a moment."),
)


def friendly_error(exc: BaseException) -> str:
    """Turn an exception from yt-dlp into something a person can act on."""
    text = str(exc).lower()
    for needles, message in _ERROR_HINTS:
        if any(needle in text for needle in needles):
            return message
    return "Something went wrong while downloading. Please check the link and try again."
