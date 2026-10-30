# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The layer of this Natron fork: Natron made to look and behave like Nuke by default, with no change to Natron's
own code (see FORK.md and layer/README.md).

``start()`` runs in every Natron session (init.py), ``start_gui()`` in sessions with an interface (initGui.py).
Neither writes Natron's preferences.
"""

from __future__ import annotations

import os

__version__ = "0.3.0"

last_report = None  # the look's report from start(), for the smoke test and the curious


def start() -> object | None:
    """The Nuke look for this session (NATRON_LAYER_LOOK=off leaves Natron's own look)."""
    global last_report  # noqa: PLW0603
    if os.environ.get("NATRON_LAYER_LOOK", "").strip().lower() == "off":
        return None
    from . import look  # noqa: PLC0415

    from . import compat  # noqa: PLC0415

    try:
        last_report = look.apply()
    except Exception as exc:  # noqa: BLE001  (Natron must start whatever happens)
        compat.say(f"Natron layer: the Nuke look wasn't applied ({exc}).")
        return None
    compat.say(last_report.summary())
    return last_report


def start_gui() -> dict | None:
    """The skin (icons, font) before Natron builds its window, then the Nuke menu."""
    from . import gui, skin  # noqa: PLC0415

    if os.environ.get("NATRON_LAYER_LOOK", "").strip().lower() != "off":
        try:
            gui.compat.say(skin.install().summary())
        except Exception as exc:  # noqa: BLE001  (Natron must start whatever happens)
            gui.compat.say(f"Natron layer: the skin wasn't applied ({exc}).")
    try:
        return gui.install()
    except Exception as exc:  # noqa: BLE001
        gui.compat.say(f"Natron layer: its menu wasn't installed ({exc}).")
        return None
