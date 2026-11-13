# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Cryptomatte for Natron: a matte of the objects (or materials, assets…) named in a list, from a render's
Cryptomatte layers, the way Nuke's Cryptomatte works. One of the layer's gizmos (``gizmos.py``): a Group of Natron's
own nodes, rendered on the CPU.

How it's built, and why (natron_layer.cryptomatte_data has the arithmetic):

- **One branch per layer of ranks** (``Rank0``…``Rank7``: up to 16 ranks, the most Blender and Karma write): a
  Shuffle takes the ``<name>NN`` layer into RGBA and a CImgExpression (``Ranks0``…) adds up both ranks' coverage
  where the rank's ID is in the list. CImg's math is double precision and each ID is written as the shortest decimal
  that reads back as the same 32-bit float, so the comparison is exact (checked on every ID of the test renders).
  A Merge (plus) sums the branches: the matte is the sum of every listed object's coverage over every rank, soft and
  exact at edges and through motion blur, and an empty rank (ID 0) never counts.
- **The list lives in the comp as names** (``matteList``), with wildcards; the IDs are worked out in Python when
  the list, the layer or the manifest changes, and written into the inner nodes' expressions. So a saved comp
  renders the same on the farm (NatronRenderer), and opens as a plain Group where the layer isn't installed: the
  Python only runs while an artist edits the list.
- **Picking**: Natron lets a colour control take the colour under a Ctrl+click in the viewer (exact 32-bit values with
  Natron's default "Linear color pickers"), but tells a script nothing else (no position, no pixels). So the
  **preview** draws each object in a colour that holds its ID exactly (``cryptomatte_data.preview_expression``), and
  the picked colour gives the ID back. Pick (add) and Pick (remove) are those colour controls.
- The **manifest** (names) is read from the EXR's header by a few lines of Python (no pixels read): from the
  Read upstream of the node, or from the file given in Manifest file (an EXR or a sidecar JSON). Without one, plain
  names still work (they're hashed as the renderer does); wildcards and picking by name need it.

- **The first inner nodes are named after the node** (``Rank0_Cryptomatte1``…). Natron's image cache knows a node by
  a hash of its *own* script name, its inputs' hashes and a count of its changes (``Node::computeHashInternal``),
  not by its parameters' values nor the group it's in: two Cryptomattes on the same Read, with inner nodes of the
  same names and the same number of changes, shared their cached mattes (checked: the second rendered the first's).
  So the nodes fed straight by the group's inputs carry the node's name (set again whenever the node is connected,
  a pasted copy too), which makes every node after them distinct through its inputs; they're found by their role
  (the name before ``_``), and their values are all worked out again from the controls (``refresh``). The other
  gizmos, and any Group with fixed inner names, can still meet it: see ``layer/GAPS.md``.

No NatronGui: it builds and renders headless.
"""

from __future__ import annotations

import os
import re
from typing import Any

from . import compat
from . import cryptomatte_data as data
from .gizmo_kit import Kit, channel

SHUFFLE = "net.sf.openfx.ShufflePlugin"
EXPRESSION = "net.sf.cimg.CImgExpression"
MERGE = "net.sf.openfx.MergePlugin"
SWITCH = "net.sf.openfx.switchPlugin"
PREMULT = "net.sf.openfx.Premult"
NEEDS = (SHUFFLE, EXPRESSION, MERGE, SWITCH, PREMULT)

RANK_LAYERS = 8  # branches, each a layer of two ranks
# The inner nodes fed straight by the group's inputs: named after the node (see the notes above). The others are told
# apart by their inputs already, and keep fixed names (OutputSwitch's expression is compiled with its node's name).
NAMED = (*(f"Rank{k}" for k in range(RANK_LAYERS)), "ImageIn")
OUTPUTS = ("image, matte in alpha", "image premultiplied by the matte", "matte only")
PICK_PARAMS = ("pickAdd", "pickRemove")
ADD_NAME_FIRST = "(choose a name to add it)"
_RANK_LAYER = re.compile(r"^B\.(.+?)(\d\d)\.([RGBA])$", re.I)

# --- Building ---


def build(kit: Kit) -> None:
    source = kit.input("Source")
    image = kit.input("Image", optional=True)
    kit.group.getParam("onParamChanged").setValue("natron_layer.cryptomatte.param_changed")
    kit.group.getParam("onInputChanged").setValue("natron_layer.cryptomatte.input_changed")

    layer = kit.choice("cryptoLayer", "Layer", ["(connect a render with Cryptomatte layers)"], 0,
                       help="Which Cryptomatte of the render: objects, materials, assets… (the names the renderer "
                       "gave them: CryptoObject, CryptoMaterial, Karma's CryptoPrimitives…).")
    layer.setPersistent(False)
    kit.string("layerName", "Layer name", "default", "The Cryptomatte the node keys (kept with the comp).",
               visible=False)
    for name, label, what in (("pickAdd", "Pick (add)", "add"), ("pickRemove", "Pick (remove)", "remove")):
        pick = kit.colour(name, label, (0.0, 0.0, 0.0),
                          help=f"Click the colour square, then Ctrl+click an object in the viewer to {what} it "
                          "(the viewer shows this node with Preview on, at 100 % or closer).")
        pick.setPersistent(False)
        pick.setEvaluateOnChange(False)
    by_name = kit.choice("addName", "Add by name", [ADD_NAME_FIRST], 0,
                         help="Every name in the layer's manifest: choose one to add it to the list.")
    by_name.setPersistent(False)
    by_name.setEvaluateOnChange(False)
    kit.string("matteList", "Matte list", "multiline",
               "The objects in the matte, one a line (or separated by commas): names as the manifest writes them, "
               "* and ? as wildcards, -name to leave out what a wildcard took, <0.123> for an ID without a name. "
               "Kept with the comp.")
    kit.button("clear", "Clear the list", "Empty the matte list.")
    kit.boolean("preview", "Preview", False,
                help="Shows every object in its own colour (the listed ones bright, the others dim), the matte in "
                "alpha: what picking reads (a pick turns it on). Off for the render: the image and the matte.")
    kit.choice("output", "Output", OUTPUTS, 0, help="What comes out (Preview off): the image with the matte in "
               "alpha, the image multiplied by the matte, or the matte alone in every channel.")
    kit.file("manifestFile", "Manifest file", "Where the names are when the render's own header has none (a "
             "sidecar .json, or another frame or the beauty .exr of the same render). Empty: the Read upstream of "
             "this node.")
    kit.button("reload", "Read the manifest again", "After the render was written again.")
    kit.string("status", "", "label")

    ranks = []
    for k in range(RANK_LAYERS):
        x = 200.0 * k
        shuffle = kit.node(SHUFFLE, f"Rank{k}", [(f"output{c}", "0") for c in "RGBA"], [source], at=(x, 120))
        expression = kit.node(EXPRESSION, f"Ranks{k}", (("expression", "0"),), [shuffle], at=(x, 200))
        kit.only_channels(expression, "RGBA")
        _no_premult(expression)
        ranks.append(expression)
    matte = kit.node(MERGE, "Matte", (("operation", "plus"),), _merge_inputs(ranks), at=(700, 300))
    preview = kit.node(EXPRESSION, "Preview", (("expression", data.preview_expression([])),),
                       [ranks[0].getInput(0)], at=(-200, 200))
    kit.only_channels(preview, "RGBA")
    _no_premult(preview)

    picture = kit.node(SWITCH, "ImageIn", (("which", 1),), [image, source], at=(-400, 300))
    with_matte = kit.node(SHUFFLE, "WithMatte", [*((f"output{c}", channel("B", c)) for c in "RGB"),
                                                 ("outputA", channel("A", "R"))], [picture, matte], at=(-400, 380))
    premultiplied = kit.node(PREMULT, "Premultiplied", (), [with_matte], at=(-200, 460))
    matte_only = kit.node(SHUFFLE, "MatteOnly", [(f"output{c}", channel("A", "R")) for c in "RGBA"],
                          [matte, matte], at=(0, 460))
    preview_out = kit.node(SHUFFLE, "PreviewOut", [*((f"output{c}", channel("B", c)) for c in "RGB"),
                                                   ("outputA", channel("A", "R"))], [preview, matte], at=(200, 460))
    for node, state in ((with_matte, "Unpremultiplied"), (matte_only, "Premultiplied"),
                        (preview_out, "Unpremultiplied")):
        _set_option(node.getParam("outputPremult"), state)
    switch = kit.node(SWITCH, "OutputSwitch", (), [with_matte, premultiplied, matte_only, preview_out],
                      at=(0, 560))
    kit.expression(switch, "which", "3 if thisGroup.preview.get() else thisGroup.output.get()")
    kit.output(switch)
    layer.setEvaluateOnChange(False)
    name_inner_nodes(kit.group)


def inner(node: Any, role: str) -> Any:
    """The inner node playing ``role`` (``Ranks0``…), whatever node name it carries (``Ranks0_<node>``)."""
    for child in compat.children(node):
        name = child.getScriptName()
        if name == role or name.startswith(role + "_"):
            return child
    return None


def name_inner_nodes(node: Any) -> None:
    """Give the inner nodes the node's name (their image cache entries then can't be taken for another
    Cryptomatte's: see the module's notes)."""
    suffix = re.sub(r"\W", "_", str(node.getScriptName()))
    for role in NAMED:
        child = inner(node, role)
        wanted = f"{role}_{suffix}"
        if child is not None and child.getScriptName() != wanted:
            child.setScriptName(wanted)
            child.setLabel(role)


def _no_premult(node: Any) -> None:
    """CImg's nodes divide by alpha first and multiply after, unless told not to; an alpha here is a coverage."""
    compat.set_node_value(node, "premultChanged", True)
    compat.set_node_value(node, "premult", False)


def _merge_inputs(streams: list[Any]) -> list[Any]:
    """Merge's inputs for B, A, A2, A3…: 0 is B, 1 is A, 2 is the mask, 3 onwards A2, A3…"""
    return [streams[0], streams[1], None, *streams[2:]]


def _set_option(param: Any, label: str) -> bool:
    if param is None:
        return False
    options = [str(o) for o in param.getOptions()]
    wanted = [i for i, o in enumerate(options) if o.lower() == label.lower()]
    if not wanted:
        return False
    if param.get() != wanted[0]:
        param.setValue(wanted[0])
    return True


# --- Reading what's upstream ---


def stream_layers(node: Any) -> dict[str, dict[int, dict[str, str]]]:
    """The Cryptomatte-like layers flowing into the node: base name -> {NN: {letter: Shuffle option}}."""
    shuffle = inner(node, "Rank0")
    found: dict[str, dict[int, dict[str, str]]] = {}
    if shuffle is None:
        return found
    for option in shuffle.getParam("outputR").getOptions():
        match = _RANK_LAYER.match(str(option))
        if match:
            base, number, letter = match.group(1), int(match.group(2)), match.group(3).upper()
            found.setdefault(base, {}).setdefault(number, {})[letter] = str(option)
    return {base: ranks for base, ranks in found.items() if 0 in ranks and all(len(r) == 4 for r in ranks.values())}


def _crypto_like(name: str) -> bool:
    return "crypto" in name.lower()


def upstream_file(node: Any, app: Any) -> str | None:
    """The file of the Read feeding the node's Source (through any nodes and Groups), at the current frame."""
    seen = set()
    queue = [node.getInput(0)]
    while queue:
        current = queue.pop(0)
        if current is None or id(current) in seen or len(seen) > 200:
            continue
        seen.add(id(current))
        filename = current.getParam("filename")
        if filename is not None and current.isReaderNode():
            pattern = _expand(str(filename.get()), app)
            if pattern:
                return data.nearest_frame_file(pattern, _frame(app, current))
        for child in compat.children(current) if _is_group(current) else []:
            if child.isReaderNode():
                queue.append(child)
        queue.extend(current.getInput(i) for i in range(max(current.getMaxInputCount(), 0)))
    return None


def _is_group(node: Any) -> bool:
    try:
        return bool(node.getChildren())
    except Exception:  # noqa: BLE001
        return False


def _frame(app: Any, reader: Any) -> int:
    try:
        return int(app.timelineGetTime())
    except Exception:  # noqa: BLE001
        first = reader.getParam("firstFrame")
        return int(first.get()) if first is not None else 1


def _expand(pattern: str, app: Any) -> str:
    """Natron's project variables (``[Project]/renders/…``) replaced by their folders."""
    paths = compat.project_param(app, "projectPaths")
    value = str(paths.get()) if paths is not None else ""

    def variable(match: re.Match[str]) -> str:
        return compat.project_variable(value, match.group(1)) or match.group(0)

    return re.sub(r"\[([^\]]+)\]", variable, pattern).replace("\\", "/")


_MANIFESTS: dict[tuple[str, float, int], list[data.Cryptomatte]] = {}


def manifests(node: Any, app: Any) -> tuple[list[data.Cryptomatte], str]:
    """The Cryptomattes named by the manifest source (Manifest file, else the Read upstream), and a word on where
    they came from. Cached by file and modification time."""
    chosen = str(node.getParam("manifestFile").get() or "").strip()
    path = _expand(chosen, app) if chosen else upstream_file(node, app)
    if not path or not os.path.isfile(path):
        return [], (f"the manifest file {chosen} wasn't found" if chosen else "no Read with a file upstream")
    info = os.stat(path)
    key = (path, info.st_mtime, info.st_size)
    if key not in _MANIFESTS:
        try:
            if path.lower().endswith(".exr"):
                found = data.cryptomattes_in(path)
            else:
                found = [data.Cryptomatte("", "", data.read_manifest_file(path), path)]
        except (OSError, ValueError) as error:
            return [], f"{os.path.basename(path)} couldn't be read ({error})"
        _MANIFESTS.clear()
        _MANIFESTS[key] = found
    return _MANIFESTS[key], os.path.basename(path)


# --- Updating the inner nodes ---


def _set_if_changed(param: Any, value: Any) -> None:
    if param is not None and param.get() != value:
        param.setValue(value)


def refresh(node: Any, app: Any = None) -> dict[str, Any]:
    """Make the inner nodes match the controls: the layer, the list, the manifest. Returns what it found (for the
    status line and the tests)."""
    app = app or compat.active_app()
    name_inner_nodes(node)
    layers = stream_layers(node)
    cryptos, where = manifests(node, app)
    named = {c.name: c for c in cryptos if c.name}
    flat = next((c.manifest for c in cryptos if not c.name), None)  # a sidecar JSON: the same names for any layer
    names = [n for n in named if n in layers] + [n for n in layers if n not in named and _crypto_like(n)]
    current = str(node.getParam("layerName").get() or "")
    if current not in names and names:
        preferred = [n for n in names if re.search(r"object|primitive", n, re.I)]
        current = (preferred or names)[0]
        _set_if_changed(node.getParam("layerName"), current)
    _refresh_choice(node.getParam("cryptoLayer"), names, current)

    manifest = flat if flat is not None else (named[current].manifest if current in named else {})
    _refresh_choice(node.getParam("addName"), [ADD_NAME_FIRST, *sorted(manifest)], ADD_NAME_FIRST)
    entries = data.parse_list(str(node.getParam("matteList").get() or ""))
    selection = data.select(entries, manifest)
    missing_patterns = [e for e in selection.unmatched if data.is_pattern(e.lstrip("-"))]
    result = {"layer": current, "layers": names, "ids": selection.ids, "names": selection.names,
              "unmatched": selection.unmatched, "manifest": len(manifest), "where": where, "updated": False}

    if current not in layers:
        _status(node, f"No {current or 'Cryptomatte'} layers in the input: connect a render with them "
                "(Natron's Read shows them in its layer list).")
        return result
    if missing_patterns and not manifest:
        _status(node, f"No manifest ({where}): wildcards can't be worked out, so the matte stays as it was. "
                "Give the render's beauty or its .json in Manifest file.")
        return result

    ranks = layers[current]
    pair = data.rank_pair_expression(selection.ids)
    for k in range(RANK_LAYERS):
        shuffle = inner(node, f"Rank{k}")
        expression = inner(node, f"Ranks{k}")
        used = k in ranks
        for letter in "RGBA":
            _set_option(shuffle.getParam(f"output{letter}"), ranks[k][letter] if used else "0")
        _set_if_changed(expression.getParam("expression"), pair if used else "0")
        _set_if_changed(expression.getParam("disableNode"), not used)
    _set_if_changed(inner(node, "Preview").getParam("expression"),
                    data.preview_expression(selection.ids))
    result["updated"] = True
    words = [f"{len(selection.ids)} in the matte" + (f" ({', '.join(selection.names[:3])}"
                                                      f"{'…' if len(selection.names) > 3 else ''})"
                                                      if selection.names else ""),
             f"{len(ranks) * 2} ranks"]
    if manifest:
        words.append(f"{len(manifest)} names in {where}")
    else:
        words.append(f"no manifest ({where}): plain names only")
    if selection.unmatched:
        words.append("matched nothing: " + ", ".join(selection.unmatched[:4]))
    _status(node, "; ".join(words) + ".")
    return result


def _refresh_choice(param: Any, options: list[str], current: str) -> None:
    if param is None:
        return
    shown = [str(o) for o in param.getOptions()]
    if options and shown != options:
        param.setOptions([(o, "") for o in options])
    if options and current in options:
        _set_if_changed(param, options.index(current))


def _status(node: Any, text: str) -> None:
    _set_if_changed(node.getParam("status"), text)


# --- What the artist does ---


def _entries(node: Any) -> list[str]:
    return data.parse_list(str(node.getParam("matteList").get() or ""))


def _write_entries(node: Any, entries: list[str]) -> None:
    _set_if_changed(node.getParam("matteList"), data.format_list(entries))


def _manifest_now(node: Any, app: Any) -> dict[str, int]:
    cryptos, _ = manifests(node, app)
    current = str(node.getParam("layerName").get() or "")
    for c in cryptos:
        if not c.name or c.name == current:
            return c.manifest
    return {}


def add_or_remove(node: Any, bits: int, add: bool, app: Any = None) -> str:
    """Put the object with ID ``bits`` in the list (or take it out), by its manifest name when it has one."""
    app = app or compat.active_app()
    manifest = _manifest_now(node, app)
    names = sorted(n for n, b in manifest.items() if b == bits)
    entry = names[0] if names else data.raw_entry(bits)
    entries = _entries(node)
    if add:
        if f"-{entry}" in entries:
            entries.remove(f"-{entry}")
        if bits not in data.select(entries, manifest).ids:
            entries.append(entry)
    else:
        entries = [e for e in entries if e != entry and data.select([e], manifest).ids != {bits}]
        if bits in data.select(entries, manifest).ids:  # still taken by a wildcard: leave it out explicitly
            entries.append(f"-{entry}")
    _write_entries(node, entries)
    refresh(node, app)
    return entry


def pick(node: Any, colour: tuple[float, float, float], add: bool, app: Any = None) -> str | None:
    """A colour picked from the preview: add or remove the object it stands for. Returns the entry, or None."""
    app = app or compat.active_app()
    bits = data.decode_preview(*colour)
    if bits is None:
        if not node.getParam("preview").get():
            node.getParam("preview").setValue(True)
            _status(node, "Preview is on now: Ctrl+click the object again.")
        elif any(colour):
            _status(node, "Nothing to pick there: pick inside an object (not on an edge), with the viewer at 100 % "
                    "or closer and Natron's Linear color pickers on (Preferences, Viewer).")
        return None
    manifest = _manifest_now(node, app)
    if manifest and bits not in set(manifest.values()):
        _status(node, "That colour isn't one of this layer's objects: pick inside an object, with Preview on.")
        return None
    return add_or_remove(node, bits, add, app)


def param_changed(thisParam: Any, thisNode: Any, thisGroup: Any, app: Any, userEdited: bool) -> None:  # noqa: N803
    """Natron's callback for the node's controls."""
    try:
        name = thisParam.getScriptName()
        if name in PICK_PARAMS:
            colour = tuple(float(thisParam.getValue(d)) for d in range(3))
            if any(colour):
                pick(thisNode, colour, name == "pickAdd", app)  # type: ignore[arg-type]
            return
        if not userEdited:
            return
        if name == "addName":
            options = [str(o) for o in thisParam.getOptions()]
            chosen = options[thisParam.get()] if 0 < thisParam.get() < len(options) else ""
            if chosen:
                entries = _entries(thisNode)
                if chosen not in entries:
                    _write_entries(thisNode, [*entries, chosen])
                thisParam.setValue(0)
            refresh(thisNode, app)
        elif name == "cryptoLayer":
            options = [str(o) for o in thisParam.getOptions()]
            if 0 <= thisParam.get() < len(options):
                _set_if_changed(thisNode.getParam("layerName"), options[thisParam.get()])
            refresh(thisNode, app)
        elif name == "clear":
            _write_entries(thisNode, [])
            refresh(thisNode, app)
        elif name == "reload":
            _MANIFESTS.clear()
            refresh(thisNode, app)
        elif name in ("matteList", "manifestFile"):
            refresh(thisNode, app)
    except Exception as error:  # noqa: BLE001  (a callback must never break Natron; say what went wrong instead)
        _safe_status(thisNode, f"Cryptomatte couldn't update: {error}")


def image_switch(node: Any) -> None:
    """The picture under the matte: the Image input when it's connected (a render whose Cryptomatte is in a file of
    its own), else the Source."""
    _set_if_changed(inner(node, "ImageIn").getParam("which"), 0 if node.getInput(1) is not None else 1)


def input_changed(inputIndex: int, thisNode: Any, thisGroup: Any, app: Any) -> None:  # noqa: N803
    """Natron's callback when an input is connected (also while a comp opens): the inner nodes' names, the picture
    to use, then the layers and the manifest. Headless (a farm render), the comp's saved inner values are kept, unless
    they're missing (a comp opened through the PyPlug's file, which rebuilds the inner nodes empty)."""
    try:
        name_inner_nodes(thisNode)
        image_switch(thisNode)
        if thisNode.getInput(0) is None:
            return
        empty = str(inner(thisNode, "Ranks0").getParam("expression").get()) == "0"
        if not compat.is_background() or (empty and _entries(thisNode)):
            refresh(thisNode, app)
    except Exception as error:  # noqa: BLE001
        _safe_status(thisNode, f"Cryptomatte couldn't update: {error}")


def _safe_status(node: Any, text: str) -> None:
    try:
        _status(node, text)
    except Exception:  # noqa: BLE001
        return
