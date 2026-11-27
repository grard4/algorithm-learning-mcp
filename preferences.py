"""Read user-owned learning preferences without making them server requirements."""
from __future__ import annotations

import os
import stat
from pathlib import Path

DEFAULT_TEXT = (
    "No custom learning preferences are configured. Use clear explanations, "
    "state assumptions, distinguish taught/practiced/understood/mastered, and "
    "do not infer mastery without evidence."
)
MAX_BYTES = 64 * 1024


def preference_path() -> Path:
    configured = os.environ.get("ALGORITHM_PREFERENCES")
    return Path(configured).expanduser() if configured else Path(__file__).resolve().parent / "config" / "learning_preferences.md"


def read_preferences() -> dict:
    path = preference_path()
    try:
        # A bounded fresh read also detects replacement with preserved size/mtime.
        # Configuration is operator-owned; callers cannot supply arbitrary paths.
        if not path.is_file():
            if not path.exists():
                return {"status": "missing", "source": "default", "text": DEFAULT_TEXT}
            return {"status": "invalid", "source": "file", "error": "preference path must be a regular file"}
        with path.open('rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                return {"status": "invalid", "source": "file", "error": "preference path must be a regular file"}
            raw=stream.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:
            return {"status": "invalid", "source": "file", "error": f"file exceeds {MAX_BYTES} bytes"}
        text=raw.decode('utf-8').strip()
    except FileNotFoundError:
        return {"status": "missing", "source": "default", "text": DEFAULT_TEXT}
    except UnicodeError:
        return {"status": "invalid", "source": "file", "error": "file must be valid UTF-8"}
    except OSError:
        return {"status": "unavailable", "source": "file", "error": "preference file could not be read"}
    if not text:
        return {"status": "empty", "source": "default", "text": DEFAULT_TEXT}
    return {"status": "custom", "source": "file", "text": text}
