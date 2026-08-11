import os
import re
from telegram import Update
from telegram.ext import ContextTypes
from downloader import download_media
from ratelimit import check_cooldown
from config import DOWNLOAD_DIR, MAX_SIZE_MB, COOLDOWN_SECONDS

URL_PATTERN = re.compile(r"https?://\S+")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send me a link (X/Twitter, YouTube, TikTok, Instagram...) and I'll download it for you."
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    wait_time = check_cooldown(user_id, COOLDOWN_SECONDS)
    if wait_time > 0:
        await update.message.reply_text(
            f"Slow down a bit — please wait {wait_time}s before your next download."
        )
        return

    text = update.message.text.strip()
    match = URL_PATTERN.search(text)
    if not match:
        await update.message.reply_text("That doesn't look like a valid link.")
        return

    url = match.group(0)
    status_msg = await update.message.reply_text("Downloading...")

    filepath = None
    try:
        filepath = download_media(url, DOWNLOAD_DIR)
        size_mb = os.path.getsize(filepath) / (1024 * 1024)

        if size_mb > MAX_SIZE_MB:
            await status_msg.edit_text(f"File too large ({size_mb:.1f}MB). Telegram limit is {MAX_SIZE_MB}MB.")
            return

        await status_msg.edit_text("Uploading...")
        with open(filepath, "rb") as f:
            ext = filepath.rsplit(".", 1)[-1].lower()
            if ext in ("mp4", "mov", "webm"):
                await update.message.reply_video(video=f, read_timeout=120, write_timeout=120)
            elif ext in ("jpg", "jpeg", "png", "webp"):
                await update.message.reply_photo(photo=f)
            else:
                await update.message.reply_document(document=f)

        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"Failed to download: {str(e)[:200]}")

    finally:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
