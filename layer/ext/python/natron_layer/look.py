# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The Nuke look: this build's default values for Natron's preferences.

The rule, at every start (``apply``):

1. A preference the artist stored in Natron's own settings is theirs: it's left as it is. Natron stores a preference
   only when it was changed in its Preferences window and saved (or by a script calling ``saveSettings``), so a
   stored key is a choice someone made.
2. Otherwise, a value imported from the artist's Nuke preferences (``user_config``, after their yes) is used.
3. Otherwise, the build's Nuke look (``ext/presets/nuke_look.toml``).

Values from 2 and 3 are set for the session only: Natron doesn't write a preference set from Python, and the layer
also turns Natron's hidden "Save settings on change" off while it sets them (``compat.unsaved``). So the artist's
Natron settings never change by themselves, and Natron's Preferences window saves only what the artist changes in it.

The look has two tables: ``[settings]``, what it looks like (the stylesheet, the colours), and ``[habits]``, how it
behaves (snap, Merge to A, panels). When the artist chose Natron's own look (``skin.natron_look_chosen``), only the
habits apply. In a session with a window, the stylesheet is the skin's session copy of nuke.qss
(``skin.session_stylesheet``: the layer's pictures' paths filled in, the skin's font size).

``reset`` is the menu's "Use this build's look again…": with the artist's yes, it removes their stored values of the
look's preferences from Natron's settings, so the look applies again (Natron's own "Restore Defaults" button gives
Natron's stock values instead, and stores them).
"""

from __future__ import annotations

import dataclasses
from typing import Any

from . import compat, paths, user_config

LAYER_PREFIX = "@layer/"


@dataclasses.dataclass
class Report:
    applied: list[str] = dataclasses.field(default_factory=list)  # set for the session from the look
    imported: list[str] = dataclasses.field(default_factory=list)  # set for the session from the Nuke import
    kept: list[str] = dataclasses.field(default_factory=list)  # the artist's own (stored), left alone
    missing: list[str] = dataclasses.field(default_factory=list)  # this Natron has no such preference
    failed: list[str] = dataclasses.field(default_factory=list)  # the value didn't fit

    def summary(self) -> str:
        parts = [f"{len(self.applied)} from the Nuke look"]
        if self.imported:
            parts.append(f"{len(self.imported)} from your Nuke preferences")
        if self.kept:
            parts.append(f"{len(self.kept)} of your own kept ({', '.join(self.kept)})")
        if self.missing:
            parts.append(f"{len(self.missing)} this Natron doesn't have ({', '.join(self.missing)})")
        if self.failed:
            parts.append(f"{len(self.failed)} that didn't fit ({', '.join(self.failed)})")
        return "Nuke look: " + "; ".join(parts) + "."


def load_look(visual: bool = True) -> dict[str, Any]:
    """The look's preferences, by Natron script name, with ``@layer/`` paths made absolute: its habits, and its
    visual preferences unless ``visual`` is False."""
    import tomllib  # noqa: PLC0415

    with open(paths.preset("nuke_look.toml"), "rb") as file:
        data = tomllib.load(file)
    values = dict(data.get("settings", {})) if visual else {}
    values.update(data.get("habits", {}))
    root = paths.layer_root()
    for name, value in values.items():
        if isinstance(value, str) and value.startswith(LAYER_PREFIX):
            values[name] = (root / value[len(LAYER_PREFIX) :]).as_posix()
    return values


def is_own(name: str, stored: compat.StoredSettings, param: Any = None) -> bool:
    """Whether the artist stored this preference in Natron's settings."""
    return any(stored.contains(key) for key in compat.stored_keys(name, param))


def wanted_values(imported: dict[str, Any] | None = None) -> dict[str, tuple[str, Any]]:
    """Each preference the layer would set, with where its value comes from: ``imported`` (the artist's Nuke
    preferences) over ``look``."""
    from . import skin  # noqa: PLC0415

    values = {name: ("look", value) for name, value in load_look(visual=not skin.natron_look_chosen()).items()}
    imported = user_config.nuke_import().get("settings", {}) if imported is None else imported
    for name, value in (imported or {}).items():
        values[name] = ("imported", value)
    return values


def apply(stored: compat.StoredSettings | None = None, imported: dict[str, Any] | None = None) -> Report:
    """Set the look (and the imported Nuke preferences) for this session, leaving the artist's own preferences."""
    stored = compat.StoredSettings.of_natron() if stored is None else stored
    report = Report()
    with compat.unsaved():
        for name, (source, value) in wanted_values(imported).items():
            param = compat.setting(name)
            if param is None:
                report.missing.append(name)
                continue
            if is_own(name, stored, param):
                report.kept.append(name)
                continue
            if name == "stylesheetFile" and source == "look" and _with_window():
                from . import skin  # noqa: PLC0415

                value = skin.session_stylesheet(str(value), stored)
            if not compat.set_param_value(param, value):
                report.failed.append(name)
                continue
            (report.imported if source == "imported" else report.applied).append(name)
    return report


def _with_window() -> bool:
    try:
        return not compat.is_background()
    except Exception:  # noqa: BLE001  (outside Natron: the tests)
        return False


def own_values_in_the_way(stored: compat.StoredSettings | None = None) -> list[str]:
    """The look's preferences the artist stored (and so keeps instead of the look's)."""
    stored = compat.StoredSettings.of_natron() if stored is None else stored
    return [name for name in load_look() if compat.setting(name) is not None and is_own(name, stored)]


def reset(writer: compat.SettingsWriter, names: list[str]) -> Report:
    """After the artist's yes: remove their stored values of ``names`` from Natron's settings, then apply the look
    to them for the session. Only the keys of those preferences are touched."""
    for name in names:
        for key in compat.stored_keys(name):
            writer.remove(key)
    writer.sync()
    return apply(stored=compat.StoredSettings(writer.target))
