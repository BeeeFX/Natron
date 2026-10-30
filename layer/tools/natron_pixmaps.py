# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Natron's own interface pictures, read from the fork's source: each ``NATRON_PIXMAP_*`` with its number (its place
in ``Global/Enums.h``, which is the key Natron caches the picture under) and the file Natron loads for it
(``Gui/GuiApplicationManager.cpp``, ``getIcon``).

The skin (``natron_layer/skin.py``) gives Natron our pictures by putting them in Qt's picture cache under those
numbers before Natron builds its window, so the numbers must be the ones the release was built with. This module
is how the icon maker (``make_icons.py``) writes the table the skin reads (``ext/icons/pixmaps.toml``) and how the
smoke test checks that table against the source of the release this branch carries.

Standard library only, any Python 3.10+.
"""

from __future__ import annotations

import re
from pathlib import Path

ENUM_START = "enum PixmapEnum"
CASE = re.compile(r"case\s+(NATRON_PIXMAP_\w+)\s*:")
PATH = re.compile(r'path\s*=\s*NATRON_IMAGES_PATH\s*"([^"]+)"(.*);')


def enum_numbers(enums_h: str) -> dict[str, int]:
    """``{"NATRON_PIXMAP_PLAYER_PREVIOUS": 0, ...}`` from Global/Enums.h."""
    start = enums_h.index(ENUM_START)
    body = enums_h[enums_h.index("{", start) + 1 : enums_h.index("};", start)]
    numbers: dict[str, int] = {}
    current = -1
    for raw in body.splitlines():
        line = raw.split("//", 1)[0].strip().rstrip(",")
        if not line.startswith("NATRON_PIXMAP_"):
            continue
        if "=" in line:
            name, value = (part.strip() for part in line.split("=", 1))
            current = int(value)
        else:
            name = line
            current += 1
        numbers[name] = current
    return numbers


def enum_files(manager_cpp: str, icon_set: int = 3) -> dict[str, str]:
    """``{"NATRON_PIXMAP_PLAYER_PREVIOUS": "back1.png", ...}`` from getIcon's switch; the grouping icons with the
    icon set Natron picks (3, or 2 when "Use black & white toolbutton icons" is on)."""
    start = manager_cpp.index("GuiApplicationManager::getIcon(PixmapEnum e,")
    end = manager_cpp.index("} // getIcon", start)
    files: dict[str, str] = {}
    pending: list[str] = []
    for raw in manager_cpp[start:end].splitlines():
        line = raw.strip()
        cases = CASE.findall(line)
        if cases:
            pending.extend(cases)
            continue
        found = PATH.search(line)
        if found and pending:
            name = found.group(1)
            rest = found.group(2)
            if "iconSetStr" in rest:  # "GroupingIcons/Set" + iconSetStr + "/image_grouping_" + iconSetStr + ".png"
                parts = re.findall(r'"([^"]*)"', rest)
                name = name + str(icon_set) + "".join(p + (str(icon_set) if i < len(parts) - 1 else "")
                                                       for i, p in enumerate(parts))
            for case in pending:
                files[case] = name
            pending = []
        elif line.startswith("break"):
            pending = []
    return files


def table(repo: Path) -> list[tuple[str, int, str]]:
    """``[(enum name, number, file), ...]`` in number order, from the fork's source at ``repo``."""
    numbers = enum_numbers((repo / "Global" / "Enums.h").read_text(encoding="utf-8", errors="replace"))
    files = enum_files((repo / "Gui" / "GuiApplicationManager.cpp").read_text(encoding="utf-8", errors="replace"))
    return sorted(((name, numbers[name], files.get(name, "")) for name in numbers), key=lambda row: row[1])


if __name__ == "__main__":
    import sys

    for name, number, file in table(Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[2])):
        print(number, name, file)
