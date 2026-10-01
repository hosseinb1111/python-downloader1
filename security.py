"""URL safety checks, so the bot can't be used to probe internal networks (SSRF)."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

from errors import UnsafeURL


def check_url(url: str) -> None:
    """Raise UnsafeURL unless `url` is an http(s) link to a public address."""
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise UnsafeURL("That link doesn't look valid.") from exc

    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        raise UnsafeURL("Only http:// and https:// links are supported.")

    host = parts.hostname
    if not host:
        raise UnsafeURL("That link has no host name.")

    try:
        infos = socket.getaddrinfo(host, port or (443 if scheme == "https" else 80),
                                   type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeURL("I couldn't resolve that address.") from exc
    except UnicodeError as exc:
        raise UnsafeURL("That address looks invalid.") from exc

    for info in infos:
        ip = ipaddress.ip_address(str(info[4][0]).split("%")[0])
        if ip.version == 6 and ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        if not ip.is_global:
            raise UnsafeURL("That address points to a private or internal network.")
