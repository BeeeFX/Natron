# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""ToolSets, as in Nuke: saved node setups pasted into the comp (menu bar › Nuke › ToolSets).

A ToolSet is a file of Natron's own copied nodes (``<name>.xml``, the text Natron's Copy puts on the clipboard and
its Paste reads), so pasting one is Natron's paste: ``pasteNodes`` after putting the file's text on the clipboard
(whatever the artist had there is put back). Three places hold them, each a menu of its own:

- **Studio**: the layer's own, ``ext/toolsets/`` (made by ``layer/tools/make_toolsets.py`` from
  ``toolset_recipes.py``).
- **Mine**: the artist's, saved with **Save selection as ToolSet…**, in ``%APPDATA%\\natron-layer\\toolsets``.
- **Project**: the folders listed in ``NATRON_LAYER_TOOLSETS`` (separated as on PATH). This is the way in for
  Singerie's tool library: its desktop helper can point it at the project's pinned ToolSets when it launches Natron.

After a paste: a Dot named ``ToolSetIn`` is connected to the node that was selected, and each Shuffle named
``AOV_<pass>`` takes that pass's layer from its input when there is one (else black), so a beauty rebuild finds the
render's AOVs. Pasting needs Natron's window (Natron's paste is part of it).
"""

from __future__ import annotations

import dataclasses
import os
import re
from pathlib import Path
from typing import Any

from . import compat, paths, user_config

ENVIRONMENT = "NATRON_LAYER_TOOLSETS"
SHUFFLE = "net.sf.openfx.ShufflePlugin"
COLOUR = "uk.co.thefoundry.OfxImagePlaneColour"


@dataclasses.dataclass(frozen=True)
class ToolSet:
    name: str
    path: str
    place: str  # "Studio", "Mine" or "Project"


def studio_folder() -> Path:
    return paths.ext() / "toolsets"


def my_folder() -> Path:
    return user_config.folder() / "toolsets"


def project_folders() -> list[Path]:
    return [Path(p) for p in os.environ.get(ENVIRONMENT, "").split(os.pathsep) if p.strip()]


def all_toolsets() -> list[ToolSet]:
    """Every ToolSet there is now: the studio's (by their recipes' titles), the artist's, the project's."""
    from . import toolset_recipes  # noqa: PLC0415

    titles = {toolset_recipes.file_name(title): title for title in toolset_recipes.RECIPES}
    found = []
    for place, folders in (("Studio", [studio_folder()]), ("Mine", [my_folder()]), ("Project", project_folders())):
        for folder in folders:
            for path in sorted(folder.glob("*.xml")) if folder.is_dir() else []:
                name = titles.get(path.name) if place == "Studio" else None
                found.append(ToolSet(name or path.stem.replace("_", " "), str(path), place))
    return found


def looks_like_natron_nodes(text: str) -> bool:
    """Natron's copied nodes are a boost XML archive whose root is ``Clipboard``."""
    return "<boost_serialization" in text and "<Clipboard" in text


# --- After a paste ---


def layer_options(shuffle: Any) -> dict[str, list[str]]:
    """The layers a Shuffle's B input offers (``{"ViewLayer.DiffDir": ["R", "G", "B"]}``)."""
    found: dict[str, list[str]] = {}
    for option in shuffle.getParam("outputR").getOptions():
        if option.startswith("B.") and option.count(".") >= 2:
            layer, letter = option[2:].rsplit(".", 1)
            if layer != COLOUR:
                found.setdefault(layer, []).append(letter)
    return found


def match_aov_shuffles(nodes: list[Any]) -> tuple[list[str], list[str]]:
    """Each Shuffle named ``AOV_<pass>`` among ``nodes`` takes the layer named ``<pass>`` (or ``<anything>.<pass>``)
    from its input; a pass the input lacks is set to black. Returns (matched, missing) passes."""
    from . import workflow  # noqa: PLC0415

    matched, missing = [], []
    for node in nodes:
        name = _tag(node)
        if node.getPluginID() != SHUFFLE or not name.startswith("AOV_"):
            continue
        wanted = name[4:].lower()
        layers = layer_options(node)
        found = next((layer for layer in layers if layer.lower() == wanted or layer.lower().endswith("." + wanted)),
                     None)
        if found is None:
            for param in ("outputR", "outputG", "outputB", "outputA"):
                compat.set_node_value(node, param, "0")
            missing.append(name[4:])
            continue
        for param, value in workflow.shuffle_values(found, layers[found], alpha_from_colour=False):
            compat.set_node_value(node, param, value if param != "outputA" else "0")
        matched.append(name[4:])
    return matched, missing


@dataclasses.dataclass
class Pasted:
    nodes: list[str] = dataclasses.field(default_factory=list)
    connected_to: str = ""
    matched: list[str] = dataclasses.field(default_factory=list)
    missing: list[str] = dataclasses.field(default_factory=list)

    def summary(self, name: str) -> str:
        parts = [f"{name}: {len(self.nodes)} node(s) pasted"]
        if self.connected_to:
            parts.append(f"fed by {self.connected_to}")
        if self.matched or self.missing:
            parts.append(f"passes found: {', '.join(self.matched) or 'none'}")
        if self.missing:
            parts.append(f"not in the input (set to black): {', '.join(self.missing)}")
        return "; ".join(parts) + "."


def _tag(node: Any) -> str:
    """What a ToolSet calls a node: its label (Natron renames a pasted node whose name is taken, not its label),
    else its name."""
    label = str(node.getLabel() or "")
    return label if label.startswith(("ToolSetIn", "ToolSetOut", "AOV_")) else node.getScriptName()


def find(nodes: list[Any], tag: str) -> Any:
    """The pasted node labelled (or named) ``tag`` (``ToolSetIn``, ``ToolSetOut``)."""
    return next((n for n in nodes if _tag(n) == tag), None) or next(
        (n for n in nodes if n.getScriptName().startswith(tag)), None)


def after_paste(app: Any, new_nodes: list[Any], source: Any = None) -> Pasted:
    """Connect the ToolSet's ``ToolSetIn`` to ``source`` and match its AOV Shuffles (works headless too, on nodes a
    recipe made)."""
    report = Pasted(nodes=[n.getScriptName() for n in new_nodes])
    start = find(new_nodes, "ToolSetIn")
    if start is not None and source is not None:
        compat.connect(start, 0, source)
        report.connected_to = source.getScriptName()
    report.matched, report.missing = match_aov_shuffles(new_nodes)
    return report


# --- Paste and save (interface only) ---


def paste(app: Any, toolset: ToolSet, source: Any = None) -> Pasted:
    """Paste ``toolset`` with Natron's own paste, fed by ``source`` (the selected node by default)."""
    text = Path(toolset.path).read_text(encoding="utf-8")
    if not looks_like_natron_nodes(text):
        raise ValueError(f"{toolset.path} isn't a file of Natron's copied nodes.")
    if source is None:
        selected = compat.selected_nodes(app)
        source = selected[0] if len(selected) == 1 else None
    before = {n.getScriptName() for n in compat.children(app)}
    with compat.kept_clipboard():
        # Natron's paste reads whatever the clipboard holds (and failed badly on an empty one): only paste once the
        # ToolSet is really there.
        if not compat.set_clipboard_text(text):
            raise RuntimeError("Windows didn't let Natron put the ToolSet on the clipboard (another program had it "
                               "open); try again.")
        compat.paste_nodes(app)
    new_nodes = [n for n in compat.children(app) if n.getScriptName() not in before]
    return after_paste(app, new_nodes, source)


def save_selection(app: Any, name: str) -> Path:
    """The selected nodes, copied with Natron's own Copy, saved as one of the artist's ToolSets."""
    clean = re.sub(r"[^\w\- ]", "", name).strip().replace(" ", "_")
    if not clean:
        raise ValueError("A ToolSet needs a name.")
    with compat.kept_clipboard():
        compat.copy_selected_nodes(app)
        text = compat.clipboard_text()
    if not looks_like_natron_nodes(text):
        raise ValueError("Natron's Copy gave nothing (select the nodes first).")
    folder = my_folder()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{clean}.xml"
    target.write_text(text, encoding="utf-8")
    return target


# --- The menu ---


def _paste_number(number: int) -> Pasted | None:
    if number >= len(_menu_toolsets):
        return None
    toolset = _menu_toolsets[number]
    if not os.path.isfile(toolset.path):
        compat.warning("ToolSets", f"{toolset.path} isn't there any more.")
        return None
    app = compat.active_app()
    report = paste(app, toolset)
    compat.say(report.summary(toolset.name))
    return report


_menu_toolsets: list[ToolSet] = []


def save_selection_dialog() -> Path | None:
    """Menu: Nuke › ToolSets › Save selection as ToolSet…"""
    qt = compat.qt_modules()
    app = compat.active_app()
    if not compat.selected_nodes(app):
        compat.information("Save selection as ToolSet", "Select the nodes to keep as a ToolSet first.")
        return None
    name, ok = qt.QtWidgets.QInputDialog.getText(None, "Save selection as ToolSet", "Name of the ToolSet:")
    if not ok or not name.strip():
        return None
    try:
        path = save_selection(app, name)
    except ValueError as exc:
        compat.warning("Save selection as ToolSet", str(exc))
        return None
    compat.information("Save selection as ToolSet", f"Saved in {path}. It's under Nuke › ToolSets › Paste a "
                       "ToolSet… now, and in the ToolSets menu when Natron starts again.")
    return path


def paste_dialog() -> Pasted | None:
    """Menu: Nuke › ToolSets › Paste a ToolSet…: every ToolSet there is now (saved this session included)."""
    qt = compat.qt_modules()
    found = all_toolsets()
    if not found:
        compat.information("Paste a ToolSet", "No ToolSet yet: select nodes and use Save selection as ToolSet….")
        return None
    labels = [f"{t.place}: {t.name}" for t in found]
    label, ok = qt.QtWidgets.QInputDialog.getItem(None, "Paste a ToolSet", "ToolSet:", labels, 0, False)
    if not ok:
        return None
    toolset = found[labels.index(label)]
    report = paste(compat.active_app(), toolset)
    compat.say(report.summary(toolset.name))
    return report


def install_menu() -> list[str]:
    """Nuke › ToolSets: one entry per ToolSet found at start, then Paste a ToolSet… and Save selection as
    ToolSet…. Interface only."""
    done = []
    _menu_toolsets[:] = all_toolsets()
    for number, toolset in enumerate(_menu_toolsets):
        name = f"paste_{number}"
        globals()[name] = (lambda n: lambda: _paste_number(n))(number)
        if compat.add_menu_command(f"Nuke/ToolSets/{toolset.place}/{toolset.name}", f"natron_layer.toolsets.{name}"):
            done.append(f"{toolset.place}/{toolset.name}")
    compat.add_menu_command("Nuke/ToolSets/Paste a ToolSet...", "natron_layer.toolsets.paste_dialog")
    compat.add_menu_command("Nuke/ToolSets/Save selection as ToolSet...", "natron_layer.toolsets.save_selection_dialog")
    return done
