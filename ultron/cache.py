"""Tiny in-memory TTL cache for network tool results.

Avoids redundant API calls when the same query repeats within the TTL window
(e.g. asking for weather/news/stocks twice in a short span).
"""
from __future__ import annotations
import time
import functools
import threading

_store: dict = {}
_lock = threading.Lock()


def ttl_cache(seconds: int = 120):
    """Decorator: cache a function's string result by its args for `seconds`."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # repr-based key so unhashable args (e.g. dicts) still work.
            key = f"{fn.__module__}.{fn.__qualname__}|{args!r}|{sorted(kwargs.items())!r}"
            now = time.time()
            with _lock:
                hit = _store.get(key)
                if hit and now - hit[0] < seconds:
                    return hit[1]
            result = fn(*args, **kwargs)
            with _lock:
                _store[key] = (now, result)
            return result
        return wrapper
    return deco


def clear() -> None:
    with _lock:
        _store.clear()
