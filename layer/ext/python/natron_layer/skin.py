# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The skin: Natron's interface drawn like Nuke's, for this session, with no change to Natron's own files.

Three parts, each set from Python while Natron starts (``install``, from initGui.py, before Natron builds its
window), each standing aside for what the artist chose:

- **Icons.** Natron loads every interface picture through one function that first looks in Qt's picture cache
  under the picture's number (``GuiApplicationManager::getIcon``). The skin puts our own pictures
  (``ext/icons/``, drawn by ``tools/make_icons.py``) in that cache under those numbers (``ext/icons/pixmaps.toml``)
  before the window exists, so Natron builds its toolbar, viewer, playback bar and panels with them, two-state
  buttons included. A picture we haven't drawn stays Natron's.
- **Font.** Natron registers its own font (Droid Sans) and names it everywhere (the stylesheet, the node graph's
  labels). The skin registers ours (DejaVu Sans, ``ext/fonts/``), takes Natron's registration out and tells Qt to
  use ours wherever Droid Sans is asked for, so every text follows. Not when the artist chose a font in Natron's
  Preferences (``systemFont`` stored).
- **Stylesheet.** The look's stylesheet (``ext/qss/nuke.qss``) is written for the session into a temporary file
  with the layer's own pictures' paths filled in and, unless the artist stored a ``fontSize``, the skin's font size
  (``session_stylesheet``); that file is the session value of Natron's ``stylesheetFile`` preference.

Nothing here writes Natron's settings. The artist's way back is the Nuke menu's **Look › Natron's own look for
me**, kept in the layer's own config.json on their click (``LOOK_KEY``): then the skin and the look's visual
preferences stay out (Natron's stylesheet, colours, icons and font), the Nuke habits stay. ``NATRON_LAYER_SKIN=off``
does the same for one session (the tests' "before" pictures).
"""

from __future__ import annotations

import dataclasses
import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any

from . import compat, paths, user_config

NATRON_FONT = "Droid Sans"  # Natron's own interface font (NATRON_FONT, compiled in)
NATRON_SIZES = (11, 18, 24, 26)  # Natron's icon sizes in pixels at 96 dpi (Gui/GuiDefines.h)
LOOK_KEY = "look"  # in the layer's config.json: "natron" when the artist chose Natron's own look
LAYER_PREFIX = "@layer/"
CACHE_LIMIT_KB = 65536  # Qt's picture cache, raised so our pictures are never dropped (Qt's default is 10 MB)


@dataclasses.dataclass
class Report:
    font: str = ""  # the font now in use, or why Natron's stayed
    icons: int = 0  # pictures given to Natron
    theme: str = ""  # the icon theme Qt reads the menus' icons from (the File menu), or "" when not set
    missing: list[str] = dataclasses.field(default_factory=list)  # table entries whose PNG isn't there
    off: str = ""  # why the skin stayed out (the artist's choice, the environment)

    def summary(self) -> str:
        if self.off:
            return f"Skin: off ({self.off})."
        parts = [f"{self.icons} icons", f"font {self.font}"]
        if self.theme:
            parts.append(f"menu icons from the {self.theme} theme")
        if self.missing:
            parts.append(f"{len(self.missing)} icon files missing ({', '.join(self.missing[:5])})")
        return "Skin: " + "; ".join(parts) + "."


last_report: Report | None = None


# --- Whether the skin applies ---


def natron_look_chosen() -> bool:
    """The artist chose Natron's own look (menu › Nuke › Look), or this session asked for it."""
    if os.environ.get("NATRON_LAYER_SKIN", "").strip().lower() == "off":
        return True
    return user_config.load().get(LOOK_KEY) == "natron"


def why_off() -> str:
    if os.environ.get("NATRON_LAYER_SKIN", "").strip().lower() == "off":
        return "NATRON_LAYER_SKIN=off"
    if user_config.load().get(LOOK_KEY) == "natron":
        return "you chose Natron's own look (Nuke > Look)"
    return ""


def settings() -> dict[str, Any]:
    """The look's ``[skin]`` table (font file, font size, icons on or off)."""
    import tomllib  # noqa: PLC0415

    with open(paths.preset("nuke_look.toml"), "rb") as file:
        data = tomllib.load(file)
    return dict(data.get("skin", {}))


def layer_path(value: str) -> Path:
    if value.startswith(LAYER_PREFIX):
        return paths.layer_root() / value[len(LAYER_PREFIX) :]
    return Path(value)


# --- The stylesheet ---


def font_block(size: float) -> str:
    """Natron's own stylesheet starts with its font and size; the same four rules with the skin's size."""
    size_text = f"{size:g}pt"
    return (
        "\n/* ---- The skin's font size (natron_layer/skin.py; left out when you chose a size in Natron) ---- */\n"
        f"QWidget {{ font-size: {size_text}; }}\n"
        f"QListView {{ font-size: {size_text}; }}\n"
        f"QComboBox::drop-down {{ font-size: {size_text}; }}\n"
        f"QInputDialog {{ font-size: {size_text}; }}\n"
    )


def session_folder() -> Path:
    return Path(tempfile.gettempdir()) / "natron-layer"


def session_stylesheet(source: str, stored: compat.StoredSettings | None = None) -> str:
    """The stylesheet file for this session: ``source`` (the look's nuke.qss) with ``@layer/`` filled in with the
    layer's folder and, unless the artist stored a font size, the skin's size. Written once per content into the
    system's temporary folder (never into Natron's settings or the artist's files); returns its path, or ``source``
    when it can't be written."""
    stored = compat.StoredSettings.of_natron() if stored is None else stored
    try:
        text = Path(source).read_text(encoding="utf-8")
    except OSError:
        return source
    text = text.replace(LAYER_PREFIX, paths.layer_root().as_posix() + "/")
    size = settings().get("font_size")
    if size and not stored.contains("fontSize"):
        text += font_block(float(size))
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    target = session_folder() / f"nuke-{digest}.qss"
    if not target.is_file():
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            handle, temporary = tempfile.mkstemp(prefix="nuke-", suffix=".tmp", dir=target.parent)
            with os.fdopen(handle, "w", encoding="utf-8") as file:
                file.write(text)
            os.replace(temporary, target)
        except OSError:
            return source
    return target.as_posix()


# --- The icons ---


def icon_table() -> list[dict[str, Any]]:
    import tomllib  # noqa: PLC0415

    table = paths.ext() / "icons" / "pixmaps.toml"
    try:
        with open(table, "rb") as file:
            return list(tomllib.load(file).get("icon", []))
    except OSError:
        return []


def _screen_scale(qt: Any) -> tuple[float, float]:
    """Natron's own size factor (logical dpi / 96, its TO_DPIX) and the screen's device pixel ratio."""
    app = compat.application()
    screen = app.primaryScreen() if app is not None else None
    if screen is None:
        return 1.0, 1.0
    return float(screen.logicalDotsPerInchX()) / 96.0, float(screen.devicePixelRatio())


def install_icons(qt: Any) -> tuple[int, list[str]]:
    """Put our pictures in Qt's picture cache under Natron's numbers (the plain number, and ``<number>@<size>``
    for each size Natron asks for), so Natron's ``getIcon`` finds ours. Returns (pictures given, files missing)."""
    QtGui, QtCore = qt.QtGui, qt.QtCore
    if QtGui.QPixmapCache.cacheLimit() < CACHE_LIMIT_KB:
        QtGui.QPixmapCache.setCacheLimit(CACHE_LIMIT_KB)
    ratio, dpr = _screen_scale(qt)
    folder = paths.ext() / "icons"
    given, missing = 0, []
    for row in icon_table():
        one = folder / row["file"]
        two = one.with_name(one.stem + "@2x.png")
        if not one.is_file():
            missing.append(row["file"])
            continue
        size = int(row.get("size", 18))
        sharp = ratio * dpr > 1.01 and two.is_file()
        picture = QtGui.QPixmap(str(two if sharp else one))
        if picture.isNull():
            missing.append(row["file"])
            continue
        if sharp:
            device = max(1, round(size * ratio * dpr))
            if picture.width() != device:
                picture = picture.scaled(device, device, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                         QtCore.Qt.TransformationMode.SmoothTransformation)
            picture.setDevicePixelRatio(dpr)
        number = int(row["number"])
        QtGui.QPixmapCache.insert(str(number), picture)
        for wanted in {*NATRON_SIZES, size}:
            for pixels in {int(wanted * ratio), round(wanted * ratio)}:
                QtGui.QPixmapCache.insert(f"{number}@{pixels}", picture)
        given += 1
    return given, missing


THEME = "natron-layer"  # ext/icons/theme/<THEME>/index.theme, written by tools/make_icons.py


def install_theme(qt: Any) -> str:
    """Natron gives its File menu's actions icons by name (``QIcon::fromTheme("document-open", ...)``, falling back
    to its own pictures): our icon theme answers those names first. Returns the theme's name, or "" when it isn't
    there."""
    folder = paths.ext() / "icons" / "theme"
    if not (folder / THEME / "index.theme").is_file():
        return ""
    QtGui = qt.QtGui
    search = [str(folder)] + [str(p) for p in QtGui.QIcon.themeSearchPaths() if str(p) != str(folder)]
    QtGui.QIcon.setThemeSearchPaths(search)
    QtGui.QIcon.setThemeName(THEME)
    return THEME


# --- The font ---


def install_font(qt: Any, stored: compat.StoredSettings) -> str:
    """Our font for every text Natron draws, unless the artist chose a font in Natron's Preferences."""
    if stored.contains("systemFont"):
        return "yours (Natron's Preferences), kept"
    wanted = settings()
    font_file = layer_path(str(wanted.get("font", "")))
    if not font_file.is_file():
        return "Natron's (the skin's font file isn't there)"
    QtGui, QtWidgets = qt.QtGui, qt.QtWidgets
    database = QtGui.QFontDatabase
    # Natron registered Droid Sans before any script ran; take that registration out so Qt substitutes ours
    # wherever Natron names Droid Sans (its stylesheet's first rule, the node graph's labels).
    database.removeAllApplicationFonts()
    found = database.applicationFontFamilies(database.addApplicationFont(str(font_file)))
    if not found:
        return "Natron's (Qt couldn't read the skin's font)"
    family = str(found[0])
    QtGui.QFont.insertSubstitution(NATRON_FONT, family)
    size = float(wanted.get("font_size") or 0)
    font = QtGui.QFont(family)
    font.setPointSizeF(size if size and not stored.contains("fontSize") else QtWidgets.QApplication.font().pointSizeF())
    # Letters placed at their true widths: the node graph draws node names with this font scaled by its zoom, and
    # widths fitted to whole pixels then open gaps inside words ("Vie wer1"); checked on the fork, no hinting is the
    # setting that keeps them closed.
    font.setHintingPreference(QtGui.QFont.HintingPreference.PreferNoHinting)
    QtWidgets.QApplication.setFont(font)
    return f"{family} {font.pointSizeF():g} pt"


# --- Installing ---


def install(stored: compat.StoredSettings | None = None) -> Report:
    """The skin for this session: icons and font. Interface only, before Natron builds its window (initGui.py)."""
    global last_report  # noqa: PLW0603
    report = Report()
    off = why_off()
    qt = compat.qt_modules()
    if off:
        report.off = off
    elif qt is None or qt.QtGui is None or compat.application() is None:
        report.off = "no interface"
    else:
        stored = compat.StoredSettings.of_natron() if stored is None else stored
        if settings().get("icons", True):
            report.icons, report.missing = install_icons(qt)
            report.theme = install_theme(qt)
        report.font = install_font(qt, stored)
    last_report = report
    return report


def polish(window: Any) -> dict[str, int]:
    """Once the window is up: the left toolbar's buttons show our 20-pixel pictures at their size (Natron's
    buttons keep Qt's 16), and the default layout's properties pane takes Nuke's share of the width
    (``default_layout``). Returns what was done."""
    qt = compat.qt_modules()
    if qt is None or natron_look_chosen():
        return {}
    ratio, _dpr = _screen_scale(qt)
    side = int(round(int(settings().get("toolbar_icon", 20)) * ratio))
    done = {"toolbar buttons": 0, "layout": 0}
    for bar in window.findChildren(qt.QtWidgets.QToolBar):
        for button in bar.findChildren(qt.QtWidgets.QToolButton):
            button.setIconSize(qt.QtCore.QSize(side, side))
            done["toolbar buttons"] += 1
    done["layout"] = int(default_layout(window, qt))
    return done


NATRON_PROPERTIES_SHARE = 0.35  # Natron's default layout (Gui10.cpp, createDefaultLayout1): properties at 35 %


def default_layout(window: Any, qt: Any, tries: int = 20) -> bool:
    """Natron's default layout is already Nuke's arrangement (viewer top left, node graph under it, properties on
    the right, toolbar on the left); Nuke's properties bin is narrower. When the window still has Natron's default
    layout (its properties pane, ``pane2``, at Natron's 35 % of the width), give the properties the look's share.
    A layout the artist made or a comp brought keeps its sizes."""
    share = float(settings().get("properties_share", 0) or 0)
    if not 0.1 < share < 0.6:
        return False
    for splitter in window.findChildren(qt.QtWidgets.QSplitter):
        if splitter.orientation() != qt.QtCore.Qt.Orientation.Horizontal or splitter.count() != 2:
            continue
        if splitter.widget(1).objectName() != "pane2":
            continue
        sizes = list(splitter.sizes())
        total = sum(sizes)
        if total <= 0 or min(sizes) <= 0:
            if tries > 0:  # not laid out yet: look again shortly
                qt.QtCore.QTimer.singleShot(250, lambda: default_layout(window, qt, tries - 1))
            return False
        if abs(sizes[1] / total - NATRON_PROPERTIES_SHARE) > 0.03:
            return False
        right = int(total * share)
        splitter.setSizes([total - right, right])
        return True
    return False


# --- The artist's choice (the Nuke menu) ---


def choose_natron_look(confirm: Any = None, done: Any = None) -> bool:
    """Menu › Nuke › Look › Natron's own look for me…: after the artist's yes, keep "natron" in the layer's config so
    the skin and the look's colours stay out from the next start. Natron's settings aren't touched."""
    from . import gui  # noqa: PLC0415

    confirm = gui.ask if confirm is None else confirm
    done = gui.tell if done is None else done
    if user_config.load().get(LOOK_KEY) == "natron":
        done("Natron's own look", "You already have Natron's own look. Nuke > Look > Nuke look for me brings the "
             "Nuke look back.")
        return False
    if not confirm("Natron's own look", "Use Natron's own look (its stylesheet, colours, icons and font) instead of "
                   "this build's Nuke look, for you on this PC?\n\nThe Nuke habits (keys, Tab names, ToolSets) stay. "
                   "It shows when Natron starts again."):
        return False
    data = user_config.load()
    data[LOOK_KEY] = "natron"
    user_config.save(data)
    done("Natron's own look", "Done: restart Natron to see its own look. Nuke > Look > Nuke look for me brings this "
         "build's look back.")
    return True


def choose_nuke_look(confirm: Any = None, done: Any = None) -> bool:
    """Menu › Nuke › Look › Nuke look for me…: back to this build's look from the next start."""
    from . import gui  # noqa: PLC0415

    confirm = gui.ask if confirm is None else confirm
    done = gui.tell if done is None else done
    if user_config.load().get(LOOK_KEY) != "natron":
        done("Nuke look", "You already have this build's Nuke look.")
        return False
    if not confirm("Nuke look", "Use this build's Nuke look again (its stylesheet, colours, icons and font)? It "
                   "shows when Natron starts again."):
        return False
    data = user_config.load()
    data.pop(LOOK_KEY, None)
    user_config.save(data)
    done("Nuke look", "Done: restart Natron to see the Nuke look.")
    return True
