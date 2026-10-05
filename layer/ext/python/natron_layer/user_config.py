# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The layer's own small file of the artist's answers: whether the Nuke preferences pop-up was answered, and what
was imported from their Nuke preferences.

It's a JSON file in the artist's settings folder (``%APPDATA%\\natron-layer\\config.json`` on Windows,
``$XDG_CONFIG_HOME/natron-layer/config.json`` or ``~/.config/natron-layer/config.json`` elsewhere;
``NATRON_LAYER_CONFIG_DIR`` points elsewhere, as the tests do). It's written only when the artist answers the pop-up
or runs the import: never by itself. Natron's own preferences are never written here or anywhere by the layer.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

FILE_NAME = "config.json"
VERSION = 1


def folder() -> Path:
    explicit = os.environ.get("NATRON_LAYER_CONFIG_DIR", "").strip()
    if explicit:
        return Path(explicit)
    if os.name == "nt" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "natron-layer"
    base = os.environ.get("XDG_CONFIG_HOME", "").strip() or str(Path.home() / ".config")
    return Path(base) / "natron-layer"


def path() -> Path:
    return folder() / FILE_NAME


def load() -> dict[str, Any]:
    """The answers so far ({} when there are none, or when the file can't be read)."""
    try:
        data = json.loads(path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save(data: dict[str, Any]) -> Path:
    """Write the answers (whole file, replaced atomically)."""
    data = {**data, "version": VERSION}
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix="config.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, sort_keys=True)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)
    return target


def nuke_import() -> dict[str, Any]:
    """What was imported from the artist's Nuke preferences (empty when nothing was)."""
    found = load().get("nuke_import")
    return found if isinstance(found, dict) else {}


def pop_up_answer() -> str | None:
    """``imported``, ``never``, or None while the pop-up should still ask (no answer, or "Not now")."""
    answer = load().get("pop_up")
    return answer if answer in ("imported", "never") else None
