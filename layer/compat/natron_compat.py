# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The one place where the layer talks to Natron and to Qt.

Everything else in the layer calls these functions, never NatronEngine, NatronGui or a Qt binding directly, so that
when the fork changes its Python API (it moved to Qt 6 and Python 3.14 in 2026) the fix is made here once.

Rules this module keeps:

- Qt comes through ``qtpy`` (the fork bundles qtpy 2.4 on PySide6), else PySide6 directly.
- Features are checked, not versions: ``has_plugin()`` looks at ``getPluginIDs()``; ``version()`` is only reported.
- Nothing here writes Natron's preferences except ``SettingsWriter``, which the layer only uses after the artist
  said yes (the Nuke preferences import, the look's reset).
- It imports with or without Natron, so the parts of the layer that don't need Natron (the Nuke preferences reader)
  can be tested with any Python 3.10+.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Iterator, Mapping
from typing import Any

# Natron keeps its settings with QSettings under these names (the registry key HKCU\Software\INRIA\Natron on
# Windows, ~/.config/INRIA/Natron.conf on Linux). Read in Engine/Settings.cpp and Gui/GuiApplicationManager*.cpp.
ORGANISATION = "INRIA"
APPLICATION = "Natron"

# The hidden setting Natron's own --setting option turns off so that a value set for one process is never written.
SAVE_SETTINGS = "saveSettings"

_plugin_ids: frozenset[str] | None = None


# --- Natron itself ---


def engine() -> Any:
    """The NatronEngine module (ImportError outside Natron)."""
    import NatronEngine  # noqa: PLC0415  (only inside Natron)

    return NatronEngine


def natron() -> Any:
    """Natron's application object (``natron`` in Natron's own scripts)."""
    return engine().natron


def gui_natron() -> Any:
    """Natron's application object with its interface functions (NatronGui's ``natron``: addMenuCommand, dialogs),
    or None headless. NatronEngine's ``natron`` lacks them even in the interface."""
    try:
        import NatronGui  # noqa: PLC0415  (only in Natron's interface)
    except ImportError:
        return None
    return NatronGui.natron


def in_natron() -> bool:
    try:
        engine()
    except ImportError:
        return False
    return True


def is_background() -> bool:
    """True in NatronRenderer and in ``Natron -t`` (no interface)."""
    return bool(natron().isBackground())


def version() -> tuple[int, int, int]:
    n = natron()
    return (n.getNatronVersionMajor(), n.getNatronVersionMinor(), n.getNatronVersionRevision())


def version_encoded() -> int:
    return int(natron().getNatronVersionEncoded())


def plugin_ids(refresh: bool = False) -> frozenset[str]:
    """Every plug-in this Natron registered (OpenFX, built-in, PyPlugs)."""
    global _plugin_ids  # noqa: PLW0603
    if _plugin_ids is None or refresh:
        _plugin_ids = frozenset(str(i) for i in natron().getPluginIDs())
    return _plugin_ids


def has_plugin(plugin_id: str) -> bool:
    return plugin_id in plugin_ids()


def has_3d() -> bool:
    """The fork's 3D workspace (stock Natron 2.5 has none)."""
    return has_plugin("fr.inria.built-in.Scene3D")


def plugin_paths() -> list[str]:
    """The folders Natron looks in for PyPlugs and startup scripts, in its order."""
    return [str(p) for p in natron().getNatronPath()]


def app_folder() -> str | None:
    """The Natron release folder (the one holding bin/ and Plugins/), from the bundled PyPlugs folder."""
    for folder in plugin_paths():
        normalised = os.path.normpath(folder)
        if normalised.replace("\\", "/").endswith("/Plugins/PyPlugs"):
            return os.path.dirname(os.path.dirname(normalised))
    return None


# --- Preferences (Natron's settings) ---


def setting(name: str) -> Any:
    """A preference by its script name (``stylesheetFile``, ``readerColor``…), or None when this Natron lacks it."""
    try:
        return natron().getSettings().getParam(name)
    except Exception:  # noqa: BLE001  (a Natron without it)
        return None


def setting_value(name: str) -> Any:
    """A preference's current value: bool, int, float, str, a choice's option id, or a tuple for colours."""
    param = setting(name)
    if param is None:
        return None
    return param_value(param)


def param_value(param: Any) -> Any:
    kind = type(param).__name__
    if kind == "ChoiceParam":
        options = list(param.getOptions())
        index = int(param.get())
        return options[index] if 0 <= index < len(options) else index
    if kind == "ColorParam" or param.getNumDimensions() > 1:
        return tuple(float(param.getValue(d)) for d in range(param.getNumDimensions()))
    value = param.get()
    return value


def set_param_value(param: Any, value: Any) -> bool:
    """Set a parameter from a plain value: a choice by its option id (or index), a colour or 2D/3D value from a
    tuple, anything else as it is. Returns False when the value doesn't fit."""
    kind = type(param).__name__
    try:
        if kind == "ChoiceParam":
            if isinstance(value, str):
                options = list(param.getOptions())
                if value not in options:
                    return False
                param.setValue(options.index(value))
            else:
                param.setValue(int(value))
            return True
        if isinstance(value, (tuple, list)):
            dims = param.getNumDimensions()
            values = list(value)[:dims]
            if len(values) < dims:
                if kind != "ColorParam" or len(values) != 3:
                    return False
            for dim, v in enumerate(values):
                param.setValue(float(v) if not isinstance(v, bool) else v, dim)
            return True
        if kind == "BooleanParam":
            param.setValue(bool(value))
        elif kind == "IntParam":
            param.setValue(int(value))
        elif kind == "DoubleParam":
            param.setValue(float(value))
        else:
            param.setValue(value)
    except Exception:  # noqa: BLE001
        return False
    return True


def stored_keys(name: str, param: Any = None) -> list[str]:
    """The key(s) Natron stores a preference under: its script name, or ``name.r``/``name.g``… per dimension
    (Settings::saveSettings writes ``<name>.<dimension name>`` for parameters with several dimensions; colours'
    dimensions are r, g, b, a, the others' x, y, z, w)."""
    param = param if param is not None else setting(name)
    if param is None:
        return [name]
    dims = param.getNumDimensions()
    if dims <= 1:
        return [name]
    letters = "rgba" if type(param).__name__ == "ColorParam" else "xyzw"
    return [f"{name}.{letters[d]}" for d in range(dims)]


@contextlib.contextmanager
def unsaved() -> Iterator[None]:
    """Changes made inside are never written to the artist's preferences, then saving comes back as it was.

    Natron writes preferences only from its Preferences window (the ones changed while it was open), from
    ``AppSettings.saveSettings()`` and for a few flags of its own; setting a value from Python doesn't write it
    (checked on the fork). Turning the hidden "Save settings on change" off while the layer sets its look is the
    belt to those braces, the way Natron's own --setting option does it.
    """
    save = setting(SAVE_SETTINGS)
    before = bool(save.get()) if save is not None else None
    if save is not None and before:
        save.setValue(False)
    try:
        yield
    finally:
        if save is not None and before:
            save.setValue(True)


class StoredSettings(Mapping[str, Any]):
    """What the artist's Natron preferences hold, read only (a QSettings, or a plain dict in tests).

    Natron stores a preference only once someone changed it in its Preferences window (or a script saved it), so a
    key found here is the artist's own choice and the layer leaves it alone.
    """

    def __init__(self, source: Any = None) -> None:
        self._source = source

    @classmethod
    def of_natron(cls) -> StoredSettings:
        qt = qt_modules()
        if qt is None:
            return cls({})
        return cls(qt.QtCore.QSettings(ORGANISATION, APPLICATION))

    def contains(self, key: str) -> bool:
        if isinstance(self._source, dict):
            return key in self._source
        return bool(self._source.contains(key))

    def __getitem__(self, key: str) -> Any:
        if not self.contains(key):
            raise KeyError(key)
        if isinstance(self._source, dict):
            return self._source[key]
        return self._source.value(key)

    def __iter__(self) -> Iterator[str]:
        if isinstance(self._source, dict):
            return iter(self._source)
        return iter(self._source.allKeys())

    def __len__(self) -> int:
        return len(list(iter(self)))


class SettingsWriter:
    """Writes values in Natron's own format, for the moments the artist asked for it (never by itself).

    ``target`` is a QSettings (Natron's own, or an .ini file in tests) or a dict. Values are written with the types
    Natron writes them with (Settings::saveSettings): bools and ints as they are, doubles as doubles, choices by
    their option id, one key per dimension.
    """

    def __init__(self, target: Any) -> None:
        self.target = target
        self.written: list[str] = []
        self.removed: list[str] = []

    @classmethod
    def of_natron(cls) -> SettingsWriter:
        qt = qt_modules()
        if qt is None:
            raise RuntimeError("Qt isn't available to write Natron's preferences.")
        return cls(qt.QtCore.QSettings(ORGANISATION, APPLICATION))

    @classmethod
    def ini_file(cls, path: str) -> SettingsWriter:
        qt = qt_modules()
        if qt is None:
            raise RuntimeError("Qt isn't available to write a settings file.")
        return cls(qt.QtCore.QSettings(path, qt.QtCore.QSettings.Format.IniFormat))

    def set(self, key: str, value: Any) -> None:
        if isinstance(self.target, dict):
            self.target[key] = value
        else:
            self.target.setValue(key, value)
        self.written.append(key)

    def remove(self, key: str) -> None:
        if isinstance(self.target, dict):
            self.target.pop(key, None)
        else:
            self.target.remove(key)
        self.removed.append(key)

    def sync(self) -> None:
        if not isinstance(self.target, dict):
            self.target.sync()


# --- Qt ---


class _Qt:
    def __init__(self, core: Any, gui: Any, widgets: Any) -> None:
        self.QtCore, self.QtGui, self.QtWidgets = core, gui, widgets


def qt_modules() -> _Qt | None:
    """QtCore, QtGui and QtWidgets through qtpy (else PySide6); None when Qt can't be imported. Headless, QtGui and
    QtWidgets may be None."""
    for loader in (_from_qtpy, _from_pyside6):
        found = loader()
        if found is not None:
            return found
    return None


def _from_qtpy() -> _Qt | None:
    try:
        from qtpy import QtCore  # noqa: PLC0415
    except Exception:  # noqa: BLE001
        return None
    gui = widgets = None
    with contextlib.suppress(Exception):
        from qtpy import QtGui, QtWidgets  # noqa: PLC0415

        gui, widgets = QtGui, QtWidgets
    return _Qt(QtCore, gui, widgets)


def _from_pyside6() -> _Qt | None:
    try:
        from PySide6 import QtCore  # noqa: PLC0415
    except Exception:  # noqa: BLE001
        return None
    gui = widgets = None
    with contextlib.suppress(Exception):
        from PySide6 import QtGui, QtWidgets  # noqa: PLC0415

        gui, widgets = QtGui, QtWidgets
    return _Qt(QtCore, gui, widgets)


def application() -> Any:
    """The running QApplication (with widgets), or None: headless, Natron runs a QCoreApplication."""
    qt = qt_modules()
    if qt is None or qt.QtWidgets is None:
        return None
    instance = qt.QtCore.QCoreApplication.instance()
    return instance if isinstance(instance, qt.QtWidgets.QApplication) else None


def say(text: str) -> None:
    """Print to Natron's console (headless) or its Script Editor (Natron's window catches Python's output with an
    object that has no flush), whatever the console's encoding."""
    import sys  # noqa: PLC0415

    try:
        print(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        print(text.encode(encoding, "replace").decode(encoding))
    flush = getattr(sys.stdout, "flush", None)
    if callable(flush):
        flush()


def key_and_modifiers(shortcut: str) -> tuple[Any, Any] | None:
    """``"Alt+B"`` → (Qt.Key.Key_B, Qt.KeyboardModifier.AltModifier), as addMenuCommand takes them."""
    qt = qt_modules()
    if qt is None:
        return None
    sequence = qt.QtGui.QKeySequence(shortcut) if qt.QtGui is not None else None
    if sequence is None or sequence.count() == 0:
        return None
    combination = sequence[0]
    key = combination.key()
    modifiers = combination.keyboardModifiers()
    return key, modifiers


# --- Nodes and the node graph ---


def create_node(app: Any, plugin_id: str, group: Any = None) -> Any:
    """A new node of ``plugin_id`` in ``group`` (the project's top level when None). Toolset PyPlugs make nodes of
    their own and give None."""
    if group is None or isinstance(group, str):
        return app.createNode(plugin_id)
    return app.createNode(plugin_id, -1, group)


def node_param(node: Any, name: str) -> Any:
    return node.getParam(name)


def set_node_value(node: Any, name: str, value: Any) -> bool:
    param = node.getParam(name)
    if param is None:
        return False
    return set_param_value(param, value)


def connect(node: Any, number: int, source: Any) -> bool:
    """Connect ``source`` to ``node``'s input ``number``, replacing what was there (Natron's connectInput never
    replaces a connection)."""
    if node.getInput(number) is not None:
        node.disconnectInput(number)
    return bool(node.connectInput(number, source))


def children(app_or_group: Any) -> list[Any]:
    return list(app_or_group.getChildren())


def unique_name(app: Any, base: str) -> str:
    """``Copy1``, ``Copy2``…: the first script name no top-level node has."""
    taken = {node.getScriptName() for node in children(app)}
    number = 1
    while f"{base}{number}" in taken:
        number += 1
    return f"{base}{number}"


def gui_app(app: Any) -> Any:
    """The app when it has an interface (NatronGui's GuiApp), else None."""
    return app if hasattr(app, "getSelectedNodes") else None


def selected_nodes(app: Any) -> list[Any]:
    gui = gui_app(app)
    if gui is None:
        return []
    try:
        return list(gui.getSelectedNodes())
    except Exception:  # noqa: BLE001
        return []


def select_only(app: Any, node: Any) -> None:
    gui = gui_app(app)
    if gui is None:
        return
    with contextlib.suppress(Exception):
        gui.clearSelection()
        gui.selectNode(node, False)


def active_app() -> Any:
    """The project's app: in Natron's window its GuiApp (selection, copy and paste, dialogs), else NatronEngine's
    App. NatronEngine's getActiveInstance gives the engine's App even in the window, without those."""
    app = natron().getActiveInstance()
    gui = gui_natron()
    if gui is not None and app is not None and hasattr(gui, "getGuiInstance"):
        with contextlib.suppress(Exception):
            found = gui.getGuiInstance(app.getAppID())
            if found is not None:
                return found
    return app


def add_menu_command(grouping: str, function: str, shortcut: str | None = None) -> bool:
    """A menu bar entry (``Nuke/Insert Copy node``) running ``function`` (a dotted name Natron looks up in its main
    namespace), with a default shortcut the artist can change in Natron's shortcut editor. Interface only: Natron
    takes menu entries only from initGui.py."""
    n = gui_natron()
    if n is None or not hasattr(n, "addMenuCommand"):
        return False
    if shortcut:
        found = key_and_modifiers(shortcut)
        if found is not None:
            key, modifiers = found
            n.addMenuCommand(grouping, function, key, modifiers)
            return True
    n.addMenuCommand(grouping, function)
    return True


def information(title: str, message: str) -> None:
    n = gui_natron()
    if n is not None and hasattr(n, "informationDialog") and not is_background():
        n.informationDialog(title, message)
    else:
        say(f"{title}: {message}")


def warning(title: str, message: str) -> None:
    n = gui_natron()
    if n is not None and hasattr(n, "warningDialog") and not is_background():
        n.warningDialog(title, message)
    else:
        say(f"{title}: {message}")


def refresh_setting(name: str) -> bool:
    """Set a preference to its own value again, so Natron acts on it now (reloading the stylesheet, say): Natron
    loads its stylesheet before any startup script runs and reloads it only when the setting changes while its
    window exists. Nothing is saved."""
    param = setting(name)
    if param is None:
        return False
    value = param.get()
    with unsaved():
        param.setValue("" if isinstance(value, str) else value)
        param.setValue(value)
    return True


def write_to_script_editor(app: Any, message: str) -> None:
    with contextlib.suppress(Exception):
        app.writeToScriptEditor(message)


# --- Groups and their parameters (the gizmos) ---


def child_by_plugin(group: Any, plugin_id: str) -> Any:
    """The first node of ``plugin_id`` inside ``group`` (a Group's own Input1 or Output1), or None."""
    for node in children(group):
        if node.getPluginID() == plugin_id:
            return node
    return None


def child_by_name(group: Any, script_name: str) -> Any:
    for node in children(group):
        if node.getScriptName() == script_name:
            return node
    return None


_PARAM_MAKERS = {
    "page": "createPageParam",
    "double": "createDoubleParam",
    "int": "createIntParam",
    "bool": "createBooleanParam",
    "choice": "createChoiceParam",
    "string": "createStringParam",
    "button": "createButtonParam",
    "double2d": "createDouble2DParam",
}


def add_user_param(node: Any, kind: str, name: str, label: str, alpha: bool = False) -> Any:
    """A parameter of the artist's kind on ``node`` (a Group's controls): ``page``, ``double``, ``int``, ``bool``,
    ``choice``, ``string``, ``button``, ``double2d`` or ``color`` (``alpha`` for a fourth channel)."""
    if kind == "color":
        return node.createColorParam(name, label, alpha)
    return getattr(node, _PARAM_MAKERS[kind])(name, label)


def refresh_user_params(node: Any, pages: list[str] | None = None) -> None:
    with contextlib.suppress(Exception):
        if pages:
            node.setPagesOrder(pages)
        node.refreshUserParamsGUI()


def set_expression(param: Any, expression: str, dimension: int = 0, has_return: bool = False) -> bool:
    """A Python expression on one dimension of ``param`` (Natron's expressions: ``thisGroup``, ``thisNode``,
    ``frame``…). An empty expression clears it."""
    return bool(param.setExpression(expression, has_return, dimension))


def expression_of(param: Any, dimension: int = 0) -> str:
    try:
        found = param.getExpression(dimension)
    except Exception:  # noqa: BLE001
        return ""
    if isinstance(found, (tuple, list)):  # (expression, has_return) on some bindings
        found = found[0] if found else ""
    return str(found or "")


def make_alias(param: Any, target: Any) -> bool:
    """``param`` (on a Group) shows and drives ``target`` (a parameter of a node inside it)."""
    return bool(param.setAsAlias(target))


# --- The interface's clipboard and copy-paste of nodes (ToolSets) ---


def _board() -> Any:
    qt = qt_modules()
    if qt is None or qt.QtGui is None or application() is None:
        return None
    return qt.QtGui.QGuiApplication.clipboard()


@contextlib.contextmanager
def kept_clipboard() -> Iterator[None]:
    """The system clipboard's text, or its picture, is put back afterwards (pasting a ToolSet goes through the
    clipboard: Natron's paste reads it). Qt's own setText and setImage are used, so the clipboard's data stays Qt's
    (no QMimeData made in Python whose lifetime PySide6 would have to hand over)."""
    board = _board()
    text = image = None
    if board is not None:
        data = board.mimeData()
        if data is not None and data.hasText():
            text = board.text()
        elif data is not None and data.hasImage():
            image = board.image().copy()
    try:
        yield
    finally:
        if board is not None:
            if text is not None:
                set_clipboard_text(text)
            elif image is not None:
                board.setImage(image)
            else:
                board.clear()
            flush_clipboard()


def flush_clipboard() -> None:
    """Hand the clipboard's content to Windows for good (OleFlushClipboard), so it stays when Natron ends, even
    abruptly (Qt does it only at a normal exit)."""
    if os.name != "nt":
        return
    with contextlib.suppress(Exception):
        import ctypes  # noqa: PLC0415

        ctypes.windll.ole32.OleFlushClipboard()


def clipboard_text() -> str:
    board = _board()
    if board is None:
        return ""
    # Once Windows holds the text (after a flush) it can come back with Windows line ends.
    return str(board.text()).rstrip("\x00").replace("\r\n", "\n")


def set_clipboard_text(text: str, tries: int = 40) -> bool:
    """Natron's own copy puts its nodes on the clipboard as ``text/plain`` (Gui/NodeGraph40.cpp), its paste reads
    them from there; Qt's setText offers exactly that. Windows lets one program at a time open the clipboard, and
    programs watching it (clipboard history…) open it right after each change, so a set can fail: it's tried again
    until the text reads back. Returns whether it did."""
    import time  # noqa: PLC0415

    board = _board()
    if board is None:
        return False
    wanted = text.replace("\r\n", "\n")
    for _ in range(tries):
        board.setText(text)
        application().processEvents()
        if clipboard_text() == wanted:
            return True
        time.sleep(0.05)
    return False


def copy_selected_nodes(app: Any) -> bool:
    """Natron's own Copy of the comp's selected nodes (interface only)."""
    gui = gui_app(app)
    if gui is None:
        return False
    gui.copySelectedNodes(gui)
    return True


def paste_nodes(app: Any) -> bool:
    """Natron's own paste, from the clipboard, into the comp's main node graph (interface only, once Natron's window
    is up: a paste before its node graph exists ended Natron, checked on the fork). The app is passed as the group:
    without one Natron pastes into the node graph last focused (a Group's, maybe); with the app, the comp's top
    level, it takes the main node graph."""
    gui = gui_app(app)
    if gui is None:
        return False
    gui.pasteNodes(gui)
    return True


def select_nodes(app: Any, nodes: list[Any]) -> None:
    """Exactly ``nodes`` selected in the node graph (GuiApp.selectNode's flag clears the previous selection, so
    Natron's setSelection is used)."""
    gui = gui_app(app)
    if gui is None:
        return
    with contextlib.suppress(Exception):
        gui.clearSelection()
        if hasattr(gui, "setSelection"):
            gui.setSelection(list(nodes))
        else:
            for node in nodes:
                gui.selectNode(node, False)


# --- The project ---


def project_param(app: Any, name: str) -> Any:
    """A project setting by its script name (``frameRange``, ``projectPaths``, ``projectName``…)."""
    try:
        return app.getProjectParam(name)
    except Exception:  # noqa: BLE001
        return None


def project_frame_range(app: Any) -> tuple[int, int]:
    found = project_param(app, "frameRange")
    if found is None:
        return (1, 1)
    return (int(found.getValue(0)), int(found.getValue(1)))


def project_file(app: Any) -> str:
    """The project's file (folder from its Project path, name from its settings), or "" when it was never saved."""
    name = project_param(app, "projectName")
    paths = project_param(app, "projectPaths")
    name = str(name.get()) if name is not None else ""
    folder = project_variable(str(paths.get()) if paths is not None else "", "Project")
    if not name or not folder or name.lower().startswith("untitled"):
        return ""
    return os.path.join(folder, name).replace("\\", "/")


def project_variable(paths_value: str, variable: str) -> str:
    """A variable of the project's paths (``<Name>Project</Name><Value>C:/...</Value>...``, Natron's format)."""
    import re  # noqa: PLC0415

    for name, value in re.findall(r"<Name>(.*?)</Name><Value>(.*?)</Value>", paths_value, flags=re.S):
        if name == variable:
            return value
    return ""


def save_temp_project(app: Any, path: str) -> bool:
    """A copy of the open project at ``path``; the open project, its file and its name are left as they are."""
    return bool(app.saveTempProject(path.replace("\\", "/")))


def renderer_executable() -> str | None:
    """NatronRenderer next to the running Natron (its bin folder), or None."""
    folder = app_folder()
    candidates = []
    if folder:
        candidates.append(os.path.join(folder, "bin"))
    qt = qt_modules()
    if qt is not None:
        with contextlib.suppress(Exception):
            candidates.append(str(qt.QtCore.QCoreApplication.applicationDirPath()))
    for base in candidates:
        for name in ("NatronRenderer.exe", "NatronRenderer"):
            path = os.path.join(base, name)
            if os.path.isfile(path):
                return path
    return None


def open_with_system(path: str) -> bool:
    """Open a file or a folder with the system's own program for it (Explorer, the default video player)."""
    import subprocess  # noqa: PLC0415
    import sys  # noqa: PLC0415

    try:
        if os.name == "nt":
            os.startfile(path)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])  # noqa: S603,S607
        else:
            subprocess.Popen(["xdg-open", path])  # noqa: S603,S607
    except OSError:
        return False
    return True
