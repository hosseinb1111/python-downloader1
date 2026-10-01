import asyncio
import os
import shutil
import sys
import tempfile
import types
import unittest
from types import SimpleNamespace

# Use the real python-telegram-bot if installed, otherwise minimal stand-ins.
try:
    import telegram  # noqa: F401
    import telegram.ext  # noqa: F401
except ImportError:
    tg = types.ModuleType("telegram")
    tg.Update = object
    tg_error = types.ModuleType("telegram.error")

    class TelegramError(Exception):
        pass

    class BadRequest(TelegramError):
        pass

    tg_error.TelegramError, tg_error.BadRequest = TelegramError, BadRequest
    tg_ext = types.ModuleType("telegram.ext")
    tg_ext.ContextTypes = SimpleNamespace(DEFAULT_TYPE=object)
    sys.modules.update({"telegram": tg, "telegram.error": tg_error, "telegram.ext": tg_ext})
    tg.error, tg.ext = tg_error, tg_ext

import config  # noqa: E402
import handlers  # noqa: E402
import ratelimit  # noqa: E402
from downloader import DownloadResult  # noqa: E402
from errors import DownloadRejected  # noqa: E402
from telegram.error import BadRequest  # noqa: E402


class FakeStatus:
    def __init__(self, text):
        self.history = [text]
        self.deleted = False

    async def edit_text(self, text, **kw):
        self.history.append(text)

    async def delete(self):
        self.deleted = True


class FakeMessage:
    def __init__(self, text="", reply_to=None):
        self.text = text
        self.caption = None
        self.reply_to_message = reply_to
        self.replies, self.sent = [], []
        self.video_error = None

    async def reply_text(self, text, **kw):
        status = FakeStatus(text)
        self.replies.append(status)
        return status

    async def _send(self, kind, **kw):
        self.sent.append((kind, kw))

    async def reply_video(self, **kw):
        if self.video_error:
            raise self.video_error
        await self._send("video", **kw)

    async def reply_audio(self, **kw):
        await self._send("audio", **kw)

    async def reply_photo(self, **kw):
        await self._send("photo", **kw)

    async def reply_document(self, **kw):
        await self._send("document", **kw)


def make_update(message, user_id=1, chat_type="private"):
    return SimpleNamespace(
        effective_message=message,
        effective_user=SimpleNamespace(id=user_id, first_name="Ann <3"),
        effective_chat=SimpleNamespace(type=chat_type),
    )


class HandlerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        ratelimit._last_request.clear()
        handlers._slots = None
        self.tmp = tempfile.mkdtemp()
        self.workdirs = []
        self._saved = (config.COOLDOWN_SECONDS, config.PROGRESS_INTERVAL,
                       config.ALLOWED_USER_IDS, config.DOWNLOAD_DIR, handlers.download_media)
        config.COOLDOWN_SECONDS, config.PROGRESS_INTERVAL = 30, 0.01
        config.DOWNLOAD_DIR = self.tmp
        handlers.download_media = self.fake_download

    def tearDown(self):
        (config.COOLDOWN_SECONDS, config.PROGRESS_INTERVAL, config.ALLOWED_USER_IDS,
         config.DOWNLOAD_DIR, handlers.download_media) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def fake_download(self, url, out_dir, *, audio=False, progress=None, **kw):
        progress.update({"status": "downloading", "downloaded_bytes": 40, "total_bytes": 100})
        import time
        time.sleep(0.05)
        workdir = tempfile.mkdtemp(dir=out_dir)
        self.workdirs.append(workdir)
        name = "song.mp3" if audio else "clip.mp4"
        path = os.path.join(workdir, name)
        with open(path, "wb") as fh:
            fh.write(b"data")
        return DownloadResult(path=path, workdir=workdir, title="T <&>", uploader="U",
                              duration=65, width=640, height=360, url=url, audio=audio,
                              size_bytes=4)

    async def test_link_sends_video_and_cleans_up(self):
        msg = FakeMessage("check this https://8.8.8.8/v.")
        await handlers.handle_link(make_update(msg), None)

        kind, kw = msg.sent[0]
        self.assertEqual(kind, "video")
        self.assertEqual(kw["parse_mode"], "HTML")
        self.assertIn("T &lt;&amp;&gt;", kw["caption"])
        self.assertTrue(kw["supports_streaming"])
        status = msg.replies[0]
        self.assertTrue(status.deleted)
        self.assertTrue(any("Downloading" in h for h in status.history))
        self.assertIn("📤 Uploading…", status.history)
        self.assertFalse(os.path.exists(self.workdirs[0]))

    async def test_audio_command_with_args(self):
        msg = FakeMessage("/audio https://8.8.8.8/s")
        await handlers.audio_command(make_update(msg), SimpleNamespace(args=["https://8.8.8.8/s"]))
        self.assertEqual(msg.sent[0][0], "audio")

    async def test_audio_command_uses_replied_message(self):
        original = FakeMessage("listen: https://8.8.8.8/s")
        msg = FakeMessage("/audio", reply_to=original)
        await handlers.audio_command(make_update(msg), SimpleNamespace(args=[]))
        self.assertEqual(msg.sent[0][0], "audio")

    async def test_audio_command_without_link_shows_usage(self):
        msg = FakeMessage("/audio")
        await handlers.audio_command(make_update(msg), SimpleNamespace(args=[]))
        self.assertIn("Usage", msg.replies[0].history[0])
        self.assertEqual(msg.sent, [])

    async def test_no_link_hint_in_private_but_silent_in_groups(self):
        private = FakeMessage("hello")
        await handlers.handle_link(make_update(private), None)
        self.assertEqual(len(private.replies), 1)

        group = FakeMessage("hello")
        await handlers.handle_link(make_update(group, chat_type="supergroup"), None)
        self.assertEqual(group.replies, [])

    async def test_non_link_does_not_burn_cooldown(self):
        await handlers.handle_link(make_update(FakeMessage("hello")), None)
        msg = FakeMessage("https://8.8.8.8/v")
        await handlers.handle_link(make_update(msg), None)
        self.assertEqual(msg.sent[0][0], "video")

    async def test_cooldown_blocks_second_request(self):
        await handlers.handle_link(make_update(FakeMessage("https://8.8.8.8/a")), None)
        msg = FakeMessage("https://8.8.8.8/b")
        await handlers.handle_link(make_update(msg), None)
        self.assertIn("Slow down", msg.replies[0].history[0])
        self.assertEqual(msg.sent, [])

    async def test_rejection_message_is_shown(self):
        def boom(*a, **k):
            raise DownloadRejected("That's too long (2:00:00).")

        handlers.download_media = boom
        msg = FakeMessage("https://8.8.8.8/a")
        await handlers.handle_link(make_update(msg), None)
        self.assertEqual(msg.replies[0].history[-1], "⚠️ That's too long (2:00:00).")

    async def test_unexpected_error_is_friendly(self):
        def boom(*a, **k):
            raise RuntimeError("ERROR: Unsupported URL: /secret/path")

        handlers.download_media = boom
        msg = FakeMessage("https://8.8.8.8/a")
        await handlers.handle_link(make_update(msg), None)
        final = msg.replies[0].history[-1]
        self.assertTrue(final.startswith("❌"))
        self.assertNotIn("secret", final)

    async def test_video_falls_back_to_document(self):
        msg = FakeMessage("https://8.8.8.8/a")
        msg.video_error = BadRequest("Wrong file type")
        await handlers.handle_link(make_update(msg), None)
        self.assertEqual(msg.sent[0][0], "document")

    async def test_private_bot_blocks_strangers(self):
        config.ALLOWED_USER_IDS = frozenset({42})
        msg = FakeMessage("https://8.8.8.8/a")
        await handlers.handle_link(make_update(msg, user_id=1), None)
        self.assertIn("private", msg.replies[0].history[0])
        self.assertEqual(msg.sent, [])

        msg = FakeMessage("https://8.8.8.8/a")
        await handlers.handle_link(make_update(msg, user_id=42), None)
        self.assertEqual(msg.sent[0][0], "video")

    async def test_start_escapes_name(self):
        msg = FakeMessage("/start")
        await handlers.start(make_update(msg), None)
        text = msg.replies[0].history[0]
        self.assertIn("Ann &lt;3", text)
        self.assertIn("/audio", text)


if __name__ == "__main__":
    unittest.main()
