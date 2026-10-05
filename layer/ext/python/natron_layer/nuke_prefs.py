# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Reading an artist's own Nuke preferences and translating what maps to Natron.

Nuke keeps its preferences in ``~/.nuke/preferences<version>.nk`` (Nuke's script format: a ``Preferences { … }``
node whose knobs are written one per line, ``name value``) and an artist's own shortcuts in ``~/.nuke/menu.py``
(Python calling ``nuke.menu(...).addCommand(name, command, shortcut)``). This module reads both **without running
anything** (menu.py is parsed with Python's ``ast``, never executed) and **writes nothing in the .nuke folder**.

What it makes of them (``translate``) is a plan: Natron preferences to use instead of the Nuke look, node shortcuts
to add as menu commands, and a note for everything it couldn't use and why. The layer keeps the plan in its own
config file (``user_config``) after the artist's yes and applies it at every start like the look itself: for the
session, never over a preference the artist set in Natron. Natron's own settings are not written.

**Not yet checked against a real Nuke preferences file**: Nuke isn't installed on the PC this was written on, so the
knob names below come from Nuke's documented Preferences labels and common usage, and the tests use hand-written
files. The report lists every knob it read and didn't use, so the first real file shows what to add.

Pure Python (3.10+), no Natron needed: ``layer/tests/smoke/test_nuke_prefs.py`` runs it with any Python.
"""

from __future__ import annotations

import ast
import dataclasses
import os
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

# --- Nuke's node classes → Natron (a plug-in id, or one of the layer's aliases) ---

NUKE_NODES: dict[str, tuple[str, str]] = {
    # Nuke class: (Natron plug-in id, alias name or "")
    "Blur": ("net.sf.cimg.CImgBlur", ""),
    "ColorCorrect": ("net.sf.openfx.ColorCorrectPlugin", ""),
    "Grade": ("net.sf.openfx.GradePlugin", ""),
    "Merge": ("net.sf.openfx.MergePlugin", ""),
    "Merge2": ("net.sf.openfx.MergePlugin", ""),
    "Transform": ("net.sf.openfx.TransformPlugin", ""),
    "Roto": ("fr.inria.built-in.Roto", ""),
    "RotoPaint": ("fr.inria.built-in.RotoPaint", ""),
    "Dot": ("fr.inria.built-in.Dot", ""),
    "Read": ("fr.inria.built-in.Read", ""),
    "Write": ("fr.inria.built-in.Write", ""),
    "Crop": ("net.sf.openfx.CropPlugin", ""),
    "Reformat": ("net.sf.openfx.Reformat", ""),
    "Shuffle": ("net.sf.openfx.ShufflePlugin", ""),
    "Shuffle2": ("net.sf.openfx.ShufflePlugin", ""),
    "Premult": ("net.sf.openfx.Premult", ""),
    "Unpremult": ("net.sf.openfx.Unpremult", ""),
    "Constant": ("net.sf.openfx.ConstantPlugin", ""),
    "CheckerBoard": ("net.sf.openfx.CheckerBoardPlugin", ""),
    "CheckerBoard2": ("net.sf.openfx.CheckerBoardPlugin", ""),
    "ColorBars": ("net.sf.openfx.ColorBars", ""),
    "Keyer": ("net.sf.openfx.KeyerPlugin", ""),
    "HueCorrect": ("net.sf.openfx.HueCorrect", ""),
    "HueKeyer": ("net.sf.openfx.HueKeyer", ""),
    "Saturation": ("net.sf.openfx.SaturationPlugin", ""),
    "Clamp": ("net.sf.openfx.Clamp", ""),
    "Invert": ("net.sf.openfx.Invert", ""),
    "Multiply": ("net.sf.openfx.MultiplyPlugin", ""),
    "Add": ("net.sf.openfx.AddPlugin", ""),
    "Gamma": ("net.sf.openfx.GammaPlugin", ""),
    "ColorLookup": ("net.sf.openfx.ColorLookupPlugin", ""),
    "Sharpen": ("net.sf.cimg.CImgSharpen", ""),
    "Median": ("net.sf.cimg.CImgMedian", ""),
    "Erode": ("net.sf.cimg.CImgErode", ""),
    "Dilate": ("net.sf.cimg.CImgDilate", ""),
    "Noise": ("net.sf.cimg.CImgNoise", ""),
    "FrameHold": ("net.sf.openfx.FrameHold", ""),
    "TimeOffset": ("net.sf.openfx.timeOffset", ""),
    "FrameRange": ("net.sf.openfx.FrameRange", ""),
    "Retime": ("net.sf.openfx.Retime", ""),
    "AppendClip": ("net.sf.openfx.AppendClip", ""),
    "Switch": ("net.sf.openfx.switchPlugin", ""),
    "Dissolve": ("net.sf.openfx.DissolvePlugin", ""),
    "Keymix": ("net.sf.openfx.KeyMix", ""),
    "NoOp": ("net.sf.openfx.NoOpPlugin", ""),
    "BackdropNode": ("fr.inria.built-in.BackDrop", ""),
    "Group": ("fr.inria.built-in.Group", ""),
    "Camera": ("fr.inria.built-in.Camera3D", ""),
    "Camera2": ("fr.inria.built-in.Camera3D", ""),
    "Camera3": ("fr.inria.built-in.Camera3D", ""),
    "Card": ("fr.inria.built-in.Card3D", ""),
    "Card2": ("fr.inria.built-in.Card3D", ""),
    "Scene": ("fr.inria.built-in.Scene3D", ""),
    "ScanlineRender": ("fr.inria.built-in.ScanlineRender", ""),
    "ReadGeo": ("fr.inria.built-in.ReadGeo", ""),
    "ReadGeo2": ("fr.inria.built-in.ReadGeo", ""),
    "Project3D": ("fr.inria.built-in.Project3D", ""),
    "Project3D2": ("fr.inria.built-in.Project3D", ""),
    "LensDistortion": ("net.sf.openfx.LensDistortion", ""),
    "LensDistortion2": ("net.sf.openfx.LensDistortion", ""),
    "STMap": ("net.sf.openfx.STMap", ""),
    "IDistort": ("net.sf.openfx.IDistort", ""),
    "Tracker": ("fr.inria.built-in.Tracker", ""),
    "Tracker4": ("fr.inria.built-in.Tracker", ""),
    "VectorBlur": ("fr.inria.built-in.VectorBlur", ""),
    "VectorBlur2": ("fr.inria.built-in.VectorBlur", ""),
    "Exposure": ("fr.inria.built-in.Exposure", ""),
    "ContactSheet": ("net.sf.openfx.ContactSheetOFX", ""),
    "LayerContactSheet": ("net.sf.openfx.LayerContactSheetOFX", ""),
    # The layer's aliases (ext/plugin/aliases): the Natron node set up the Nuke way.
    "Copy": ("net.sf.openfx.ShufflePlugin", "Copy"),
    "ShuffleCopy": ("net.sf.openfx.ShufflePlugin", "ShuffleCopy"),
    "ChannelMerge": ("net.sf.openfx.MergePlugin", "ChannelMerge"),
    "Keylight": ("net.sf.openfx.PIK", "Keylight"),
    "OFXuk.co.thefoundry.keylight.keylight_v201": ("net.sf.openfx.PIK", "Keylight"),
    "IBKGizmo": ("net.sf.openfx.PIK", "IBKGizmo"),
    "IBKGizmoV3": ("net.sf.openfx.PIK", "IBKGizmo"),
    "Glow": ("net.sf.cimg.CImgBloom", "Glow"),
    "Glow2": ("net.sf.cimg.CImgBloom", "Glow"),
    "Denoise2": ("net.sf.openfx.DenoiseSharpen", "Denoise"),
    "FilterErode": ("net.sf.cimg.CImgErode", "FilterErode"),
    "CornerPin2D": ("net.sf.openfx.CornerPinPlugin", "CornerPin2D"),
    "AdjustBBox": ("net.sf.openfx.AdjustRoDPlugin", "AdjustBBox"),
    "CurveTool": ("net.sf.openfx.ImageStatistics", "CurveTool"),
    "TimeClip": ("net.sf.openfx.FrameRange", "TimeClip"),
}

# Natron's own default keys where a node graph has the keyboard (Natron's node graph group, the ten plug-ins with a
# key, the player keys the node graph takes, the global ones), from the fork's source, and the layer's own.
NATRON_NODE_GRAPH_KEYS: dict[str, str] = {
    "R": "Read", "W": "Write", "T": "Transform", "O": "Roto", "P": "RotoPaint", "M": "Merge", "G": "Grade",
    "C": "ColorCorrect", "B": "Blur", ".": "Dot", "L": "rearrange nodes", "D": "disable nodes",
    "Backspace": "delete nodes", "Shift+E": "show expressions", "Up": "go upstream", "Down": "go downstream",
    "Shift+Up": "select upstream", "Shift+Down": "select downstream", "Ctrl+A": "select all",
    "Ctrl+Shift+A": "select all visible", "Shift+X": "switch inputs", "Ctrl+C": "copy", "Ctrl+V": "paste",
    "Ctrl+X": "cut", "Alt+K": "clone", "Alt+Shift+K": "declone", "Alt+C": "duplicate", "Shift+P": "force preview",
    "Alt+P": "postage stamps on or off", "F": "frame the nodes", "Ctrl+F": "find a node", "Tab": "Tab search",
    "N": "rename", "Ctrl+Shift+X": "extract", "Ctrl+G": "group", "Ctrl+Alt+G": "expand a group",
    "Return": "open the node's panel", "S": "project settings", "Shift+S": "preferences", "Alt+S": "full screen",
    "Ctrl+I": "new viewer", "Space": "maximise the panel", "F2": "render statistics", "F5": "render all",
    "F7": "render the selection", "Ctrl+T": "next tab", "Ctrl+Shift+T": "previous tab", "Ctrl+N": "new project",
    "Ctrl+O": "open a project", "Ctrl+S": "save", "Ctrl+Shift+S": "save as", "Ctrl+W": "close the project",
    "Ctrl+Q": "quit", "Ctrl+Shift+R": "reload the project", "Ctrl+Shift+K": "clear all caches",
    "Left": "previous frame", "Right": "next frame", "Shift+Left": "previous increment",
    "Shift+Right": "next increment", "Ctrl+Left": "first frame", "Ctrl+Right": "last frame",
    "Ctrl+Shift+Left": "previous keyframe", "Ctrl+Shift+Right": "next keyframe",
    **{str(n % 10): f"viewer input {n}" for n in range(1, 11)},
    **{f"Shift+{n % 10}": f"viewer B input {n}" for n in range(1, 11)},
    # the layer's own (ext/presets/nuke_hotkeys.toml)
    "K": "Copy (this build)", "I": "node info (this build)", "\\": "snap to grid (this build)",
    "Shift+Y": "connect second to first (this build)", "Alt+B": "duplicate and branch (this build)",
}  # fmt: skip

# Which node each of Natron's ten default node keys makes (to say "already Natron's").
NATRON_NODE_KEYS = {
    "B": "net.sf.cimg.CImgBlur", "C": "net.sf.openfx.ColorCorrectPlugin", "G": "net.sf.openfx.GradePlugin",
    "M": "net.sf.openfx.MergePlugin", "O": "fr.inria.built-in.Roto", "P": "fr.inria.built-in.RotoPaint",
    "R": "fr.inria.built-in.Read", "T": "net.sf.openfx.TransformPlugin", "W": "fr.inria.built-in.Write",
    ".": "fr.inria.built-in.Dot",
}  # fmt: skip


# --- Nuke preferences → Natron preferences ---


@dataclasses.dataclass(frozen=True)
class Preference:
    natron: str  # Natron's preference (script name)
    nuke: tuple[str, ...]  # the Nuke knob names it may be written under (compared without case or underscores)
    kind: str  # bool, int, float, colour
    label: str  # what it is, for the report
    scale: float = 1.0  # Nuke value × scale = Natron value (for ints and floats)


PREFERENCES: tuple[Preference, ...] = (
    Preference("maxPanels", ("maxPanels", "max_panels"), "int", "most properties panels open at once"),
    Preference("enableSnapToNode", ("SnapToNode", "snap_to_node"), "bool", "snap nodes to each other"),
    Preference("autoSaveDelay", ("AutoSaveTime", "autosave_time", "autoSaveIdle"), "int", "autosave delay (seconds)"),
    Preference("maxUndoRedo", ("UndoLevels", "undo_levels", "undoHistory"), "int", "undo steps in the node graph"),
    Preference("autoHideInputs", ("autoHideMaskInputs", "hide_mask_inputs"), "bool", "hide mask inputs"),
    Preference(
        "enableAutoPreviewNewProjects", ("postageStamps", "postage_stamp_mode"), "bool", "postage stamps on new nodes"
    ),
    Preference("maxRAMPercent", ("cacheMemory", "cache_memory_percent"), "int", "RAM used for caching (%)"),
    Preference("maxViewerDiskCache", ("diskCacheGB", "DiskCacheGB"), "int", "playback disk cache (GB)"),
)

# Knobs read but deliberately not applied, with why (said in the report).
NOT_APPLIED: dict[str, str] = {
    "uifontsize": "Natron reads its font before any script runs: set Preferences › Appearance › Font size yourself",
    "uifont": "Natron reads its font before any script runs: set Preferences › Appearance › Font yourself",
    "dagbackcolor": "Natron draws the node graph's background with the interface's base colour (the stylesheet), "
    "so it isn't set alone",
}


@dataclasses.dataclass(frozen=True)
class Shortcut:
    keys: str  # Qt's way of writing it: Ctrl+Shift+B
    nuke_class: str  # the node the command makes (Blur), or "" when it's not a node
    name: str  # the menu entry it was given in menu.py (Filter/Blur)
    line: int  # where in menu.py


@dataclasses.dataclass
class Plan:
    settings: dict[str, Any] = dataclasses.field(default_factory=dict)  # Natron preference: value
    shortcuts: list[dict[str, str]] = dataclasses.field(default_factory=list)  # keys, plugin, alias, label, ...
    notes: list[tuple[str, str]] = dataclasses.field(default_factory=list)  # (what, what happened and why)
    read: list[str] = dataclasses.field(default_factory=list)  # the files read

    def report(self) -> str:
        lines = [f"Read: {', '.join(self.read) or 'nothing'}."]
        if self.settings:
            lines.append("Preferences taken: " + ", ".join(f"{k} = {v}" for k, v in self.settings.items()) + ".")
        if self.shortcuts:
            lines.append(
                "Shortcuts taken: " + ", ".join(f"{s['keys']} {s['label']}" for s in self.shortcuts) + "."
            )
        for what, why in self.notes:
            lines.append(f"- {what}: {why}")
        return "\n".join(lines)


# --- Finding the files ---


def nuke_folder(home: str | os.PathLike[str] | None = None) -> Path | None:
    """The artist's ``.nuke`` folder (NUKE_PATH isn't followed: it's for shared tools, not preferences)."""
    base = Path(home) if home is not None else Path.home()
    folder = base / ".nuke"
    return folder if folder.is_dir() else None


def preferences_file(folder: Path) -> Path | None:
    """The newest ``preferences<version>.nk`` in the folder (``preferences15.1.nk`` over ``preferences14.0.nk``)."""
    best: tuple[tuple[int, ...], Path] | None = None
    for path in folder.glob("preferences*.nk"):
        numbers = tuple(int(n) for n in re.findall(r"\d+", path.stem))
        if best is None or numbers > best[0]:
            best = (numbers, path)
    return best[1] if best else None


def has_something(home: str | os.PathLike[str] | None = None) -> bool:
    folder = nuke_folder(home)
    return folder is not None and (preferences_file(folder) is not None or (folder / "menu.py").is_file())


# --- Reading Nuke's script format (no code run) ---

_TOKEN = re.compile(r'\s*(?:(\{)|(\})|"((?:[^"\\]|\\.)*)"|([^\s{}"]+))', re.S)


def _tokens(text: str) -> Iterable[tuple[str, str, int]]:
    """(kind, value, line) for ``{``, ``}``, quoted strings and words."""
    position = 0
    while position < len(text):
        match = _TOKEN.match(text, position)
        if match is None or match.end() == position:
            break
        line = text.count("\n", 0, match.start(match.lastindex or 0)) + 1
        position = match.end()
        if match.group(1):
            yield ("open", "{", line)
        elif match.group(2):
            yield ("close", "}", line)
        elif match.group(3) is not None:
            yield ("word", re.sub(r"\\(.)", r"\1", match.group(3)), line)
        elif match.group(4):
            yield ("word", match.group(4), line)


def node_knobs(text: str, node_class: str = "Preferences") -> dict[str, str]:
    """The knobs of the first ``<node_class> { … }`` block, as text: ``{"maxPanels": "10", ...}``. A knob's value is
    what follows its name on its line (a value in braces may span lines; it's kept as written inside them)."""
    tokens = list(_tokens(text))
    start = None
    for i in range(len(tokens) - 1):
        if tokens[i] == ("word", node_class, tokens[i][2]) and tokens[i + 1][0] == "open":
            start = i + 2
            break
    if start is None:
        return {}
    knobs: dict[str, str] = {}
    depth = 0
    current: str | None = None
    current_line = -1
    parts: list[str] = []
    i = start
    while i < len(tokens):
        kind, value, line = tokens[i]
        if kind == "close" and depth == 0:
            break
        if depth == 0 and kind == "word" and line != current_line:
            if current is not None:
                knobs[current] = " ".join(parts)
            current, current_line, parts = value, line, []
        elif kind == "open":
            group, i = _brace_group(tokens, i)
            parts.append(group)
        else:
            parts.append(value)
        i += 1
    if current is not None:
        knobs[current] = " ".join(parts)
    return knobs


def _brace_group(tokens: list[tuple[str, str, int]], i: int) -> tuple[str, int]:
    depth = 0
    words = []
    while i < len(tokens):
        kind, value, _line = tokens[i]
        if kind == "open":
            depth += 1
            if depth > 1:
                words.append("{")
        elif kind == "close":
            depth -= 1
            if depth == 0:
                return " ".join(words), i
            words.append("}")
        else:
            words.append(value)
        i += 1
    return " ".join(words), i


def read_preferences(path: Path) -> dict[str, str]:
    return node_knobs(path.read_text(encoding="utf-8", errors="replace"))


# --- Reading menu.py (parsed, never run) ---

_MODIFIER_WORDS = {"ctrl": "Ctrl", "control": "Ctrl", "cmd": "Ctrl", "alt": "Alt", "option": "Alt",
                   "shift": "Shift", "meta": "Meta"}  # fmt: skip
_KEY_NAMES = {"del": "Delete", "delete": "Delete", "backspace": "Backspace", "return": "Return", "enter": "Return",
              "tab": "Tab", "space": "Space", "esc": "Escape", "escape": "Escape", "up": "Up", "down": "Down",
              "left": "Left", "right": "Right", "home": "Home", "end": "End", "pageup": "PgUp",
              "pagedown": "PgDown", "period": ".", "backslash": "\\"}  # fmt: skip


def qt_keys(nuke_shortcut: str) -> str | None:
    """A Nuke shortcut in Qt's spelling: ``"ctrl+shift+b"`` → ``"Ctrl+Shift+B"``; Nuke's short prefixes too:
    ``^`` Ctrl, ``#`` Alt, ``+`` Shift (``"^+b"`` → ``"Ctrl+Shift+B"``). None when it can't be read."""
    text = nuke_shortcut.strip()
    if not text:
        return None
    modifiers: list[str] = []
    while len(text) > 1 and text[0] in "^#+@":
        modifiers.append({"^": "Ctrl", "#": "Alt", "+": "Shift", "@": "Meta"}[text[0]])
        text = text[1:]
    parts = [p for p in re.split(r"\+(?=.)", text) if p != ""] if "+" in text[:-1] else [text]
    key = parts[-1]
    for word in parts[:-1]:
        mapped = _MODIFIER_WORDS.get(word.strip().lower())
        if mapped is None:
            return None
        modifiers.append(mapped)
    key = key.strip()
    lowered = key.lower()
    if lowered in _KEY_NAMES:
        key = _KEY_NAMES[lowered]
    elif re.fullmatch(r"f\d{1,2}", lowered):
        key = lowered.upper()
    elif len(key) == 1:
        key = key.upper()
    else:
        return None
    order = ["Ctrl", "Alt", "Shift", "Meta"]
    unique = sorted(set(modifiers), key=order.index)
    return "+".join([*unique, key])


def _string(node: ast.AST | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _created_class(node: ast.AST | None) -> str:
    """The class a command makes: ``'nuke.createNode("Blur")'`` or ``lambda: nuke.createNode('Blur')``."""
    text = _string(node)
    if text is not None:
        found = re.search(r"createNode\(\s*['\"]([A-Za-z0-9_.]+)['\"]", text)
        return found.group(1) if found else ""
    if isinstance(node, ast.Lambda):
        node = node.body
    if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name)):
        name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        if name == "createNode" and node.args:
            return _string(node.args[0]) or ""
    return ""


def read_menu_shortcuts(source: str) -> list[Shortcut]:
    """The shortcuts menu.py gives: ``addCommand(name, command, shortcut)`` (third argument or ``shortcut=``) and
    ``findItem(name).setShortcut(keys)``, with the node each command makes when it makes one."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found: list[Shortcut] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "addCommand":
            name = _string(node.args[0]) if node.args else None
            command = node.args[1] if len(node.args) > 1 else None
            shortcut = _string(node.args[2]) if len(node.args) > 2 else None
            for keyword in node.keywords:
                if keyword.arg == "shortcut":
                    shortcut = _string(keyword.value)
                elif keyword.arg == "command":
                    command = keyword.value
            keys = qt_keys(shortcut) if shortcut else None
            if name and keys:
                found.append(Shortcut(keys, _created_class(command), name, node.lineno))
        elif node.func.attr == "setShortcut" and node.args:
            keys = qt_keys(_string(node.args[0]) or "")
            target = node.func.value
            item = ""
            if isinstance(target, ast.Call) and isinstance(target.func, ast.Attribute):
                if target.func.attr == "findItem" and target.args:
                    item = _string(target.args[0]) or ""
            if keys and item:
                guess = item.rsplit("/", 1)[-1]
                found.append(Shortcut(keys, guess if guess in NUKE_NODES else "", item, node.lineno))
    return sorted(found, key=lambda s: s.line)


# --- Translating ---


def _norm(name: str) -> str:
    return name.replace("_", "").lower()


def convert(value: str, kind: str, scale: float = 1.0) -> Any:
    """A Nuke knob's text as a Natron value; None when it isn't one."""
    text = value.strip().strip("{}").strip()
    try:
        if kind == "bool":
            if text.lower() in ("true", "1", "yes", "on"):
                return True
            if text.lower() in ("false", "0", "no", "off"):
                return False
            return None
        if kind == "int":
            return round(float(text) * scale)
        if kind == "float":
            return float(text) * scale
        if kind == "colour":
            number = int(text, 16) if text.lower().startswith("0x") else int(text)
            return tuple(round(((number >> shift) & 0xFF) / 255.0, 4) for shift in (24, 16, 8))
    except ValueError:
        return None
    return None


def translate(
    knobs: dict[str, str],
    shortcuts: list[Shortcut],
    has_plugin: Callable[[str], bool] = lambda _id: True,
    has_setting: Callable[[str], bool] = lambda _name: True,
) -> Plan:
    """What of the artist's Nuke preferences and shortcuts maps to Natron, and a note for the rest."""
    plan = Plan()
    used: set[str] = set()
    by_name = {_norm(name): (name, value) for name, value in knobs.items()}
    for pref in PREFERENCES:
        hit = next((by_name[_norm(n)] for n in pref.nuke if _norm(n) in by_name), None)
        if hit is None:
            continue
        nuke_name, text = hit
        used.add(_norm(nuke_name))
        if not has_setting(pref.natron):
            plan.notes.append((f"{nuke_name} ({pref.label})", "this Natron has no such preference"))
            continue
        value = convert(text, pref.kind, pref.scale)
        if value is None:
            plan.notes.append((f"{nuke_name} ({pref.label})", f"couldn't read its value {text!r}"))
            continue
        plan.settings[pref.natron] = value
    for key, why in NOT_APPLIED.items():
        if key in by_name:
            used.add(key)
            plan.notes.append((by_name[key][0], why))
    unused = sorted(name for name in knobs if _norm(name) not in used and name not in ("name", "inputs"))
    if unused:
        plan.notes.append(
            (f"{len(unused)} other Nuke preference(s)", "no Natron equivalent known yet: " + ", ".join(unused[:40]))
        )
    taken: dict[str, str] = {}
    for shortcut in shortcuts:
        where = f"{shortcut.keys} ({shortcut.name}, menu.py line {shortcut.line})"
        if not shortcut.nuke_class:
            plan.notes.append((where, "runs a Nuke command, not a node: nothing to map in Natron"))
            continue
        mapped = NUKE_NODES.get(shortcut.nuke_class)
        if mapped is None:
            plan.notes.append((where, f"Nuke's {shortcut.nuke_class} has no Natron equivalent known to this build"))
            continue
        plugin, alias = mapped
        if not (alias or has_plugin(plugin)):
            plan.notes.append((where, f"this Natron has no {plugin}"))
            continue
        if NATRON_NODE_KEYS.get(shortcut.keys) == plugin and not alias:
            plan.notes.append((where, "already Natron's own key for that node"))
            continue
        if shortcut.keys in taken:
            plan.notes.append((where, f"the same keys were already taken for {taken[shortcut.keys]}"))
            continue
        clash = NATRON_NODE_GRAPH_KEYS.get(shortcut.keys)
        label = alias or shortcut.nuke_class
        entry = {"keys": shortcut.keys, "plugin": plugin, "alias": alias, "label": label,
                 "nuke_class": shortcut.nuke_class}  # fmt: skip
        if clash:
            entry["replaces"] = clash
            plan.notes.append((where, f"in the node graph it takes the place of Natron's {shortcut.keys} ({clash})"))
        plan.shortcuts.append(entry)
        taken[shortcut.keys] = label
    return plan


def plan_for(
    home: str | os.PathLike[str] | None = None,
    has_plugin: Callable[[str], bool] = lambda _id: True,
    has_setting: Callable[[str], bool] = lambda _name: True,
) -> Plan:
    """Read the artist's .nuke folder (preferences and menu.py) and translate it."""
    folder = nuke_folder(home)
    if folder is None:
        plan = Plan()
        plan.notes.append(("~/.nuke", "no Nuke preferences folder was found"))
        return plan
    knobs: dict[str, str] = {}
    shortcuts: list[Shortcut] = []
    read: list[str] = []
    prefs = preferences_file(folder)
    if prefs is not None:
        knobs = read_preferences(prefs)
        read.append(str(prefs))
    menu = folder / "menu.py"
    if menu.is_file():
        shortcuts = read_menu_shortcuts(menu.read_text(encoding="utf-8", errors="replace"))
        read.append(str(menu))
    plan = translate(knobs, shortcuts, has_plugin, has_setting)
    plan.read = read
    return plan
