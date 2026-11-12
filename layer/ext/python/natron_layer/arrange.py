# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Natron's window arranged like Nuke's, once it's up: Natron's own widgets moved, nothing of Natron's changed.

Route P (GAPS.md): Python acting on Natron's live interface. Each part looks for Natron's widgets by their kind and
order (the way Natron builds them, ``Gui/ViewerTab.cpp``) and leaves a part as Natron made it when they aren't what
it expects (a release that changed them): nothing breaks, that part just stays Natron's.

- **The viewer's two toolbars** in Nuke's order (Foundry's "Using the Viewer Controls" page names each control):
  the first row has the layer, alpha channel and channels, the viewer process (Natron keeps it in the second row),
  the A and B inputs with the compare operation between them, then on the right the proxy and full-frame switches,
  the zoom and the proxy level; the second row has gain then gamma, each a switch, a field and a slider, then on the
  right refresh, region of interest and pause, the clip-to-format and checkerboard switches, the viewers' lock, and
  the info bar's switch last. Thin separators between groups. Viewers made later are arranged too, as Qt polishes
  them (``watch``).
- **Object names** on the rows and the playback bar (``SngViewerBar1``, ``SngViewerBar2``, ``SngPlayerBar``), so
  the look's stylesheet draws them as Nuke's (flat bars; playback buttons in small raised boxes).
- **The timeline and playback bar in Nuke's order** (Foundry's "Using the Viewer Controls", the timeline picture):
  the playback in and out points as two tall fields at the ends of the frame ruler (``SngInPoint``, ``SngOutPoint``);
  under it the frame rate and time format on the left, the loop mode, then in the middle the set-in button, first
  frame, previous keyframe, previous frame, play backward, the current frame, play, next frame, next keyframe, last
  frame and the set-out button, then the frame increment; the viewers' lock on the right. The ruler itself is drawn
  by Natron (core patch 0006's ``timelineRulerCompact``); with it the ruler and the bar are as compact as Nuke's (the
  current frame's number beside its marker). Since round 6 (.sng9) at Nuke's sizes: the viewer's bars 26 pixels
  high, the info bar 20, the playback buttons 30 x 24 in a 30-pixel row.
- **The properties panels' header in Nuke's order**: the collapse button first, the name field taking the width,
  the colour, undo, redo and revert buttons after it, help, float and close at the right end. Panels opened later
  are arranged too (``watch``).
- **Nuke's default workspace**: in Natron's default layout the viewer takes a little more of the height (58 %), and
  the properties pane starts empty (Natron opens the project's settings there at start).
- **The menu bar's Layout menu is called Workspace**, Nuke's name for the same thing (saved layouts); Natron's other
  menu names stay (its help pages use them).

Nothing here writes Natron's settings or changes a comp; the artist's way back is Natron's own look (Nuke > Look),
which keeps this module out.
"""

from __future__ import annotations

from typing import Any

from . import compat

ARRANGED = "sngArranged"  # dynamic property on a viewer once its bars are arranged
SEPARATOR = "SngViewerSeparator"

# Natron's two viewer rows, widget by widget (Gui/ViewerTab.cpp, 2.6): the kind of each widget in its layout, in order
# (Natron's Button has no class name of its own, so it reads as QPushButton; its channels drop-down as ComboBox).
ROW1 = ("ComboBox", "ComboBox", "ComboBox", "QFrame", "ComboBox", "QPushButton", "QPushButton", "QFrame",
        "QPushButton", "QPushButton", "QPushButton", "QPushButton", "ComboBox", "QFrame", "QPushButton", "QPushButton",
        "QFrame", "Label", "ComboBox", "Label", "ComboBox", "Label", "ComboBox")
ROW2 = ("QPushButton", "SpinBox", "ScaleSliderQWidget", "QPushButton", "QPushButton", "SpinBox", "ScaleSliderQWidget",
        "ComboBox", "QPushButton", "ComboBox", "QPushButton")
ROW1_NAMES = ("layer", "alpha", "channels", "-", "zoom", "sync", "centre", "-", "clip", "full_frame", "roi", "proxy",
              "proxy_level", "-", "refresh", "pause", "-", "a_label", "a_input", "op_icon", "operation", "b_label",
              "b_input")
ROW2_NAMES = ("gain_switch", "gain", "gain_slider", "auto_contrast", "gamma_switch", "gamma", "gamma_slider",
              "process", "checkerboard", "views", "info_bar")

# Nuke's order: "|" a separator, "~" the stretch, a number a spacing in pixels.
NUKE_ROW1 = ("layer", "alpha", "channels", "|", "process", "|", "a_label", "a_input", 2, "operation", 2, "b_label",
             "b_input", "~", "clip", "full_frame", "proxy", "|", "zoom", "|", "proxy_level")
NUKE_ROW2 = ("gain_switch", "gain", "gain_slider", "|", "gamma_switch", "gamma", "gamma_slider", "auto_contrast",
             "~", "refresh", "roi", "pause", "|", "checkerboard", "sync", "centre", "|", "views", "info_bar")
HIDDEN = ("op_icon",)  # Nuke has no picture before the compare operation; its drop-down keeps the tooltip
# Drop-downs drawn flat, text and arrow only, as Nuke's viewer bar draws them (Natron's ComboBox reads the "flat"
# property in this fork's builds, core patch 0004; elsewhere the property does nothing). The A and B inputs keep their
# box, as Nuke's do.
FLAT = ("layer", "alpha", "channels", "process", "operation", "zoom", "proxy_level")


def kind(widget: Any) -> str:
    try:
        return str(widget.metaObject().className()).rsplit(":", 1)[-1]
    except Exception:  # noqa: BLE001  (a widget Qt already deleted)
        return ""


def row_widgets(row: Any) -> list[Any]:
    layout = row.layout()
    if layout is None:
        return []
    found = []
    for i in range(layout.count()):
        widget = layout.itemAt(i).widget()
        if widget is not None:
            found.append(widget)
    return found


def find_rows(viewer: Any, qt: Any) -> tuple[Any, Any] | None:
    """Natron's two toolbar rows of a viewer, or None when they aren't laid out as this module knows them."""
    first = second = None
    for child in viewer.findChildren(qt.QtWidgets.QWidget, options=qt.QtCore.Qt.FindChildOption.FindDirectChildrenOnly):
        kinds = tuple(kind(w) for w in row_widgets(child))
        if kinds == ROW1:
            first = child
        elif kinds == ROW2:
            second = child
    if first is None or second is None:
        return None
    return first, second


def player_bar(viewer: Any, qt: Any) -> Any:
    """The playback bar: the viewer's last row, a line of buttons and fields."""
    layout = viewer.layout()
    if layout is None:
        return None
    for i in range(layout.count() - 1, -1, -1):
        widget = layout.itemAt(i).widget()
        if widget is None:
            continue
        kinds = [kind(w) for w in row_widgets(widget)]
        if kinds.count("QPushButton") >= 8 and "SpinBox" in kinds:
            return widget
        return None
    return None


PLAYER = ("QPushButton", "SpinBox", "QCheckBox", "ClickableLabel", "SpinBox", "ComboBox", "QPushButton", "QPushButton",
          "QPushButton", "QPushButton", "QPushButton", "SpinBox")  # the playback bar's start, to its current frame


def repolish(qt: Any, widget: Any) -> None:
    """Qt applies a stylesheet's rules for object names when a widget is first drawn: after naming a widget, its
    style is applied again to it and to everything inside it."""
    for w in [widget, *widget.findChildren(qt.QtWidgets.QWidget)]:
        style = w.style()
        style.unpolish(w)
        style.polish(w)
        w.update()


def separator(qt: Any, parent: Any) -> Any:
    line = qt.QtWidgets.QFrame(parent)
    line.setObjectName(SEPARATOR)
    line.setFrameShape(qt.QtWidgets.QFrame.Shape.NoFrame)  # the stylesheet paints it: one dark pixel
    line.setFixedWidth(1)
    return line


def relayout(qt: Any, row: Any, order: tuple, widgets: dict[str, Any]) -> None:
    """Empty ``row``'s layout and fill it again in ``order``; widgets left out are hidden."""
    layout = row.layout()
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget() if item is not None else None
        if widget is not None and widget.objectName() != SEPARATOR and kind(widget) == "QFrame":
            widget.hide()  # Natron's own separators: ours take their place
    for entry in order:
        if entry == "|":
            layout.addSpacing(4)
            layout.addWidget(separator(qt, row))
            layout.addSpacing(4)
        elif entry == "~":
            layout.addStretch(1)
        elif isinstance(entry, int):
            layout.addSpacing(entry)
        else:
            widget = widgets[entry]
            hidden = widget.isHidden()
            if widget.parentWidget() is not row:
                widget.setParent(row)
            layout.addWidget(widget)
            widget.setHidden(hidden)


def arrange_viewer(viewer: Any, qt: Any) -> bool:
    """One viewer's toolbars in Nuke's order. False when its rows aren't the ones this module knows."""
    if viewer.property(ARRANGED):
        return True
    rows = find_rows(viewer, qt)
    if rows is None:
        return False
    first, second = rows
    widgets = dict(zip(ROW1_NAMES, row_widgets(first)))
    widgets.update(zip(ROW2_NAMES, row_widgets(second)))
    widgets.pop("-", None)
    for name in HIDDEN:
        widgets[name].hide()
    for name in FLAT:
        widgets[name].setProperty("flat", True)
        widgets[name].update()
    relayout(qt, first, NUKE_ROW1, widgets)
    relayout(qt, second, NUKE_ROW2, widgets)
    first.setObjectName("SngViewerBar1")
    second.setObjectName("SngViewerBar2")
    for row in (first, second):
        row.setFixedHeight(VIEWER_ROW)
    for info in [w for w in viewer.findChildren(qt.QtWidgets.QWidget) if kind(w) == "InfoViewerWidget"]:
        info.setFixedHeight(INFO_ROW)
    bar = player_bar(viewer, qt)
    if bar is not None:
        bar.setObjectName("SngPlayerBar")
        found = row_widgets(bar)
        if not arrange_player(viewer, bar, qt) and tuple(kind(w) for w in found[: len(PLAYER)]) == PLAYER:
            found[len(PLAYER) - 1].setObjectName("SngCurrentFrame")  # Nuke shows the current frame in orange
        repolish(qt, bar)
        for name in ("SngInPoint", "SngOutPoint"):
            for field in viewer.findChildren(qt.QtWidgets.QWidget, name):
                repolish(qt, field)
    repolish(qt, first)
    repolish(qt, second)
    viewer.setProperty(ARRANGED, True)
    return True


# The playback bar's widgets, in Natron's order (Gui/ViewerTab.cpp, 2.6), and Nuke's order for them: "|" a separator,
# "~" the stretch, a number a spacing in pixels. The in and out fields go beside the frame ruler instead.
PLAYER_ALL = PLAYER + ("QPushButton", "QPushButton", "QPushButton", "QPushButton", "QPushButton", "QPushButton",
                       "QPushButton", "SpinBox", "QPushButton", "SpinBox", "QPushButton")
PLAYER_NAMES = ("in_button", "in_point", "fps_switch", "fps_label", "fps", "time_format", "turbo", "loop", "sync",
                "first", "play_back", "current", "play", "last", "prev_frame", "next_frame", "prev_key", "next_key",
                "prev_incr", "incr", "next_incr", "out_point", "out_button")
NUKE_PLAYER = ("fps_switch", 3, "fps_label", "fps", "time_format", "|", "loop", "turbo", "~", "in_button", "first",
               "prev_key", "prev_frame", "play_back", "current", "play", "next_frame", "next_key", "last",
               "out_button", 8, "prev_incr", "incr", "next_incr", "~", "sync")
PLAYER_BUTTON = (30, 24)  # Nuke's playback buttons, flat boxes a little wider than tall (round 6, .sng9: measured at
# about 34 x 27 on Foundry's newest timeline picture and 24 high on its older viewer picture; 18 high until .sng8)
PLAYER_ROW = 30  # the playback bar's height: its buttons and fields, three pixels above and below (Nuke's row: 36)
VIEWER_ROW = 26  # each of the viewer's two bars, as Nuke's (Foundry's viewer pictures at 1x: 26 and a one-pixel line)
INFO_ROW = 20  # the viewer's info bar under the picture (Nuke's: 26; Natron's: the font's height, 14 at 11 pixels)
POINT_WIDTH = 46  # the in and out fields at the ruler's ends
RULER_HEIGHT = 54  # Natron's ruler drawn as Natron's (current frame's number over its marker): room for both lines


def ruler_height(ruler: Any) -> int:
    """The ruler's height. Drawn as Nuke's (preference ``timelineRulerCompact``, this fork's builds), the current frame's
    number sits beside its marker, so the ruler is as compact as Nuke's: a line for the marker, the ticks and the
    numbers beside them, and a line for the frame numbers (Foundry's timeline picture: the ruler a little more than
    five digits tall). Otherwise room for Natron's two lines of text over the ticks."""
    if compat.setting_value("timelineRulerCompact") is not True:
        return max(ruler.minimumHeight(), RULER_HEIGHT)
    # The ruler draws its text in Natron's font at its "Font size" preference (Gui/TimeLineGui.cpp), not the
    # widget's: a line of frame numbers, the gap to the ticks' baseline (5), the marker's number standing on it, and
    # a few pixels around.
    qt = compat.qt_modules()
    font = qt.QtGui.QFont(ruler.font())
    font.setPointSizeF(float(compat.setting_value("fontSize") or font.pointSizeF()))
    metrics = qt.QtGui.QFontMetrics(font)
    return metrics.height() + round(metrics.capHeight()) + 11


def arrange_player(viewer: Any, bar: Any, qt: Any) -> bool:
    """The playback bar in Nuke's order and the in and out fields beside the frame ruler. False (nothing moved) when
    the bar or the viewer's layout isn't the one this module knows."""
    found = row_widgets(bar)
    if tuple(kind(w) for w in found) != PLAYER_ALL:
        return False
    timeline = [w for w in viewer.findChildren(qt.QtWidgets.QWidget) if kind(w) == "TimeLineGui"]
    layout = viewer.layout()
    if len(timeline) != 1 or layout is None or layout.indexOf(timeline[0]) < 0:
        return False
    widgets = dict(zip(PLAYER_NAMES, found))
    relayout(qt, bar, NUKE_PLAYER, widgets)
    compact = compat.setting_value("timelineRulerCompact") is True
    for name in NUKE_PLAYER:
        if isinstance(name, str) and kind(widgets.get(name)) == "QPushButton":
            widgets[name].setFixedSize(*PLAYER_BUTTON)
        elif compact and isinstance(name, str) and name in widgets:  # not "|" and "~"
            widgets[name].setMaximumHeight(PLAYER_BUTTON[1])  # fields and drop-downs as tall as the buttons
    if compact:
        bar.setFixedHeight(PLAYER_ROW)
    widgets["current"].setObjectName("SngCurrentFrame")
    # The ruler's row: [in] ruler [out], a layout inside the viewer's own, so the ruler (an OpenGL widget) keeps its
    # parent; only the two fields move to the viewer.
    ruler = timeline[0]
    height = ruler_height(ruler)
    if height < RULER_HEIGHT:
        ruler.setFixedHeight(height)  # smaller than Natron's own size hint
    else:
        ruler.setMinimumHeight(height)
    index = layout.indexOf(ruler)
    layout.removeWidget(ruler)
    row = qt.QtWidgets.QHBoxLayout()
    row.setContentsMargins(2, 1, 2, 0)
    row.setSpacing(2)
    for name, object_name in (("in_point", "SngInPoint"), ("out_point", "SngOutPoint")):
        field = widgets[name]
        hidden = field.isHidden()
        field.setParent(viewer)
        field.setObjectName(object_name)
        field.setAlignment(qt.QtCore.Qt.AlignmentFlag.AlignCenter)
        field.setFixedWidth(POINT_WIDTH)
        field.setMinimumHeight(0)
        field.setMaximumHeight(16777215)
        field.setSizePolicy(qt.QtWidgets.QSizePolicy.Policy.Fixed, qt.QtWidgets.QSizePolicy.Policy.Preferred)
        field.setHidden(hidden or ruler.isHidden())
    row.addWidget(widgets["in_point"])
    row.addWidget(ruler, 1)
    row.addWidget(widgets["out_point"])
    layout.insertLayout(index, row)
    follow_ruler(qt, ruler, [widgets["in_point"], widgets["out_point"]])
    return True


_filters: list[Any] = []  # the event filters below, kept alive (PySide would drop them otherwise)
_classes: dict[str, Any] = {}


def _filter_class(qt: Any, name: str, handle: Any) -> Any:
    """A QObject subclass whose eventFilter calls ``handle(watched, event)`` (made once per name: Qt is only there
    inside Natron)."""
    if name not in _classes:

        class _Filter(qt.QtCore.QObject):
            def __init__(self, parent: Any, call: Any) -> None:
                super().__init__(parent)
                self._call = call

            def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802  (Qt's name)
                try:
                    self._call(watched, event)
                except Exception:  # noqa: BLE001,S110  (a nicety: never in the way of Natron's own events)
                    pass
                return False

        _classes[name] = _Filter
    return _classes[name]


def follow_ruler(qt: Any, ruler: Any, fields: list[Any]) -> Any:
    """The in and out fields shown and hidden with the frame ruler: Natron's "hide timeline" hides only the ruler
    (ViewerTab::setTimelineVisible), and the fields, moved beside it, would stay alone in an empty row. The ruler's
    own hidden flag is followed, not its parent's, so switching viewer tabs changes nothing."""
    shown = (qt.QtCore.QEvent.Type.Show, qt.QtCore.QEvent.Type.Hide)

    def handle(_watched: Any, event: Any) -> None:
        if event.type() in shown:
            for field in fields:
                field.setHidden(ruler.isHidden())

    watcher = _filter_class(qt, "follow", handle)(ruler, handle)
    ruler.installEventFilter(watcher)
    _filters.append(watcher)
    return watcher


HEADER = "DockablePanelHeader"  # the properties panels' header (core patch 0002 names it)
HEADER_ARRANGED = "sngHeaderArranged"


def arrange_header(header: Any, qt: Any) -> bool:
    """A properties panel's header in Nuke's order: the collapse button first, the name field taking the width, the
    colour, undo, redo and revert buttons after it, then help, float and close at the right end. Natron's header is
    [icon, centre, name] ~ [colour, (overlay), undo, redo, revert] ~ [(group), help, hide unmodified, collapse, float,
    close]; anything else is left as it is."""
    if header.property(HEADER_ARRANGED):
        return True
    header.setProperty(HEADER_ARRANGED, True)
    layout = header.layout()
    if layout is None:
        return False
    items = [layout.itemAt(i) for i in range(layout.count())]
    spacers = [i for i, item in enumerate(items) if item.spacerItem() is not None]
    widgets = [item.widget() for item in items if item.widget() is not None]
    if len(spacers) != 2 or len(widgets) < 8 or not all(kind(w) == "QPushButton" for w in widgets[-3:]):
        return False
    collapse = widgets[-3]
    first, second = spacers

    def part(start: int, stop: int) -> list[Any]:
        return [items[i].widget() for i in range(start, stop)
                if items[i].widget() is not None and items[i].widget() is not collapse]

    left, middle, right = part(0, first), part(first + 1, second), part(second + 1, len(items))
    names = [w for w in left if kind(w) in ("LineEdit", "QLineEdit")]
    while layout.count():
        layout.takeAt(0)
    layout.addWidget(collapse)
    for w in left:
        layout.addWidget(w, 1 if names and w is names[0] else 0)
    if not names:
        layout.addStretch(1)
    for w in middle:
        layout.addWidget(w)
    layout.addSpacing(8)
    for w in right:
        layout.addWidget(w)
    return True


def arrange_headers(window: Any, qt: Any) -> int:
    done = 0
    for header in window.findChildren(qt.QtWidgets.QFrame, HEADER):
        if not header.property(HEADER_ARRANGED) and arrange_header(header, qt):
            done += 1
    return done


def viewers(window: Any, qt: Any) -> list[Any]:
    """Natron's viewers (ViewerTab), found through the panes (``pane1``...) so the search stays small."""
    found = []
    expr = qt.QtCore.QRegularExpression("^pane[0-9]+$")
    for pane in window.findChildren(qt.QtWidgets.QWidget, expr):
        for child in pane.findChildren(qt.QtWidgets.QWidget, options=qt.QtCore.Qt.FindChildOption.FindDirectChildrenOnly):
            if kind(child) == "ViewerTab":
                found.append(child)
    # A floating viewer lives in its own window.
    app = compat.application()
    for top in app.topLevelWidgets() if app is not None else []:
        if top is window or not top.isVisible():
            continue
        for child in top.findChildren(qt.QtWidgets.QWidget):
            if kind(child) == "ViewerTab":
                found.append(child)
    return found


def arrange_all(window: Any, qt: Any) -> dict[str, int]:
    done = {"viewers": 0, "viewers left as Natron's": 0}
    for viewer in viewers(window, qt):
        if viewer.property(ARRANGED):
            continue
        if arrange_viewer(viewer, qt):
            done["viewers"] += 1
        else:
            done["viewers left as Natron's"] += 1
            viewer.setProperty(ARRANGED, True)  # don't look at it again
    return done


def rename_menus(window: Any) -> int:
    """Natron's Layout menu as Nuke's Workspace (saved layouts, the default one, the panes' tabs)."""
    renamed = 0
    for action in window.menuBar().actions():
        if action.text().replace("&", "") == "Layout":
            action.setText("Workspace")
            renamed += 1
    return renamed


def close_project_settings(window: Any, qt: Any) -> int:
    """Natron opens the project's settings in the properties pane at start; Nuke's properties bin starts empty (its
    project settings open with S). Closed once, at start; Display > Project Settings opens them again."""
    closed = 0
    for panel in window.findChildren(qt.QtWidgets.QWidget):
        if kind(panel) == "DockablePanel" and panel.isVisible():
            if qt.QtCore.QMetaObject.invokeMethod(panel, "closePanel"):
                closed += 1
    return closed


def widen_panel_count(window: Any, qt: Any) -> int:
    """The properties pane's "how many panels" field (Natron sizes it for its own larger font, so "10" showed as
    "1(" in ours): wide enough for two digits. Found by its tooltip; left alone when it isn't found."""
    for field in window.findChildren(qt.QtWidgets.QLineEdit):
        if kind(field) == "SpinBox" and "maximum of panels" in field.toolTip():
            field.setFixedWidth(max(field.width(), field.fontMetrics().horizontalAdvance("100") + 6))
            return 1
    return 0


VIEWER_SHARE = 0.58  # Nuke's default workspace: the viewer takes a little more than half the height
NATRON_VIEWER_SHARE = 0.5  # Natron's default layout (Gui10.cpp): viewer and node graph half and half


def viewer_share(window: Any, qt: Any) -> bool:
    """In Natron's default layout (the viewer's pane ``pane1`` over the node graph's ``pane3``, half and half), the
    viewer takes Nuke's larger share. A layout the artist made keeps its sizes."""
    for splitter in window.findChildren(qt.QtWidgets.QSplitter):
        if splitter.orientation() != qt.QtCore.Qt.Orientation.Vertical or splitter.count() != 2:
            continue
        if [splitter.widget(0).objectName(), splitter.widget(1).objectName()] != ["pane1", "pane3"]:
            continue
        sizes = list(splitter.sizes())
        total = sum(sizes)
        if total <= 0 or abs(sizes[0] / total - NATRON_VIEWER_SHARE) > 0.03:
            return False
        top = int(total * VIEWER_SHARE)
        splitter.setSizes([top, total - top])
        return True
    return False


_watchers: list[Any] = []  # timers polling the window: none since the audit of 11 November 2026 (NAT-13)
_queued: list[bool] = []


def watch(window: Any, qt: Any) -> Any:
    """Viewers made later (a new viewer, a pane split, a floating viewer) and new properties panels arranged as Qt
    polishes them, before they're first drawn: an event filter on the application that only looks for a Polish of
    a ViewerTab or of a panel's header, and queues one arrangement for the next turn of the event loop (several new
    widgets at once make one). No timer looks at the window."""
    application = compat.application()
    if application is None:
        return None
    polish = qt.QtCore.QEvent.Type.Polish

    def arrange_queued() -> None:
        _queued.clear()
        arrange_all(window, qt)
        arrange_headers(window, qt)

    def handle(watched: Any, event: Any) -> None:
        if event.type() != polish or _queued:
            return
        if kind(watched) == "ViewerTab" or watched.objectName() == HEADER:
            _queued.append(True)
            qt.QtCore.QTimer.singleShot(0, arrange_queued)

    watcher = _filter_class(qt, "polish", handle)(application, handle)
    application.installEventFilter(watcher)
    _filters.append(watcher)
    return watcher


def install(window: Any) -> dict[str, int]:
    """Once the window is up (skin.polish): the viewers' bars, the Workspace menu, and the watch for new viewers."""
    qt = compat.qt_modules()
    if qt is None:
        return {}
    done = arrange_all(window, qt)
    done["menus renamed"] = rename_menus(window)
    done["viewer share"] = int(viewer_share(window, qt))
    done["project settings closed"] = close_project_settings(window, qt)
    done["panel count field"] = widen_panel_count(window, qt)
    done["panel headers"] = arrange_headers(window, qt)
    watch(window, qt)
    return done
