# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Where the layer's files are, in the repository and in a packaged build.

In the repository the layer is ``layer/`` with Natron's startup scripts in ``layer/ext/plugin`` (the folder put on
NATRON_PLUGIN_PATH). In a build made by ``layer/tools/package_build.py`` the startup scripts, the alias nodes and the
gizmos sit in ``<release>/Plugins/PyPlugs/layer`` (Natron's bundled PyPlugs folder, read at every start) and the
rest in ``<release>/Resources/layer``: Natron adds every folder under a PyPlugs folder to Python's path, so the
layer's own modules stay out of it.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT_MARKER = "upstream.toml"
PACKAGE = Path(__file__).resolve().parent


def layer_root() -> Path:
    """The folder holding upstream.toml, compat/ and ext/ (``layer/`` in the repository)."""
    explicit = os.environ.get("NATRON_LAYER_ROOT", "").strip()
    if explicit and (Path(explicit) / ROOT_MARKER).is_file():
        return Path(explicit).resolve()
    # natron_layer is in <root>/ext/python/natron_layer
    return PACKAGE.parents[2]


def ext() -> Path:
    return layer_root() / "ext"


def preset(name: str) -> Path:
    return ext() / "presets" / name


def stylesheet(name: str = "nuke.qss") -> Path:
    return ext() / "qss" / name


def upstream_file() -> Path:
    return layer_root() / ROOT_MARKER


def read_upstream() -> dict:
    """upstream.toml as a dict (empty when it can't be read)."""
    try:
        import tomllib  # noqa: PLC0415  (Python 3.11+)
    except ImportError:  # pragma: no cover
        return {}
    try:
        with open(upstream_file(), "rb") as file:
            return tomllib.load(file)
    except OSError:
        return {}
