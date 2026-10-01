import unittest

from errors import DownloadRejected, UnsafeURL
from security import check_url


class CheckUrlTests(unittest.TestCase):
    def assertBlocked(self, url):
        with self.assertRaises(UnsafeURL, msg=url):
            check_url(url)

    def test_blocks_internal_targets(self):
        for url in (
            "http://localhost/",
            "http://127.0.0.1:8080/x",
            "http://10.0.0.5/",
            "http://192.168.1.1/",
            "http://172.16.0.1/",
            "http://169.254.169.254/latest/meta-data/",
            "http://100.64.0.1/",
            "http://0.0.0.0/",
            "http://[::1]/",
            "http://[::ffff:127.0.0.1]/",
        ):
            self.assertBlocked(url)

    def test_blocks_non_http_schemes(self):
        for url in ("file:///etc/passwd", "ftp://example.com/a", "javascript:alert(1)"):
            self.assertBlocked(url)

    def test_blocks_garbage(self):
        self.assertBlocked("http://")
        self.assertBlocked("http://host:notaport/")

    def test_allows_public_ip(self):
        check_url("https://8.8.8.8/video.mp4")  # must not raise

    def test_is_a_user_facing_rejection(self):
        self.assertTrue(issubclass(UnsafeURL, DownloadRejected))


if __name__ == "__main__":
    unittest.main()
