import unittest

import ratelimit


class CooldownTests(unittest.TestCase):
    def setUp(self):
        ratelimit._last_request.clear()

    def test_first_request_allowed_even_with_small_clock(self):
        self.assertEqual(ratelimit.check_cooldown(1, 30, now=0.5), 0)

    def test_blocks_then_allows(self):
        self.assertEqual(ratelimit.check_cooldown(1, 30, now=100), 0)
        self.assertEqual(ratelimit.check_cooldown(1, 30, now=110), 20.0)
        self.assertEqual(ratelimit.check_cooldown(1, 30, now=130), 0)

    def test_users_are_independent(self):
        ratelimit.check_cooldown(1, 30, now=100)
        self.assertEqual(ratelimit.check_cooldown(2, 30, now=101), 0)

    def test_old_entries_are_pruned(self):
        for uid in range(ratelimit._PRUNE_THRESHOLD):
            ratelimit._last_request[uid] = 0
        ratelimit.check_cooldown(99999, 30, now=1000)
        self.assertEqual(len(ratelimit._last_request), 1)


if __name__ == "__main__":
    unittest.main()
