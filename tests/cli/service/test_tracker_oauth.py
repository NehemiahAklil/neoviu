"""Loopback OAuth redirect parsing and serving for tracker logins."""

import socket
import threading
import urllib.error
import urllib.request

import pytest

from viu_media.cli.service.tracking.oauth import parse_callback, wait_for_callback


@pytest.mark.parametrize(
    "value, code, state, error",
    [
        ("http://localhost:8123/callback?code=abc&state=xyz", "abc", "xyz", None),
        ("/callback?code=abc", "abc", None, None),
        ("code=abc&state=xyz", "abc", "xyz", None),
        ("  just-a-code  ", "just-a-code", None, None),
        ("?error=access_denied&message=nope", None, None, "access_denied: nope"),
        ("?error=access_denied", None, None, "access_denied"),
        ("", None, None, "Nothing was pasted."),
    ],
)
def test_parse_callback(value, code, state, error):
    callback = parse_callback(value)
    assert (callback.code, callback.state, callback.error) == (code, state, error)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _get(url: str) -> int:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as e:
        return e.code


def test_wait_for_callback_ignores_stray_requests_and_returns_the_code():
    port = _free_port()
    result = {}
    thread = threading.Thread(
        target=lambda: result.update(callback=wait_for_callback(port, timeout=10))
    )
    thread.start()
    base = f"http://127.0.0.1:{port}"
    statuses = []
    for _ in range(50):
        try:
            statuses.append(_get(f"{base}/favicon.ico"))
            break
        except urllib.error.URLError:
            threading.Event().wait(0.05)
    statuses.append(_get(f"{base}/callback?code=abc&state=xyz"))
    thread.join(10)

    assert statuses == [404, 200]
    callback = result["callback"]
    assert (callback.code, callback.state) == ("abc", "xyz")


def test_wait_for_callback_can_be_cancelled():
    cancel = threading.Event()
    cancel.set()
    assert wait_for_callback(_free_port(), timeout=10, cancel=cancel) is None


def test_wait_for_callback_raises_when_the_port_is_taken():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        with pytest.raises(OSError):
            wait_for_callback(sock.getsockname()[1], timeout=1)
