"""Media download logic built on yt-dlp.

`download_media` is synchronous and meant to be run in a worker thread
(`asyncio.to_thread`) so it never blocks the Telegram event loop.
"""
from __future__ import annotations

import functools
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass

import config
from errors import DownloadRejected
from security import check_url
from utils import format_duration, format_size

log = logging.getLogger(__name__)

# If a video doesn't fit in Telegram's size limit, retry at a lower resolution.
QUALITY_LADDER = (720, 480, 360)
_IGNORED_SUFFIXES = (".part", ".ytdl", ".temp", ".tmp", ".json", ".description", ".vtt", ".srt")


# --------------------------------------------------------------------------
# Data classes
# --------------------------------------------------------------------------
@dataclass
class Progress:
    """Live download state, updated from yt-dlp's thread and read by the bot."""

    status: str = "starting"  # starting | downloading | processing
    downloaded: int = 0
    total: int | None = None
    speed: float | None = None
    eta: int | None = None

    def update(self, data: dict) -> None:
        state = data.get("status")
        if state == "downloading":
            self.status = "downloading"
            self.downloaded = data.get("downloaded_bytes") or 0
            self.total = data.get("total_bytes") or data.get("total_bytes_estimate")
            self.speed = data.get("speed")
            self.eta = data.get("eta")
        elif state == "finished":
            self.status = "processing"

    def render(self) -> str:
        if self.status == "processing":
            return "⚙️ Processing…"
        if self.status != "downloading":
            return "🔎 Fetching info…"

        text = "⬇️ Downloading…"
        if self.total:
            pct = max(0, min(100, int(self.downloaded * 100 / self.total)))
            filled = pct // 10
            text += f" {pct}%\n{'▰' * filled}{'▱' * (10 - filled)}"
        details = []
        if self.speed:
            details.append(f"{format_size(self.speed)}/s")
        if self.eta is not None:
            details.append(f"ETA {format_duration(self.eta) or '0:00'}")
        if details:
            text += "\n" + " · ".join(details)
        return text


@dataclass
class DownloadResult:
    path: str
    workdir: str
    title: str
    uploader: str | None
    duration: int | None
    width: int | None
    height: int | None
    url: str
    audio: bool
    size_bytes: int

    def cleanup(self) -> None:
        """Delete the temporary directory holding the downloaded file."""
        shutil.rmtree(self.workdir, ignore_errors=True)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
@functools.lru_cache(maxsize=1)
def _ffmpeg_path() -> str | None:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # fall back to an ffmpeg on PATH, if any
        log.warning("Bundled ffmpeg unavailable (%s); relying on system ffmpeg.", exc)
        return None


def _video_format(height: int, max_bytes: int) -> str:
    size = f"[filesize<?{max_bytes}][filesize_approx<?{max_bytes}]"
    cap = f"[height<=?{height}]"
    return f"bv*{cap}{size}+ba{size}/b{cap}{size}/b{cap}/b"


def _as_int(value) -> int | None:
    try:
        return int(float(value)) if value else None
    except (TypeError, ValueError):
        return None


def _first_entry(info: dict) -> dict:
    """If yt-dlp returned a playlist, use its first real entry."""
    entries = info.get("entries")
    if entries:
        for entry in entries:
            if entry:
                return entry
    return info


def _empty_dir(path: str) -> None:
    for name in os.listdir(path):
        full = os.path.join(path, name)
        if os.path.isdir(full):
            shutil.rmtree(full, ignore_errors=True)
        else:
            try:
                os.remove(full)
            except OSError:
                pass


def _find_output(workdir: str) -> str | None:
    """Return the downloaded file (largest non-temporary file), if any."""
    candidates = [
        os.path.join(workdir, name)
        for name in os.listdir(workdir)
        if not name.lower().endswith(_IGNORED_SUFFIXES)
        and os.path.isfile(os.path.join(workdir, name))
    ]
    return max(candidates, key=os.path.getsize) if candidates else None


def _looks_too_large(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "max-filesize" in text or "file is larger" in text


def cleanup_stale(out_dir: str | None = None) -> None:
    """Remove job folders left behind by a previous crash."""
    out_dir = out_dir or config.DOWNLOAD_DIR
    if not os.path.isdir(out_dir):
        return
    for name in os.listdir(out_dir):
        if name.startswith("job_"):
            shutil.rmtree(os.path.join(out_dir, name), ignore_errors=True)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def download_media(
    url: str,
    out_dir: str | None = None,
    *,
    audio: bool = False,
    progress: Progress | None = None,
    max_size_mb: float | None = None,
    max_duration: int | None = None,
    allow_generic: bool | None = None,
    audio_bitrate: int | None = None,
) -> DownloadResult:
    """Download `url` (video, or MP3 when `audio=True`) into a private temp folder.

    Raises DownloadRejected for expected refusals (too long, too big, unsafe URL)
    and lets yt-dlp errors propagate for the caller to translate.
    The caller must call `result.cleanup()` when finished with the file.
    """
    out_dir = out_dir or config.DOWNLOAD_DIR
    max_size_mb = config.MAX_SIZE_MB if max_size_mb is None else max_size_mb
    max_duration = config.MAX_DURATION_SECONDS if max_duration is None else max_duration
    allow_generic = config.ALLOW_GENERIC_EXTRACTOR if allow_generic is None else allow_generic
    audio_bitrate = config.AUDIO_BITRATE_KBPS if audio_bitrate is None else audio_bitrate
    progress = progress if progress is not None else Progress()

    check_url(url)

    import yt_dlp  # imported lazily so the rest of the app is importable without it

    os.makedirs(out_dir, exist_ok=True)
    workdir = tempfile.mkdtemp(prefix="job_", dir=out_dir)
    max_bytes = int(max_size_mb * 1024 * 1024)
    rejection: list[str] = []
    too_large = (f"That file is bigger than {max_size_mb:g} MB, which is the limit for "
                 f"Telegram bots. Try a shorter clip.")

    def match_filter(info, *args, **kwargs):
        """yt-dlp calls this before downloading; returning text skips the video."""
        if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
            message = "Live streams aren't supported."
        elif (info.get("duration") or 0) > max_duration:
            message = (f"That's too long ({format_duration(info['duration'])}). "
                       f"I only handle media up to {format_duration(max_duration)}.")
        else:
            return None
        rejection.append(message)
        return message

    def build_opts(height: int | None) -> dict:
        opts = {
            "outtmpl": os.path.join(workdir, "%(id)s.%(ext)s"),
            "restrictfilenames": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": True,
            "playlist_items": "1",
            "max_filesize": max_bytes,
            "match_filter": match_filter,
            "progress_hooks": [progress.update],
            "socket_timeout": 20,
            "retries": 3,
            "fragment_retries": 3,
            "concurrent_fragment_downloads": 4,
        }
        ffmpeg = _ffmpeg_path()
        if ffmpeg:
            opts["ffmpeg_location"] = ffmpeg
        if not allow_generic:
            opts["allowed_extractors"] = ["default", "-generic"]

        if audio:
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3",
                 "preferredquality": str(audio_bitrate)},
                {"key": "FFmpegMetadata"},
            ]
        else:
            opts["format"] = _video_format(height, max_bytes)
            # Prefer H.264/AAC so the result plays inline in every Telegram client.
            opts["format_sort"] = ["res", "vcodec:h264", "acodec:aac"]
            opts["merge_output_format"] = "mp4"
        return opts

    rungs = (None,) if audio else QUALITY_LADDER
    try:
        for index, height in enumerate(rungs):
            last_rung = index == len(rungs) - 1
            _empty_dir(workdir)
            rejection.clear()
            progress.status = "starting"

            try:
                with yt_dlp.YoutubeDL(build_opts(height)) as ydl:
                    info = ydl.extract_info(url, download=True)
            except Exception as exc:
                if rejection:
                    raise DownloadRejected(rejection[0]) from exc
                if _looks_too_large(exc):
                    if last_rung:
                        raise DownloadRejected(too_large) from exc
                    log.info("Too large at %sp, retrying lower.", height)
                    continue
                raise

            path = _find_output(workdir)
            if path is None:
                if rejection:
                    raise DownloadRejected(rejection[0])
                if last_rung:
                    raise DownloadRejected(
                        "I couldn't download anything from that link "
                        "(it may be too large, private or unsupported).")
                continue

            size = os.path.getsize(path)
            if size > max_bytes:
                if last_rung:
                    raise DownloadRejected(too_large)
                log.info("Result is %s at %sp, retrying lower.", format_size(size), height)
                continue

            meta = _first_entry(info) if info else {}
            return DownloadResult(
                path=path,
                workdir=workdir,
                title=meta.get("title") or os.path.splitext(os.path.basename(path))[0],
                uploader=meta.get("uploader") or meta.get("channel"),
                duration=_as_int(meta.get("duration")),
                width=_as_int(meta.get("width")),
                height=_as_int(meta.get("height")),
                url=meta.get("webpage_url") or url,
                audio=audio,
                size_bytes=size,
            )
        raise DownloadRejected(too_large)  # pragma: no cover - loop always returns/raises
    except BaseException:
        shutil.rmtree(workdir, ignore_errors=True)
        raise
