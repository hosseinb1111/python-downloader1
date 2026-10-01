import os
import shutil
import sys
import tempfile
import types
import unittest

import downloader
from downloader import DownloadRejected, Progress, download_media

PUBLIC_URL = "https://8.8.8.8/watch?v=abc"  # IP literal: passes the SSRF check offline


class FakeYDL:
    """Stand-in for yt_dlp.YoutubeDL; `behavior(opts, url)` plays the site."""

    behavior = None
    calls: list = []

    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=True):
        FakeYDL.calls.append(self.opts)
        return FakeYDL.behavior(self.opts, url)


def write_file(opts, name="abc.mp4", size=500):
    path = os.path.join(os.path.dirname(opts["outtmpl"]), name)
    with open(path, "wb") as fh:
        fh.write(b"x" * size)
    return path


class DownloaderTests(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.mkdtemp()
        fake = types.ModuleType("yt_dlp")
        fake.YoutubeDL = FakeYDL
        self._saved = sys.modules.get("yt_dlp")
        sys.modules["yt_dlp"] = fake
        FakeYDL.calls = []

    def tearDown(self):
        if self._saved is None:
            sys.modules.pop("yt_dlp", None)
        else:
            sys.modules["yt_dlp"] = self._saved
        shutil.rmtree(self.out, ignore_errors=True)

    def run_download(self, **kw):
        kw.setdefault("max_size_mb", 0.01)  # ~10 KB
        return download_media(PUBLIC_URL, self.out, **kw)

    def test_success_returns_metadata_and_cleans_up(self):
        def behavior(opts, url):
            opts["progress_hooks"][0]({"status": "downloading", "downloaded_bytes": 50,
                                       "total_bytes": 100, "speed": 2048, "eta": 3})
            write_file(opts)
            return {"title": "Clip", "uploader": "Me", "duration": 12.0, "width": 640,
                    "height": 360, "webpage_url": "https://site/clip"}

        FakeYDL.behavior = staticmethod(behavior)
        progress = Progress()
        result = self.run_download(progress=progress)
        self.assertTrue(os.path.isfile(result.path))
        self.assertEqual((result.title, result.uploader, result.duration, result.height),
                         ("Clip", "Me", 12, 360))
        self.assertEqual(result.url, "https://site/clip")
        self.assertIn("50%", progress.render())

        opts = FakeYDL.calls[0]
        self.assertIn("height<=?720", opts["format"])
        self.assertEqual(opts["allowed_extractors"], ["default", "-generic"])
        self.assertTrue(opts["noplaylist"])

        result.cleanup()
        self.assertFalse(os.path.exists(result.workdir))

    def test_audio_uses_mp3_postprocessor(self):
        def behavior(opts, url):
            write_file(opts, "abc.mp3")
            return {"title": "Song"}

        FakeYDL.behavior = staticmethod(behavior)
        result = self.run_download(audio=True)
        keys = [pp["key"] for pp in FakeYDL.calls[0]["postprocessors"]]
        self.assertEqual(keys[0], "FFmpegExtractAudio")
        self.assertTrue(result.audio)
        result.cleanup()

    def test_generic_extractor_can_be_enabled(self):
        FakeYDL.behavior = staticmethod(lambda o, u: (write_file(o), {"title": "t"})[1])
        self.run_download(allow_generic=True).cleanup()
        self.assertNotIn("allowed_extractors", FakeYDL.calls[0])

    def test_too_long_is_rejected_and_cleaned(self):
        def behavior(opts, url):
            opts["match_filter"]({"duration": 99999})  # yt-dlp skips the video
            return {"title": "Long"}

        FakeYDL.behavior = staticmethod(behavior)
        with self.assertRaises(DownloadRejected) as ctx:
            self.run_download(max_duration=60)
        self.assertIn("too long", str(ctx.exception))
        self.assertEqual(os.listdir(self.out), [])

    def test_live_stream_is_rejected(self):
        def behavior(opts, url):
            opts["match_filter"]({"is_live": True})
            return None

        FakeYDL.behavior = staticmethod(behavior)
        with self.assertRaises(DownloadRejected) as ctx:
            self.run_download()
        self.assertIn("Live", str(ctx.exception))

    def test_match_filter_accepts_normal_video(self):
        captured = {}

        def behavior(opts, url):
            captured["verdict"] = opts["match_filter"]({"duration": 30}, incomplete=False)
            write_file(opts)
            return {"title": "ok"}

        FakeYDL.behavior = staticmethod(behavior)
        self.run_download(max_duration=60).cleanup()
        self.assertIsNone(captured["verdict"])

    def test_oversize_retries_at_lower_quality(self):
        sizes = iter([5000, 5000, 100])  # 720p and 480p too big for 1 KB limit, 360p fits

        def behavior(opts, url):
            write_file(opts, size=next(sizes))
            return {"title": "Big"}

        FakeYDL.behavior = staticmethod(behavior)
        result = self.run_download(max_size_mb=0.001)  # ~1 KB
        self.assertEqual(len(FakeYDL.calls), 3)
        self.assertIn("height<=?360", FakeYDL.calls[2]["format"])
        self.assertEqual(result.size_bytes, 100)
        result.cleanup()

    def test_always_oversize_is_rejected(self):
        FakeYDL.behavior = staticmethod(lambda o, u: (write_file(o, size=5000), {"title": "x"})[1])
        with self.assertRaises(DownloadRejected) as ctx:
            self.run_download(max_size_mb=0.001)
        self.assertIn("bigger than", str(ctx.exception))
        self.assertEqual(os.listdir(self.out), [])

    def test_max_filesize_exception_triggers_retry(self):
        state = {"n": 0}

        def behavior(opts, url):
            state["n"] += 1
            if state["n"] == 1:
                raise Exception("ERROR: File is larger than max-filesize (9 bytes > 1 bytes)")
            write_file(opts, size=10)
            return {"title": "ok"}

        FakeYDL.behavior = staticmethod(behavior)
        self.run_download().cleanup()
        self.assertEqual(state["n"], 2)

    def test_site_errors_propagate_and_clean_up(self):
        def behavior(opts, url):
            raise Exception("ERROR: Unsupported URL")

        FakeYDL.behavior = staticmethod(behavior)
        with self.assertRaises(Exception) as ctx:
            self.run_download()
        self.assertIn("Unsupported", str(ctx.exception))
        self.assertEqual(os.listdir(self.out), [])

    def test_playlist_result_uses_first_entry(self):
        def behavior(opts, url):
            write_file(opts)
            return {"entries": [None, {"title": "First", "uploader": "U"}]}

        FakeYDL.behavior = staticmethod(behavior)
        result = self.run_download()
        self.assertEqual(result.title, "First")
        result.cleanup()

    def test_unsafe_url_never_reaches_yt_dlp(self):
        FakeYDL.behavior = staticmethod(lambda o, u: self.fail("should not run"))
        with self.assertRaises(DownloadRejected):
            download_media("http://127.0.0.1/secret", self.out)
        self.assertEqual(FakeYDL.calls, [])

    def test_partial_files_are_ignored(self):
        def behavior(opts, url):
            write_file(opts, "abc.mp4.part", size=9000)
            write_file(opts, "abc.mp4", size=100)
            return {"title": "ok"}

        FakeYDL.behavior = staticmethod(behavior)
        result = self.run_download()
        self.assertTrue(result.path.endswith("abc.mp4"))
        result.cleanup()

    def test_cleanup_stale_removes_only_job_dirs(self):
        os.makedirs(os.path.join(self.out, "job_old"))
        os.makedirs(os.path.join(self.out, "keep_me"))
        downloader.cleanup_stale(self.out)
        self.assertEqual(os.listdir(self.out), ["keep_me"])


class ProgressTests(unittest.TestCase):
    def test_states(self):
        p = Progress()
        self.assertIn("Fetching", p.render())
        p.update({"status": "downloading", "downloaded_bytes": 25, "total_bytes": 100,
                  "speed": 1048576, "eta": 75})
        text = p.render()
        self.assertIn("25%", text)
        self.assertIn("1.0 MB/s", text)
        self.assertIn("ETA 1:15", text)
        p.update({"status": "finished"})
        self.assertIn("Processing", p.render())

    def test_unknown_total_has_no_percent(self):
        p = Progress()
        p.update({"status": "downloading", "downloaded_bytes": 25})
        self.assertNotIn("%", p.render())


if __name__ == "__main__":
    unittest.main()
