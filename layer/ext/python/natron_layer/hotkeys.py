# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Nuke's keys that Natron lacks, and the artist's own Nuke shortcuts after an import.

Natron already has most of Nuke's default keys (B, C, D, G, M, O, P, R, T, W, the dot, Ctrl+G, Alt+C, Alt+K…; see
``ext/presets/nuke_hotkeys.toml``). The ones it lacks are added as menu commands (menu bar › Nuke) through Natron's
``addMenuCommand``, each with its Nuke key as default, which the artist can change in Natron's shortcut editor
(Global group). Natron gives such a command's key to the whole window, so each command first looks at where the
keyboard is: in a node graph it does its job; anywhere else (the viewer's K stops playback, the curve editor's K
sets constant interpolation, Shift+Y in the viewer shows input A's luminance) the key is handed on to that widget
as if the layer weren't there.

Natron's built-in keys are never rewritten (they live in Natron's settings, and the layer writes none of them).
"""

from __future__ import annotations

import dataclasses
from typing import Any

from . import aliases, compat, paths

# The grid \ snaps to, in node graph units: 110 × 24, our understanding of Nuke's default grid (Preferences › Node
# Graph), not checked against a real Nuke. Change it here if it feels off.
GRID = (110, 24)

_registered: list[str] = []


@dataclasses.dataclass(frozen=True)
class Hotkey:
    keys: str
    where: str
    nuke: str
    natron: str
    status: str
    menu: str = ""
    command: str = ""
    why: str = ""


def table() -> list[Hotkey]:
    """Nuke's default keys next to Natron's (ext/presets/nuke_hotkeys.toml)."""
    import tomllib  # noqa: PLC0415

    with open(paths.preset("nuke_hotkeys.toml"), "rb") as file:
        data = tomllib.load(file)
    fields = {f.name for f in dataclasses.fields(Hotkey)}
    return [Hotkey(**{k: v for k, v in entry.items() if k in fields}) for entry in data.get("key", [])]


def added() -> list[Hotkey]:
    return [key for key in table() if key.status == "added"]


# --- Where the keyboard is ---


def _focus_widget() -> Any:
    app = compat.application()
    return app.focusWidget() if app is not None else None


def _class_names(widget: Any) -> list[str]:
    names = []
    while widget is not None:
        try:
            names.append(str(widget.metaObject().className()))
            widget = widget.parentWidget()
        except Exception:  # noqa: BLE001
            break
    return names


def in_node_graph(widget: Any = None) -> bool:
    """Whether the keyboard focus is in one of Natron's node graphs (its class is NodeGraph, a QGraphicsView). With
    no interface at all (a test calling the command), True."""
    widget = _focus_widget() if widget is None else widget
    if widget is None:
        return compat.application() is None
    return any(name.rsplit(":", 1)[-1] == "NodeGraph" for name in _class_names(widget))


_passing: list[str] = []  # the key being handed on (Natron may bring it back to a command: then nothing happens)


def pass_key_on(shortcut: str, widget: Any = None) -> bool:
    """Give the key to the widget that has the focus, as if no command had taken it. It's sent straight to the
    widget; a key that widget doesn't use climbs to Natron's window, which does what Natron does with it (K stops
    playback). If that brings the key back to one of the layer's commands, the command does nothing (``_passing``),
    so a key is never handed on twice."""
    widget = _focus_widget() if widget is None else widget
    qt = compat.qt_modules()
    found = compat.key_and_modifiers(shortcut)
    if widget is None or qt is None or found is None or _passing:
        return False
    key, modifiers = found
    text = shortcut if len(shortcut) == 1 else ""
    events = qt.QtCore.QEvent
    _passing.append(shortcut)
    try:
        for kind in (events.Type.KeyPress, events.Type.KeyRelease):
            event = qt.QtGui.QKeyEvent(kind, key, modifiers, text.lower())
            qt.QtWidgets.QApplication.sendEvent(widget, event)
    finally:
        _passing.clear()
    return True


def _node_graph_only(shortcut: str) -> bool:
    """True when the command should act; otherwise the key has been passed on (or is being passed on)."""
    if _passing:
        return False
    if in_node_graph():
        return True
    pass_key_on(shortcut)
    return False


# --- The commands (Natron calls them by name: natron_layer.hotkeys.<name>) ---


def copy_node() -> Any:
    """K: Nuke's Copy (the alias), fed by the selected node, in the node graph the artist is in (a Group's too)."""
    if not _node_graph_only("K"):
        return None
    app = compat.active_app()
    return aliases.make("Copy", app, compat.focused_group(app))


def node_info() -> str | None:
    """I: what Nuke's node info shows that Natron's Python can read: class, label, inputs, size, frame range."""
    if not _node_graph_only("I"):
        return None
    app = compat.active_app()
    selected = compat.selected_nodes(app, compat.focused_group(app))
    if not selected:
        compat.information("Node info", "Select a node first.")
        return None
    text = describe(selected[0], app)
    compat.information("Node info", text)
    return text


def describe(node: Any, app: Any) -> str:
    lines = [f"{node.getScriptName()} ({node.getLabel()})", f"Plug-in: {node.getPluginID()}"]
    inputs = []
    for number in range(node.getMaxInputCount()):
        source = node.getInput(number)
        if source is not None:
            inputs.append(f"{node.getInputLabel(number)} <- {source.getScriptName()}")
    lines.append("Inputs: " + (", ".join(inputs) if inputs else "none connected"))
    try:
        frame = app.timelineGetTime()
        box = node.getRegionOfDefinition(frame, 0)
        lines.append(f"Bounding box at frame {frame}: {box.x1:g} {box.y1:g} {box.x2:g} {box.y2:g}")
    except Exception:  # noqa: BLE001
        pass
    try:
        lines.append(f"Frame rate: {node.getFrameRate():g}; pixel aspect: {node.getPixelAspectRatio():g}")
        lines.append(f"Premultiplication: {node.getPremult()}; bit depth: {node.getBitDepth()}")
    except Exception:  # noqa: BLE001
        pass
    return "\n".join(lines)


# The nodes the last snap moved and where they were, for Nuke > Edit > Undo snap to grid (Natron's Python moves a
# node with no Undo of its own).
_last_snap: list[tuple[Any, float, float]] = []


def snap_to_grid() -> int | None:
    """\\: every node of the node graph the artist is in (the comp's, or a Group's) moved to the nearest point of
    Nuke's grid. Returns how many moved; Nuke > Edit > Undo snap to grid puts them back."""
    if not _node_graph_only("\\"):
        return None
    app = compat.active_app()
    moved = snap_nodes(compat.children(compat.focused_group(app)))
    if moved:
        compat.say(f"{moved} node(s) snapped to the grid: Nuke > Edit > Undo snap to grid puts them back.")
    return moved


def snap_nodes(nodes: list[Any], grid: tuple[int, int] = GRID) -> int:
    """Each node to the nearest grid point, unless another node is already there (or gets there first): then it
    stays where it was, so two nodes never land on top of each other. Remembers what moved for ``undo_snap``."""
    placed = []
    for node in nodes:
        try:
            x, y = node.getPosition()
        except Exception:  # noqa: BLE001
            continue
        placed.append((node, x, y, (round(x / grid[0]) * grid[0], round(y / grid[1]) * grid[1])))
    taken = {(x, y) for _node, x, y, _snapped in placed}
    moved: list[tuple[Any, float, float]] = []
    for node, x, y, snapped in placed:
        if snapped == (x, y) or snapped in taken:
            continue
        node.setPosition(*snapped)
        taken.discard((x, y))
        taken.add(snapped)
        moved.append((node, x, y))
    _last_snap[:] = moved
    return len(moved)


def undo_snap() -> int:
    """Nuke > Edit > Undo snap to grid: the nodes the last snap moved, back where they were (one deleted since is
    skipped). Returns how many went back."""
    back = 0
    for node, x, y in _last_snap:
        try:
            node.setPosition(x, y)
            back += 1
        except Exception:  # noqa: BLE001  (a node deleted since: Natron raises RuntimeError)
            continue
    _last_snap.clear()
    if compat.application() is not None:
        compat.say(f"Undo snap to grid: {back} node(s) back where they were." if back
                   else "Undo snap to grid: nothing to put back.")
    return back


def connect_to_first() -> bool | None:
    """Shift+Y: with two nodes selected, the second's main input is fed by the first (Natron's selection order)."""
    if not _node_graph_only("Shift+Y"):
        return None
    app = compat.active_app()
    selected = compat.selected_nodes(app, compat.focused_group(app))
    if len(selected) != 2:
        compat.information("Connect second selected to first", "Select exactly two nodes.")
        return False
    first, second = selected
    return compat.connect(second, 0, first)


def flipbook_selected() -> Any:
    """Alt+F: Nuke's flipbook of the selected node, rendered by NatronRenderer in the background and played in RV
    when it's on this PC, else as a movie in the system's player (``workflow.flipbook``)."""
    if not _node_graph_only("Alt+F"):
        return None
    from . import workflow  # noqa: PLC0415

    return workflow.flipbook_selected()


def duplicate_and_branch() -> Any:
    """Alt+B: a copy of the selected node, fed by the same input, beside it (a new branch)."""
    if not _node_graph_only("Alt+B"):
        return None
    app = compat.active_app()
    group = compat.focused_group(app)
    selected = compat.selected_nodes(app, group)
    if len(selected) != 1:
        compat.information("Duplicate and branch", "Select one node.")
        return None
    return branch_copy(app, selected[0], group)


def branch_copy(app: Any, node: Any, group: Any = None) -> Any:
    """A new node of the same plug-in with the same values, its inputs fed like the original's, beside it in the same
    node graph (``group``: the comp's top level by default)."""
    copy = compat.create_node(app, node.getPluginID(), group)
    if copy is None:
        return None
    for param in node.getParams():
        name = param.getScriptName()
        if name in ("onParamChanged", "onInputChanged", "userTextArea") or not param.getIsPersistent():
            continue
        target = copy.getParam(name)
        if target is None:
            continue
        try:
            target.copy(param)
        except Exception:  # noqa: BLE001
            continue
    for number in range(node.getMaxInputCount()):
        source = node.getInput(number)
        if source is not None:
            compat.connect(copy, number, source)
    try:
        x, y = node.getPosition()
        copy.setPosition(x + 140, y)
    except Exception:  # noqa: BLE001
        pass
    compat.select_only(app, copy)
    return copy


# --- The artist's own Nuke shortcuts (after an import) ---


def make_creator(plugin_id: str, alias: str | None, shortcut: str) -> Any:
    def create() -> Any:
        if not _node_graph_only(shortcut):
            return None
        app = compat.active_app()
        group = compat.focused_group(app)
        if alias:
            return aliases.make(alias, app, group)
        selected = compat.selected_nodes(app, group)
        node = compat.create_node(app, plugin_id, group)
        if node is not None and len(selected) == 1:
            compat.connect(node, 0, selected[0])
        return node

    return create


def register_imported(shortcuts: list[dict[str, Any]]) -> list[str]:
    """Menu commands (Nuke/My Nuke shortcuts/<node>) for the shortcuts imported from the artist's menu.py."""
    done = []
    for number, entry in enumerate(shortcuts):
        plugin_id, keys, label = entry.get("plugin", ""), entry.get("keys", ""), entry.get("label", "")
        alias = entry.get("alias") or None
        if not keys or not label or not (alias or compat.has_plugin(plugin_id)):
            continue
        name = f"imported_{number}"
        globals()[name] = make_creator(plugin_id, alias, keys)
        if compat.add_menu_command(f"Nuke/My Nuke shortcuts/{label}", f"natron_layer.hotkeys.{name}", keys):
            done.append(f"{keys} {label}")
    return done


UNDO_SNAP_MENU = "Nuke/Edit/Undo snap to grid"


def register() -> list[str]:
    """The layer's own keys (status "added"), as menu commands, and Undo snap to grid (no key). Interface only."""
    compat.add_menu_command(UNDO_SNAP_MENU, "natron_layer.hotkeys.undo_snap")
    done = []
    for key in added():
        if key.command and key.menu and compat.add_menu_command(key.menu, f"natron_layer.hotkeys.{key.command}",
                                                                 key.keys):
            done.append(key.keys)
            _registered.append(key.menu)
    return done
