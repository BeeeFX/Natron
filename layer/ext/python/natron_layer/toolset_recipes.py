# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""How the studio ToolSets shipped with the layer are made: each recipe builds its nodes at the comp's top level.

``layer/tools/make_toolsets.py`` runs them in Natron's window, copies the result with Natron's own Copy and saves it
as ``ext/toolsets/<name>.xml`` (Natron's clipboard format, what its Paste reads). The smoke test builds the same
recipes headless and checks their pixels, and pastes the saved files in the window.

Every ToolSet starts at a Dot labelled ``ToolSetIn`` (pasting connects it to the selected node) and ends at a Dot
labelled ``ToolSetOut``. A Shuffle labelled ``AOV_<pass>`` takes the layer of that name from its input once pasted
(``toolsets.match_aov_shuffles``: ``ViewLayer.DiffDir`` or ``DiffDir`` both match ``AOV_DiffDir``). Labels, because
Natron renames pasted nodes whose names are taken (a second paste) and keeps their labels.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import compat, gizmos

DOT = "fr.inria.built-in.Dot"
SHUFFLE = "net.sf.openfx.ShufflePlugin"
MERGE = "net.sf.openfx.MergePlugin"

# Blender Cycles' light passes and how they add up to the beauty (Blender's manual, "Render Passes"):
# (Dir + Ind) x Col for diffuse, glossy and transmission, plus volume, emission and the environment.
CYCLES_SHADERS = ("Diff", "Gloss", "Trans")
CYCLES_ADDED = ("VolumeDir", "VolumeInd", "Emit", "Env")
# A CG render's passes are premultiplied (by the coverage); Natron's Shuffle says "unpremultiplied" unless told, and
# a Write would then multiply them by the alpha a second time.
PREMULTIPLIED = (("outputPremult", "Premultiplied"),)


def _node(app: Any, plugin_id: str, name: str, x: float, y: float, values: tuple = (), inputs: tuple = ()) -> Any:
    node = compat.create_node(app, plugin_id)
    if node is None:
        raise RuntimeError(f"Natron couldn't make a {plugin_id} node.")
    if not node.setScriptName(name):
        raise RuntimeError(f"The comp already has a node named {name}.")
    node.setLabel(name)
    node.setPosition(x, y)
    for param, value in values:
        if not compat.set_node_value(node, param, value):
            raise RuntimeError(f"{plugin_id} has no {param} taking {value!r}.")
    for number, source in enumerate(inputs):
        if source is not None:
            compat.connect(node, number, source)
    return node


def cg_beauty_rebuild(app: Any, x: float = 0.0, y: float = 0.0) -> dict[str, Any]:
    """Blender Cycles' passes back into the beauty, with a check against the render's own beauty."""
    made: dict[str, Any] = {}
    made["ToolSetIn"] = start = _node(app, DOT, "ToolSetIn", x + 600, y)
    column = 0
    shader_results = []
    for shader in CYCLES_SHADERS:
        shuffles = {}
        for kind in ("Dir", "Ind", "Col"):
            name = f"AOV_{shader}{kind}"
            shuffles[kind] = made[name] = _node(app, SHUFFLE, name, x + 110 * column, y + 120, PREMULTIPLIED,
                                                inputs=(start,))
            column += 1
        light = made[f"{shader}Light"] = _node(app, MERGE, f"{shader}Light", x + 110 * (column - 2), y + 220,
                                               (("operation", "plus"),), (shuffles["Dir"], shuffles["Ind"]))
        result = made[f"{shader}Result"] = _node(app, MERGE, f"{shader}Result", x + 110 * (column - 2), y + 300,
                                                 (("operation", "multiply"),), (light, shuffles["Col"]))
        shader_results.append(result)
    added = []
    for name in CYCLES_ADDED:
        node = made[f"AOV_{name}"] = _node(app, SHUFFLE, f"AOV_{name}", x + 110 * column, y + 120, PREMULTIPLIED,
                                           inputs=(start,))
        added.append(node)
        column += 1
    streams = shader_results + added
    inputs = [streams[0], streams[1], None, *streams[2:]]  # Merge: B, A, the mask, then A2, A3…
    made["Rebuild"] = rebuild = _node(app, MERGE, "Rebuild", x + 330, y + 400, (("operation", "plus"),), tuple(inputs))
    colour = "uk.co.thefoundry.OfxImagePlaneColour"
    made["KeepAlpha"] = keep = _node(app, SHUFFLE, "KeepAlpha", x + 330, y + 480, (
        ("outputR", f"B.{colour}.R"), ("outputG", f"B.{colour}.G"), ("outputB", f"B.{colour}.B"),
        ("outputA", f"A.{colour}.A"), *PREMULTIPLIED), (rebuild, start))
    made["ToolSetOut"] = _node(app, DOT, "ToolSetOut", x + 330, y + 560, inputs=(keep,))
    made["Check"] = check = _node(app, MERGE, "Check", x + 600, y + 480, (
        ("operation", "difference"), ("OutputChannelsA", False)), (start, rebuild))
    check.setLabel("Check (black when the passes add up to the beauty)")
    return made


def grain_and_lens(app: Any, x: float = 0.0, y: float = 0.0) -> dict[str, Any]:
    """A CG element made to sit in a plate: the lens's distortion, its colour fringes and vignetting, then grain."""
    made: dict[str, Any] = {}
    made["ToolSetIn"] = start = _node(app, DOT, "ToolSetIn", x, y)
    made["LensDistort"] = lens = _node(app, "net.sf.openfx.LensDistortion", "LensDistort", x, y + 80, (
        ("model", "nuke"), ("direction", "Distort")), (start,))
    lens.setLabel("LensDistort (the plate's lens: set k1, k2)")
    previous = lens
    for number, (gizmo, name, values) in enumerate((
            ("ChromaticAberration", "LensFringes", (("amount", 0.002),)),
            ("Vignette", "LensVignette", (("amount", 0.15), ("scale", 1.6))),
            ("Grain", "PlateGrain", ()))):
        node = compat.create_node(app, gizmos.BY_NAME[gizmo].plugin_id)
        if node is None:
            raise RuntimeError(f"Natron couldn't make the {gizmo} gizmo.")
        if not node.setScriptName(name):
            raise RuntimeError(f"The comp already has a node named {name}.")
        node.setLabel(name)
        node.setPosition(x, y + 160 + 80 * number)
        for param, value in values:
            compat.set_node_value(node, param, value)
        compat.connect(node, 0, previous)
        made[name] = previous = node
    made["ToolSetOut"] = _node(app, DOT, "ToolSetOut", x, y + 420, inputs=(previous,))
    return made


RECIPES: dict[str, Callable[..., dict[str, Any]]] = {
    "CG beauty rebuild (Cycles passes)": cg_beauty_rebuild,
    "Grain and lens": grain_and_lens,
}


def file_name(title: str) -> str:
    """``CG beauty rebuild (Cycles passes)`` → ``CG_beauty_rebuild_Cycles_passes.xml``."""
    import re  # noqa: PLC0415

    return re.sub(r"_+", "_", re.sub(r"\W", "_", title)).strip("_") + ".xml"
