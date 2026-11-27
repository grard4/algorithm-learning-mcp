"""Read user-owned learning preferences without making them server requirements."""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_TEXT = (
    "No custom learning preferences are configured. Use clear explanations, "
    "state assumptions, distinguish taught/practiced/understood/mastered, and "
    "do not infer mastery without evidence."
)
MAX_BYTES = 64 * 1024
_cache: dict[str, tuple[int, int, str]] = {}


def preference_path() -> Path:
    configured = os.environ.get("ALGORITHM_PREFERENCES")
    return Path(configured).expanduser() if configured else Path(__file__).resolve().parent / "config" / "learning_preferences.md"


def read_preferences() -> dict:
    path = preference_path()
    key = str(path.resolve())
    try:
        stat = path.stat()
    except FileNotFoundError:
        _cache.pop(key, None)
        return {"status": "missing", "source": "default", "text": DEFAULT_TEXT}
    if not path.is_file():
        return {"status": "invalid", "source": "file", "error": "preference path must be a regular file"}
    if stat.st_size > MAX_BYTES:
        return {"status": "invalid", "source": "file", "error": f"file exceeds {MAX_BYTES} bytes"}
    cached = _cache.get(key)
    if cached and cached[:2] == (stat.st_mtime_ns, stat.st_size):
        text = cached[2]
    else:
        try:
            text = path.read_text(encoding="utf-8").strip()
        except UnicodeError:
            return {"status": "invalid", "source": "file", "error": "file must be valid UTF-8"}
        except OSError as exc:
            return {"status": "unavailable", "source": "file", "error": str(exc)}
        _cache[key] = (stat.st_mtime_ns, stat.st_size, text)
    if not text:
        return {"status": "empty", "source": "default", "text": DEFAULT_TEXT}
    return {"status": "custom", "source": "file", "path": str(path), "text": text}
