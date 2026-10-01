import unittest

from utils import (build_caption, extract_url, format_duration, format_size,
                   friendly_error, truncate)


class ExtractUrlTests(unittest.TestCase):
    def test_finds_url_in_text(self):
        self.assertEqual(extract_url("look https://youtu.be/abc123 cool"), "https://youtu.be/abc123")

    def test_strips_trailing_punctuation(self):
        self.assertEqual(extract_url("see https://x.com/a/status/1."), "https://x.com/a/status/1")
        self.assertEqual(extract_url("(https://x.com/a)"), "https://x.com/a")

    def test_keeps_balanced_parentheses(self):
        url = "https://en.wikipedia.org/wiki/Python_(language)"
        self.assertEqual(extract_url(url), url)

    def test_none_when_no_url(self):
        self.assertIsNone(extract_url("hello there"))
        self.assertIsNone(extract_url(None))
        self.assertIsNone(extract_url(""))


class FormatTests(unittest.TestCase):
    def test_duration(self):
        self.assertEqual(format_duration(65), "1:05")
        self.assertEqual(format_duration(3725), "1:02:05")
        self.assertEqual(format_duration(None), "")

    def test_size(self):
        self.assertEqual(format_size(512), "512 B")
        self.assertEqual(format_size(1536), "1.5 KB")
        self.assertEqual(format_size(5 * 1024 * 1024), "5.0 MB")

    def test_truncate(self):
        self.assertEqual(truncate("abc", 5), "abc")
        self.assertEqual(len(truncate("a" * 50, 10)), 10)


class CaptionTests(unittest.TestCase):
    def test_escapes_html(self):
        caption = build_caption("<b>Hi</b> & bye", "A&B", 65, "https://x.com/?a=1&b=2")
        self.assertIn("&lt;b&gt;Hi&lt;/b&gt; &amp; bye", caption)
        self.assertIn("1:05", caption)
        self.assertIn("a=1&amp;b=2", caption)

    def test_respects_limit(self):
        caption = build_caption("T" * 500, "U" * 500, 10, "https://x.com/" + "a" * 2000)
        self.assertLessEqual(len(caption), 1024)
        self.assertNotIn("Source", caption)  # link dropped when it would not fit

    def test_audio_icon(self):
        self.assertTrue(build_caption("Song", None, None, None, audio=True).startswith("🎵"))


class FriendlyErrorTests(unittest.TestCase):
    def test_known_errors(self):
        cases = {
            "ERROR: Unsupported URL: https://x": "don't know how",
            "ERROR: Sign in to confirm you're not a bot": "private",
            "ERROR: Video unavailable": "unavailable",
            "HTTP Error 429: Too Many Requests": "rate-limiting",
            "File is larger than max-filesize": "too big",
            "Read timed out": "reach that site",
        }
        for raw, expected in cases.items():
            self.assertIn(expected, friendly_error(Exception(raw)), raw)

    def test_unknown_error_hides_internals(self):
        message = friendly_error(Exception("Traceback /home/secret/path"))
        self.assertNotIn("secret", message)


if __name__ == "__main__":
    unittest.main()
