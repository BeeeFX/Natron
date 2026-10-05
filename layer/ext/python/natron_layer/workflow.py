# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Workflow scripts Nuke artists take for granted, in the menu bar's Nuke menu.

Written for this layer (none copied from natron-python-scripting, whose list of tools inspired the choice):

- **Extract layers into Shuffles** (Nuke › Channel): one Shuffle per layer of the selected node's stream (an EXR's
  AOVs), named after it.
- **PostageStamp** (Nuke › Other, and Tab search): the alias in ``aliases.py`` (a NoOp showing its picture).
- **Link roto to track** and **Bake expressions to keyframes** (Nuke › Roto, Nuke › Edit): a Transform inserted after
  a Roto follows a Tracker's track through an expression (Natron takes none on a shape's own parameters); baking
  turns any expressions of the selected nodes into keyframes.
- **Select similar class / colour** (Nuke › Edit).
- **Next / previous Merge operation** (Nuke › Merge).
- **Collect files…** (Nuke › File): the comp's files copied into one folder, with a copy of the comp pointing to them.
  The open comp is never changed.
- **Flipbook selected** (Nuke › Render, Alt+F as in Nuke): the selected node rendered by NatronRenderer in the
  background, then played in RV when it's on this PC (``NATRON_RV_PATH``, the fork's own setting for RV), else as a
  movie in the system's player.

Every function that does the work takes its nodes as arguments and works headless (the smoke test runs them in
NatronRenderer); the menu's functions only read the selection and show what happened.
"""

from __future__ import annotations

import dataclasses
import datetime
import glob
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from . import compat, paths

SHUFFLE = "net.sf.openfx.ShufflePlugin"
MERGE = "net.sf.openfx.MergePlugin"
COLOUR = "uk.co.thefoundry.OfxImagePlaneColour"

# The menu bar's entries (Nuke › …) and their functions here; the flipbook's is with the keys (Alt+F, hotkeys.py).
MENU = (
    ("Nuke/Channel/Extract layers into Shuffles", "extract_selected_layers"),
    ("Nuke/Edit/Select similar class", "select_similar_class"),
    ("Nuke/Edit/Select similar colour", "select_similar_colour"),
    ("Nuke/Edit/Bake expressions to keyframes", "bake_selected"),
    ("Nuke/Merge/Next operation", "next_merge_operation"),
    ("Nuke/Merge/Previous operation", "previous_merge_operation"),
    ("Nuke/Roto/Link roto to track", "link_selected_roto"),
    ("Nuke/File/Collect files...", "collect_files_dialog"),
)


def install_menu() -> list[str]:
    """The menu entries above (interface only)."""
    return [grouping for grouping, function in MENU
            if compat.add_menu_command(grouping, f"natron_layer.workflow.{function}")]


# --- Extract layers into Shuffles ---


def layers_of(app: Any, node: Any) -> list[tuple[str, list[str]]]:
    """The layers of ``node``'s stream besides its colour, each with its channels in order (``("depth", ["Z"])``).

    Read from a Shuffle's channel menu: Natron lists there exactly the layers the stream holds (an EXR's AOVs), as
    ``B.<layer>.<channel>``."""
    probe = compat.create_node(app, SHUFFLE)
    try:
        compat.connect(probe, 0, node)
        options = list(probe.getParam("outputR").getOptions())
    finally:
        probe.destroy()
    found: dict[str, list[str]] = {}
    for option in options:
        if not option.startswith("B.") or option.count(".") < 2:
            continue
        layer, letter = option[2:].rsplit(".", 1)
        if layer == COLOUR:
            continue
        found.setdefault(layer, []).append(letter)
    return [(layer, _ordered(letters)) for layer, letters in found.items()]


def _ordered(letters: list[str]) -> list[str]:
    rank = {letter: number for number, letter in enumerate("RGBAXYZWUV")}
    return sorted(letters, key=lambda letter: rank.get(letter.upper(), 99))


def shuffle_values(layer: str, letters: list[str], alpha_from_colour: bool = True) -> list[tuple[str, str]]:
    """A Shuffle's R, G, B and A for one layer: its first three channels (one channel goes to all three), its alpha
    when it has one, else the stream's own alpha (so merges keep the beauty's alpha)."""
    colour = [letter for letter in letters if letter.upper() not in ("A", "W")][:3]
    picks = [f"B.{layer}.{letter}" for letter in colour]
    if len(picks) == 1:
        picks = picks * 3
    while len(picks) < 3:
        picks.append("0")
    alpha = [letter for letter in letters if letter.upper() == "A"]
    if alpha:
        a = f"B.{layer}.{alpha[0]}"
    else:
        a = f"B.{COLOUR}.A" if alpha_from_colour else "1"
    return [("outputR", picks[0]), ("outputG", picks[1]), ("outputB", picks[2]), ("outputA", a)]


def script_name(text: str) -> str:
    """A valid Natron script name from a layer's name (``ViewLayer.DiffDir`` → ``ViewLayer_DiffDir``)."""
    name = re.sub(r"\W", "_", text).strip("_") or "Layer"
    return f"_{name}" if name[0].isdigit() else name


def extract_layers(app: Any, node: Any) -> list[Any]:
    """One Shuffle per layer of ``node``'s stream, named after the layer, in a row under it. Returns them."""
    made = []
    taken = {n.getScriptName() for n in compat.children(app)}
    try:
        x, y = node.getPosition()
    except Exception:  # noqa: BLE001
        x, y = 0.0, 0.0
    for number, (layer, letters) in enumerate(layers_of(app, node)):
        shuffle = compat.create_node(app, SHUFFLE)
        compat.connect(shuffle, 0, node)
        name = script_name(layer)
        suffix = 1
        while name in taken:
            suffix += 1
            name = f"{script_name(layer)}{suffix}"
        taken.add(name)
        try:
            shuffle.setScriptName(name)
            shuffle.setLabel(layer)
            shuffle.setPosition(x + 130.0 * number, y + 110.0)
        except Exception:  # noqa: BLE001
            pass
        for param, value in shuffle_values(layer, letters):
            compat.set_node_value(shuffle, param, value)
        # An EXR's layers are premultiplied (CG renders); Natron's Shuffle says unpremultiplied unless told, and a
        # Write would then multiply them by the alpha again.
        compat.set_node_value(shuffle, "outputPremult", "Premultiplied")
        made.append(shuffle)
    return made


def extract_selected_layers() -> list[Any]:
    """Menu: Nuke › Channel › Extract layers into Shuffles."""
    app = compat.active_app()
    selected = compat.selected_nodes(app)
    if len(selected) != 1:
        compat.information("Extract layers into Shuffles", "Select one node (a Read of a multi-layer EXR, say).")
        return []
    made = extract_layers(app, selected[0])
    if not made:
        compat.information("Extract layers into Shuffles",
                           "The selected node's picture has no layer besides its colour.")
    compat.select_nodes(app, made)
    return made


# --- Select similar ---


def similar(app: Any, reference: Any, by: str = "class") -> list[Any]:
    """The top-level nodes like ``reference``: the same plug-in (``class``) or the same node colour (``colour``)."""
    nodes = compat.children(app)
    if by == "class":
        return [n for n in nodes if n.getPluginID() == reference.getPluginID()]
    if by == "colour":
        want = tuple(round(c, 3) for c in reference.getColor())
        return [n for n in nodes if tuple(round(c, 3) for c in n.getColor()) == want]
    raise ValueError(by)


def _select_similar(by: str) -> list[Any]:
    app = compat.active_app()
    selected = compat.selected_nodes(app)
    if not selected:
        compat.information("Select similar", "Select a node first.")
        return []
    found = similar(app, selected[0], by)
    compat.select_nodes(app, found)
    return found


def select_similar_class() -> list[Any]:
    """Menu: Nuke › Edit › Select similar class."""
    return _select_similar("class")


def select_similar_colour() -> list[Any]:
    """Menu: Nuke › Edit › Select similar colour."""
    return _select_similar("colour")


# --- Merge operation cycling ---

MERGE_CYCLE = ("over", "under", "plus", "screen", "multiply", "minus", "from", "max", "min", "difference", "stencil",
               "mask", "in", "out", "atop", "divide", "average", "copy")


def cycle_merge(nodes: list[Any], step: int = 1) -> list[tuple[str, str]]:
    """Each Merge among ``nodes`` to the next (``step`` 1) or previous (-1) of Nuke's common operations. Returns
    (node, new operation) pairs."""
    done = []
    for node in nodes:
        if node.getPluginID() != MERGE:
            continue
        param = node.getParam("operation")
        options = list(param.getOptions())
        current = options[param.get()] if 0 <= param.get() < len(options) else ""
        cycle = [op for op in MERGE_CYCLE if op in options]
        position = cycle.index(current) if current in cycle else -step
        new = cycle[(position + step) % len(cycle)]
        param.setValue(options.index(new))
        done.append((node.getScriptName(), new))
    return done


def next_merge_operation() -> list[tuple[str, str]]:
    """Menu: Nuke › Merge › Next operation."""
    return cycle_merge(compat.selected_nodes(compat.active_app()), 1)


def previous_merge_operation() -> list[tuple[str, str]]:
    """Menu: Nuke › Merge › Previous operation."""
    return cycle_merge(compat.selected_nodes(compat.active_app()), -1)


# --- Roto and tracker ---

ROTO_PLUGINS = ("fr.inria.built-in.Roto", "fr.inria.built-in.RotoPaint")
TRACKER = "fr.inria.built-in.Tracker"


def roto_shapes(roto: Any) -> list[Any]:
    """Every shape of a Roto or RotoPaint node, in its layers."""
    found = []
    pending = list(roto.getRotoContext().getBaseLayer().getChildren())
    while pending:
        item = pending.pop(0)
        if hasattr(item, "getChildren") and not hasattr(item, "getNumControlPoints"):
            pending.extend(item.getChildren())
        else:
            found.append(item)
    return found


def track_of(tracker: Any, name: str | None = None) -> Any:
    """``tracker``'s track ``name``, else its selected track, else its first."""
    context = tracker.getTrackerContext()
    if name:
        return context.getTrackByName(name)
    selected = list(context.getSelectedTracks())
    tracks = selected or list(context.getAllTracks())
    return tracks[0] if tracks else None


def link_roto_to_track(app: Any, roto: Any, tracker: Any, track: Any = None, reference: int | None = None) -> Any:
    """Make ``roto``'s shapes follow ``track`` of ``tracker`` (its selected or first track), as a Nuke artist puts a
    Transform linked to a Tracker under a Roto: a Transform is inserted after ``roto`` (what it fed is fed by the
    Transform), its translate an expression giving the track's move since frame ``reference`` (the current frame by
    default), its centre the track's position on that frame. Natron takes no expression on a shape's own
    parameters, hence the Transform. Returns the Transform."""
    track = track if track is not None else track_of(tracker)
    if track is None:
        raise ValueError(f"{tracker.getScriptName()} has no track.")
    if reference is None:
        reference = int(app.timelineGetTime()) if hasattr(app, "timelineGetTime") else 1
    centre = (f"app.{tracker.getScriptName()}.getTrackerContext().getTrackByName('{track.getScriptName()}')"
              ".getParam('centerPoint')")
    downstream = [(n, i) for n in compat.children(app) for i in range(n.getMaxInputCount()) if n.getInput(i) is roto
                  or (n.getInput(i) is not None and n.getInput(i).getScriptName() == roto.getScriptName())]
    follow = compat.create_node(app, "net.sf.openfx.TransformPlugin")
    name = compat.unique_name(app, f"{roto.getScriptName()}Follow")
    follow.setScriptName(name)
    follow.setLabel(f"{name} ({tracker.getScriptName()}.{track.getScriptName()} from frame {int(reference)})")
    compat.connect(follow, 0, roto)
    point = track.getParam("centerPoint")
    for dimension in (0, 1):
        follow.getParam("center").setValue(point.getValueAtTime(int(reference), dimension), dimension)
        compat.set_expression(follow.getParam("translate"), f"{centre}.getValueAtTime(frame, dimension) - "
                              f"{centre}.getValueAtTime({int(reference)}, dimension)", dimension)
    for node, number in downstream:
        compat.connect(node, number, follow)
    try:
        x, y = roto.getPosition()
        follow.setPosition(x, y + 70)
    except Exception:  # noqa: BLE001
        pass
    return follow


def link_selected_roto() -> Any:
    """Menu: Nuke › Roto › Link roto to track: select a Roto (or RotoPaint) and a Tracker."""
    app = compat.active_app()
    selected = compat.selected_nodes(app)
    rotos = [n for n in selected if n.getPluginID() in ROTO_PLUGINS]
    trackers = [n for n in selected if n.getPluginID() == TRACKER]
    if len(rotos) != 1 or len(trackers) != 1:
        compat.information("Link roto to track", "Select one Roto (or RotoPaint) and one Tracker.")
        return None
    follow = link_roto_to_track(app, rotos[0], trackers[0])
    compat.select_only(app, follow)
    compat.information("Link roto to track", f"{follow.getScriptName()} moves {rotos[0].getScriptName()} with "
                       f"{trackers[0].getScriptName()} from frame {int(app.timelineGetTime())}. Nuke › Edit › Bake "
                       "expressions to keyframes makes it keyframes.")
    return follow


def _expression_params(node: Any) -> list[Any]:
    found = [p for p in node.getParams() if hasattr(p, "getExpression")]
    if node.getPluginID() in ROTO_PLUGINS:
        for shape in roto_shapes(node):
            for name in ("translate", "rotate", "scale", "center", "opacity"):
                param = shape.getParam(name)
                if param is not None:
                    found.append(param)
    return found


def bake_expressions(nodes: list[Any], first: int, last: int) -> int:
    """Every expression on ``nodes`` (their shapes' too, for Roto nodes) becomes a keyframe on each frame from
    ``first`` to ``last``, and the expression is removed. Returns how many dimensions were baked."""
    baked = 0
    for node in nodes:
        for param in _expression_params(node):
            try:
                dimensions = param.getNumDimensions()
            except Exception:  # noqa: BLE001
                continue
            for dimension in range(dimensions):
                if not compat.expression_of(param, dimension):
                    continue
                values = [(frame, param.getValueAtTime(frame, dimension)) for frame in range(first, last + 1)]
                compat.set_expression(param, "", dimension)
                for frame, value in values:
                    param.setValueAtTime(value, frame, dimension)
                baked += 1
    return baked


def bake_selected() -> int:
    """Menu: Nuke › Edit › Bake expressions to keyframes (the project's frame range)."""
    app = compat.active_app()
    selected = compat.selected_nodes(app)
    if not selected:
        compat.information("Bake expressions to keyframes", "Select the nodes whose expressions to bake.")
        return 0
    first, last = compat.project_frame_range(app)
    baked = bake_expressions(selected, first, last)
    compat.information("Bake expressions to keyframes", f"{baked} expression(s) baked to keyframes, frames "
                       f"{first} to {last}.")
    return baked


# --- Collect files ---

FRAME_PATTERN = re.compile(r"(#+)|%0?(\d*)d|\{frame\}")


@dataclasses.dataclass
class Collected:
    project: str = ""  # the copy of the comp, pointing to the copied files
    copied: list[str] = dataclasses.field(default_factory=list)
    missing: list[str] = dataclasses.field(default_factory=list)  # file fields whose files weren't found
    relinked: dict[str, str] = dataclasses.field(default_factory=dict)  # old value → new value


NOT_FOOTAGE = ("ocioConfigFile", "rvPath")  # the colour config and the fork's RV executable, on every Read


def file_fields(app: Any) -> list[tuple[Any, Any]]:
    """(node, parameter) for every file the comp reads (Read nodes, geometry, LUT files…), in groups too; not
    Write's (an output) nor the colour config."""
    found = []
    pending = compat.children(app)
    while pending:
        node = pending.pop(0)
        try:
            pending.extend(node.getChildren())
        except Exception:  # noqa: BLE001
            pass
        for param in node.getParams():
            value = str(param.get()).strip() if type(param).__name__ == "FileParam" else ""
            if value and param.getScriptName() not in NOT_FOOTAGE and not value.startswith("[OCIO]"):
                found.append((node, param))
    return found


def resolve(app: Any, value: str) -> str:
    """A file field's value with the project's path variables (``[Project]``, ``[OCIO]``…) replaced."""
    project_paths = compat.project_param(app, "projectPaths")
    text = str(project_paths.get()) if project_paths is not None else ""

    def variable(match: re.Match) -> str:
        return compat.project_variable(text, match.group(1)) or match.group(0)

    return re.sub(r"\[(\w+)\]", variable, value).replace("\\", "/")


def files_of(path: str) -> list[str]:
    """The files a file field names: itself, or each frame of a sequence (``####``, ``%04d``)."""
    if not FRAME_PATTERN.search(os.path.basename(path)):
        return [path] if os.path.isfile(path) else []
    folder, name = os.path.split(path)
    regex, last = "", 0
    for match in FRAME_PATTERN.finditer(name):  # each frame pattern becomes a frame number
        regex += re.escape(name[last:match.start()]) + r"-?\d+"
        last = match.end()
    regex += re.escape(name[last:])
    pattern = re.compile(f"^{regex}$")
    try:
        names = sorted(n for n in os.listdir(folder or ".") if pattern.match(n))
    except OSError:
        return []
    return [os.path.join(folder, n).replace("\\", "/") for n in names]


def collect_files(app: Any, target: str) -> Collected:
    """Copy every file the comp reads into ``target/footage/<node>/`` and write ``target/<comp>.ntp``, a copy of the
    comp reading them there (``[Project]/footage/…``: Natron sets [Project] to the folder a comp opens from). The open
    comp and its file aren't changed."""
    target_path = Path(target)
    target_path.mkdir(parents=True, exist_ok=True)
    report = Collected()
    for node, param in file_fields(app):
        value = str(param.get())
        sources = files_of(resolve(app, value))
        if not sources:
            report.missing.append(f"{node.getScriptName()}.{param.getScriptName()}: {value}")
            continue
        folder = target_path / "footage" / script_name(node.getScriptName())
        folder.mkdir(parents=True, exist_ok=True)
        for source in sources:
            destination = folder / os.path.basename(source)
            shutil.copy2(source, destination)
            report.copied.append(str(destination).replace("\\", "/"))
        report.relinked[value] = f"[Project]/footage/{folder.name}/{os.path.basename(value.replace(chr(92), '/'))}"
    name = os.path.basename(compat.project_file(app)) or "collected.ntp"
    copy = (target_path / name).as_posix()
    if not compat.save_temp_project(app, copy):
        raise RuntimeError(f"Natron couldn't save a copy of the comp at {copy}.")
    rewrite_project(copy, report.relinked)
    report.project = copy
    return report


def rewrite_project(path: str, relinked: dict[str, str]) -> None:
    """In a saved comp, each old file value replaced by its new one (a whole value only)."""
    text = Path(path).read_text(encoding="utf-8")
    for old, new in relinked.items():
        text = text.replace(f">{escape(old)}<", f">{escape(new)}<")
    Path(path).write_text(text, encoding="utf-8")


def collect_files_dialog() -> Collected | None:
    """Menu: Nuke › File › Collect files…: asks for a folder, then copies the files and writes the comp's copy."""
    app = compat.active_app()
    qt = compat.qt_modules()
    if qt is None or compat.application() is None:
        return None
    folder = qt.QtWidgets.QFileDialog.getExistingDirectory(None, "Collect files into a folder")
    if not folder:
        return None
    report = collect_files(app, folder)
    lines = [f"{len(report.copied)} file(s) copied into {folder}/footage.", f"The comp's copy: {report.project}",
             "Your open comp isn't changed."]
    if report.missing:
        lines.append("Not found: " + "; ".join(report.missing))
    compat.information("Collect files", "\n".join(lines))
    return report


# --- Flipbook ---

_running: list[Any] = []  # timers waiting for a flipbook's render, kept alive


def find_rv() -> str | None:
    """RV or OpenRV on this PC: NATRON_RV_PATH (the fork's own setting for its "Open in RV" buttons), RV_PATH,
    RV_HOME, the PATH, then the usual install folders."""
    for name in ("NATRON_RV_PATH", "RV_PATH"):
        value = os.environ.get(name, "").strip()
        if value and os.path.isfile(value):
            return value
    home = os.environ.get("RV_HOME", "").strip()
    for candidate in ([os.path.join(home, "bin", "rv.exe"), os.path.join(home, "bin", "rv")] if home else []):
        if os.path.isfile(candidate):
            return candidate
    found = shutil.which("rv")
    if found:
        return found
    if os.name == "nt":
        roots = [os.environ.get("ProgramFiles", r"C:\Program Files")]
        for pattern in ("ShotGrid/RV-*/bin/rv.exe", "Shotgun/RV-*/bin/rv.exe", "Autodesk/RV-*/bin/rv.exe",
                        "OpenRV*/bin/rv.exe", "RV*/bin/rv.exe"):
            for root in roots:
                hits = sorted(glob.glob(os.path.join(root, pattern)))
                if hits:
                    return hits[-1]
    return None


def flipbook_job_script() -> str:
    return str(paths.ext() / "python" / "natron_layer" / "flipbook_job.py")


def flipbook(app: Any, node: Any, first: int | None = None, last: int | None = None, player: str = "auto",
             movie: bool | None = None, folder: str | None = None, wait: bool = False,
             renderer: str | None = None) -> dict[str, Any]:
    """Render ``node`` from ``first`` to ``last`` (the project's range by default) with NatronRenderer, from a copy
    of the comp (the open comp isn't touched), then play it: ``player`` ``rv``, ``system`` (a movie in the system's
    player), ``none``, or ``auto`` (RV when found, else ``system``). ``movie``: an MP4 instead of EXR frames (by
    default for the system's player). With ``wait`` it returns once rendered; else the render runs in the
    background and the player opens when it's done. Returns what it started."""
    project_first, project_last = compat.project_frame_range(app)
    first = project_first if first is None else first
    last = project_last if last is None else last
    rv = find_rv() if player in ("auto", "rv") else None
    if player == "auto":
        player = "rv" if rv else "system"
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    folder = folder or os.path.join(tempfile.gettempdir(), "natron-layer-flipbook", f"{node.getScriptName()}-{stamp}")
    os.makedirs(folder, exist_ok=True)
    movie = (player == "system") if movie is None else movie
    output = os.path.join(folder, f"{node.getScriptName()}.mp4" if movie else f"{node.getScriptName()}.####.exr")
    copy = os.path.join(folder, "flipbook.ntp")
    if not compat.save_temp_project(app, copy):
        raise RuntimeError(f"Natron couldn't save a copy of the comp at {copy}.")
    paths_param = compat.project_param(app, "projectPaths")
    job = {
        "project": copy.replace("\\", "/"),
        "node": node.getScriptName(),
        "first": int(first),
        "last": int(last),
        "output": output.replace("\\", "/"),
        "movie": movie,
        "project_folder": compat.project_variable(str(paths_param.get()) if paths_param is not None else "", "Project"),
        "done": os.path.join(folder, "flipbook_done.json").replace("\\", "/"),
    }
    renderer = renderer or compat.renderer_executable()
    if renderer is None:
        raise RuntimeError("NatronRenderer wasn't found next to this Natron.")
    env = dict(os.environ, NATRON_LAYER_FLIPBOOK=json.dumps(job))
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW: no console window for the render
    process = subprocess.Popen([renderer, "-t", flipbook_job_script()], env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
    started = {"job": job, "player": player, "rv": rv, "process": process}
    if wait:
        process.wait()
        started["result"] = _result(job)
        _play(started)
    else:
        _when_done(started)
    return started


def _result(job: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(Path(job["done"]).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"ok": False, "error": "the render didn't finish (no report)"}


def _play(started: dict[str, Any]) -> bool:
    result = started.get("result") or {}
    if not result.get("ok"):
        return False
    job = started["job"]
    if started["player"] == "rv" and started["rv"]:
        subprocess.Popen([started["rv"], job["output"].replace("####", "#")])  # noqa: S603
        return True
    if started["player"] == "system":
        return compat.open_with_system(job["output"])
    return False


def _when_done(started: dict[str, Any]) -> None:
    qt = compat.qt_modules()
    if qt is None:
        return
    timer = qt.QtCore.QTimer()
    timer.setInterval(500)

    def look() -> None:
        if started["process"].poll() is None:
            return
        timer.stop()
        if timer in _running:
            _running.remove(timer)
        started["result"] = _result(started["job"])
        if not _play(started):
            compat.warning("Flipbook", "The flipbook couldn't be rendered: "
                           + str(started["result"].get("error", "see the render's report")))

    timer.timeout.connect(look)
    timer.start()
    _running.append(timer)


def flipbook_selected() -> dict[str, Any] | None:
    """Alt+F (Nuke › Render › Flipbook selected): the selected node over the project's frame range."""
    app = compat.active_app()
    selected = compat.selected_nodes(app)
    if len(selected) != 1:
        compat.information("Flipbook", "Select the one node to flipbook.")
        return None
    started = flipbook(app, selected[0])
    first, last = started["job"]["first"], started["job"]["last"]
    where = "RV" if started["player"] == "rv" else "your video player"
    compat.say(f"Flipbook: rendering {selected[0].getScriptName()} frames {first}-{last} in the background; it opens "
               f"in {where} when done ({started['job']['output']}).")
    return started
