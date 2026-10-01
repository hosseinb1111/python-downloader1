"""Telegram handlers: /start, /help, /audio and automatic link detection."""
from __future__ import annotations

import asyncio
import html
import logging
import math
import os

from telegram import Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

import config
from downloader import DownloadResult, Progress, download_media
from errors import DownloadRejected
from ratelimit import check_cooldown
from stats import stats
from utils import build_caption, extract_url, friendly_error

log = logging.getLogger(__name__)

VIDEO_EXTS = {"mp4", "mov", "webm", "m4v"}
PHOTO_EXTS = {"jpg", "jpeg", "png", "webp"}
PHOTO_MAX_BYTES = 10 * 1024 * 1024  # Telegram's limit for photos
UPLOAD_TIMEOUT = 180

_slots: asyncio.Semaphore | None = None


def _get_slots() -> asyncio.Semaphore:
    """Created lazily so it binds to the running event loop."""
    global _slots
    if _slots is None:
        _slots = asyncio.Semaphore(config.MAX_CONCURRENT_DOWNLOADS)
    return _slots


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def _is_private(update: Update) -> bool:
    chat = update.effective_chat
    return chat is not None and chat.type == "private"


async def _authorized(update: Update) -> bool:
    """Everyone is allowed unless ALLOWED_USER_IDS is set."""
    allowed = config.ALLOWED_USER_IDS
    user = update.effective_user
    if not allowed or (user is not None and user.id in allowed):
        return True
    if _is_private(update) and update.effective_message:
        await update.effective_message.reply_text("🔒 This bot is private.")
    return False


async def _safe_edit(message, text: str) -> None:
    try:
        await message.edit_text(text)
    except TelegramError as exc:  # e.g. "message is not modified"
        log.debug("Could not edit status message: %s", exc)


async def _safe_delete(message) -> None:
    try:
        await message.delete()
    except TelegramError as exc:
        log.debug("Could not delete status message: %s", exc)


def _help_text() -> str:
    minutes = max(1, round(config.MAX_DURATION_SECONDS / 60))
    return (
        "<b>How to use</b>\n"
        "• Send a link and I'll reply with the video\n"
        "• <code>/audio &lt;link&gt;</code> gives you an MP3 instead "
        "(or reply to a link with /audio)\n\n"
        "Works with YouTube, X/Twitter, TikTok, Instagram, Reddit, Facebook, "
        "Vimeo, SoundCloud and many more.\n\n"
        "<b>Limits</b>\n"
        f"• Files up to {config.MAX_SIZE_MB} MB "
        "(I lower the quality automatically to fit)\n"
        f"• Media up to {minutes} minutes\n"
        f"• One download every {config.COOLDOWN_SECONDS} seconds"
    )


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _authorized(update):
        return
    user = update.effective_user
    name = html.escape(user.first_name) if user and user.first_name else "there"
    await update.effective_message.reply_text(
        f"👋 <b>Hi {name}!</b>\n\n"
        "I download videos and music from links you send me.\n\n" + _help_text(),
        parse_mode="HTML",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _authorized(update):
        return
    await update.effective_message.reply_text(_help_text(), parse_mode="HTML")


async def audio_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None or not await _authorized(update):
        return

    url = extract_url(" ".join(context.args or []))
    if url is None and message.reply_to_message:
        replied = message.reply_to_message
        url = extract_url(replied.text or replied.caption)
    if url is None:
        await message.reply_text(
            "Usage: /audio <link>\nYou can also reply to a message that contains a link."
        )
        return
    await _process(update, url, audio=True)


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None or not message.text or not await _authorized(update):
        return

    url = extract_url(message.text)
    if url is None:
        if _is_private(update):  # stay quiet in group chats
            await message.reply_text("Send me a link (YouTube, X, TikTok, Instagram…) 🔗")
        return
    await _process(update, url, audio=False)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Unhandled error while processing an update", exc_info=context.error)


# --------------------------------------------------------------------------
# Download pipeline
# --------------------------------------------------------------------------
async def _watch_progress(status_msg, progress: Progress, task: asyncio.Task) -> None:
    """Keep the status message up to date until the download task finishes."""
    last = None
    while True:
        done, _ = await asyncio.wait({task}, timeout=config.PROGRESS_INTERVAL)
        if done:
            return
        text = progress.render()
        if text != last:
            await _safe_edit(status_msg, text)
            last = text


async def _send_result(message, result: DownloadResult) -> None:
    caption = build_caption(result.title, result.uploader, result.duration,
                            result.url, audio=result.audio)
    timeouts = {"read_timeout": UPLOAD_TIMEOUT, "write_timeout": UPLOAD_TIMEOUT,
                "connect_timeout": 30}
    extras = {"caption": caption, "parse_mode": "HTML", **timeouts}
    ext = os.path.splitext(result.path)[1].lstrip(".").lower()

    with open(result.path, "rb") as fh:
        if result.audio:
            await message.reply_audio(
                audio=fh, title=result.title, performer=result.uploader,
                duration=result.duration, **extras)
        elif ext in VIDEO_EXTS:
            try:
                await message.reply_video(
                    video=fh, duration=result.duration, width=result.width,
                    height=result.height, supports_streaming=True, **extras)
            except BadRequest as exc:  # Telegram rejected it as a video: send as a file
                log.warning("reply_video failed (%s); falling back to document", exc)
                fh.seek(0)
                await message.reply_document(document=fh, **extras)
        elif ext in PHOTO_EXTS and result.size_bytes <= PHOTO_MAX_BYTES:
            await message.reply_photo(photo=fh, **extras)
        else:
            await message.reply_document(document=fh, **extras)


async def _process(update: Update, url: str, *, audio: bool) -> None:
    message = update.effective_message
    user_id = update.effective_user.id

    wait = check_cooldown(user_id, config.COOLDOWN_SECONDS)
    if wait > 0:
        await message.reply_text(
            f"⏳ Slow down a bit — please wait {math.ceil(wait)}s before your next download."
        )
        return

    status = await message.reply_text("⏳ Queued…")
    result: DownloadResult | None = None
    try:
        async with _get_slots():
            progress = Progress()
            await _safe_edit(status, progress.render())
            task = asyncio.create_task(asyncio.to_thread(
                download_media, url, config.DOWNLOAD_DIR, audio=audio, progress=progress))
            await _watch_progress(status, progress, task)
            result = await task

        await _safe_edit(status, "📤 Uploading…")
        await _send_result(message, result)
        stats.record_success()
        await _safe_delete(status)

    except DownloadRejected as exc:
        stats.record_failure()
        await _safe_edit(status, f"⚠️ {exc}")
    except Exception as exc:
        stats.record_failure()
        log.warning("Download failed for %s: %s", url, exc, exc_info=True)
        await _safe_edit(status, f"❌ {friendly_error(exc)}")
    finally:
        if result is not None:
            result.cleanup()
