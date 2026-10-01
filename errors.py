"""Exceptions whose messages are safe to show directly to Telegram users."""
from __future__ import annotations


class DownloadRejected(Exception):
    """The request was refused on purpose (too long, too big, unsafe...).

    The message is written for end users, so handlers can display it as-is.
    """


class UnsafeURL(DownloadRejected):
    """The URL is malformed or points somewhere we must not connect to."""
