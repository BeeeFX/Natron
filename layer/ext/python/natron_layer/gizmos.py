# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The layer's gizmo pack: everyday tools Nuke artists reach for that Natron lacks, as our own Group PyPlugs.

Each is written here from Natron's own nodes (nothing derived from natron-plugins: their per-plug-in licences aren't
stated, see FORK.md), with the rules of ``gizmo_kit``: Natron's nodes only, plain expressions, fixed inner names, no
NatronGui. So a comp holding one renders on the farm, and opens as a plain Group on a Natron without the layer.

| Gizmo | Nuke's | Built from |
|---|---|---|
| Grain | Grain | Noise, per-channel CImg blurs, a response to the image's brightness |
| ZDefocus | ZDefocus | six depth slices blurred by CImg and put back together, weighted |
| EdgeExtend | EdgeExtend | the image's colour pushed out past its alpha by six growing blurs |
| ChromaticAberration | (a common gizmo) | three LensDistortion nodes, one per channel |
| Vignette | (a common gizmo) | a Radial fitted to the input's format, multiplied |
| STMapIdentity | (an Expression in Nuke) | two Ramps: R = (x + 0.5) / width, G = (y + 0.5) / height |

Natron already has, under Nuke's own names: VectorBlur (the fork's, motion vectors), Exposure (the fork's), Despill
(spill map mix, expand, respill colour, brightness), Shuffle and ShuffleCopy, so they aren't redone here; Copy and
ChannelMerge are the layer's aliases (``aliases.py``).

Each PyPlug in ``ext/plugin/gizmos/`` calls ``build`` with its name.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any

from . import compat
from .gizmo_kit import INPUT_FORMAT, Kit, channel

ID_PREFIX = "layer.gizmo."
VERSION = 1

BLUR = "net.sf.cimg.CImgBlur"
MERGE = "net.sf.openfx.MergePlugin"
SHUFFLE = "net.sf.openfx.ShufflePlugin"


@dataclasses.dataclass(frozen=True)
class Gizmo:
    name: str  # also the label and Nuke's name where Nuke has one
    menu: str  # Nuke's toolbar menu it's in
    summary: str  # one line, for the toolbar's tooltip and Tab search
    needs: tuple[str, ...]  # the Natron plug-ins it's built from (checked with getPluginIDs)
    build: Callable[[Kit], None]

    @property
    def plugin_id(self) -> str:
        return ID_PREFIX + self.name

    @property
    def grouping(self) -> str:
        return f"Nuke/{self.menu}"


# --- Grain ---


def _grain(kit: Kit) -> None:
    source = kit.input("Source")
    kit.integer("seed", "Seed", 134, help="Another number gives another grain.")
    kit.boolean("animated", "Animated", True, help="A new grain on every frame (off: the same grain on every frame).")
    kit.colour("size", "Size", (2.0, 1.8, 2.4), minimum=0.0, display=(0.0, 10.0),
               help="How big the grains are, in pixels, for red, green and blue.")
    kit.colour("intensity", "Intensity", (0.035, 0.03, 0.045), minimum=0.0, display=(0.0, 0.2),
               help="How strong the grain is, for red, green and blue: about the grain's standard deviation where "
               "the image is 1 (or everywhere with Response at 0).")
    kit.double("response", "Response", 0.5, minimum=0.0, maximum=1.0, display=(0.0, 1.0),
               help="0: the same grain everywhere; 1: grain in proportion to the image's value, none in the blacks, "
               "as on film.")
    noise = kit.node("net.sf.openfx.Noise", "Noise", (("extent", "default"),), [source], at=(0, 100))
    kit.expression(noise, "seed", "thisGroup.seed.get()")
    kit.expression(noise, "staticSeed", "not thisGroup.animated.get()")
    centred = kit.node("net.sf.openfx.AddPlugin", "Centre", (("value", (-0.5, -0.5, -0.5, 0.0)),), [noise],
                       at=(0, 160))
    previous = centred
    for number, letter in enumerate("RGB"):
        blur = kit.node(BLUR, f"Size{letter}", (("boundary", "nearest"), ("expandRoD", False)), [previous],
                        at=(0, 220 + 60 * number))
        kit.only_channels(blur, letter)
        kit.expression(blur, "size", f"thisGroup.size.getValue({number})", (0, 1))
        previous = blur
    # Blurring the noise lowers its spread about as 1 / size (measured on Natron's Noise and CImg blur), so the
    # strength is scaled back up by size: Intensity stays the grain's spread whatever its size.
    strength = kit.node("net.sf.openfx.MultiplyPlugin", "Strength", (("value", (1.0, 1.0, 1.0, 0.0)),), [previous],
                        at=(0, 420))
    kit.expression(strength, "value",
                   "max(3.46, 5.0 * thisGroup.size.getValue(dimension)) * thisGroup.intensity.getValue(dimension)",
                   (0, 1, 2))
    response = kit.node("net.sf.openfx.GradePlugin", "Response", (("clampBlack", True),), [source], at=(200, 420))
    kit.only_channels(response, "RGB")
    kit.expression(response, "multiply", "thisGroup.response.get()", (0, 1, 2))
    kit.expression(response, "offset", "1.0 - thisGroup.response.get()", (0, 1, 2))
    shaped = kit.node(MERGE, "ByResponse", (("operation", "multiply"), ("OutputChannelsA", False)),
                      [strength, response], at=(0, 480))
    added = kit.node(MERGE, "AddGrain", (("operation", "plus"), ("OutputChannelsA", False), ("bbox", "b")),
                     [source, shaped], at=(200, 540))
    kit.alias("mix", "Mix", added, "mix", help="0: the image without grain.")
    kit.output(added)


# --- ZDefocus ---

ZDEFOCUS_SLICES = 6
BLUR_FILTERS = ("quasigaussian", "gaussian", "box", "triangle", "quadratic")  # CImg Blur's own, in its order


def _zdefocus(kit: Kit) -> None:
    source = kit.input("Source")
    depth = kit.node(SHUFFLE, "Depth", (("outputR", channel("B", "A")), ("outputA", "1")), [source], at=(200, 80))
    kit.alias("depthChannel", "Depth channel", depth, "outputR",
              help="The channel holding the depth (depth.Z of a CG render: it's picked when such an input is "
              "connected).")
    for letter in "GB":
        kit.expression(depth, f"output{letter}", "thisNode.outputR.get()")
    kit.double("focalPoint", "Focal point", 1.0, display=(0.0, 100.0),
               help="The depth that stays sharp (in the depth channel's units).")
    kit.double("depthOfField", "Depth of field", 0.0, minimum=0.0, display=(0.0, 50.0),
               help="How deep the sharp zone is around the focal point.")
    kit.double("size", "Size", 10.0, minimum=0.0, display=(0.0, 100.0),
               help="Blur, in pixels, per unit of depth away from the sharp zone.")
    kit.double("maximum", "Maximum", 20.0, minimum=0.0, display=(0.0, 100.0), help="The largest blur, in pixels.")
    kit.choice("blurFilter", "Filter", BLUR_FILTERS, 1, help="The blur's shape (CImg Blur's filters; no bladed "
               "bokeh).")
    kit.choice("output", "Output", ("result", "focal plane setup"), 0,
               help="Focal plane setup shows the blur as grey: black is sharp, white is the maximum.")
    focal = kit.node("net.sf.openfx.ConstantPlugin", "FocalPoint", (("extent", "default"),), [depth], at=(400, 80))
    kit.expression(focal, "color", "thisGroup.focalPoint.get()", (0, 1, 2))
    distance = kit.node(MERGE, "Distance", (("operation", "difference"),), [depth, focal], at=(200, 140))
    amount = kit.node("net.sf.openfx.GradePlugin", "BlurAmount", (("clampBlack", True), ("clampWhite", True)),
                      [distance], at=(200, 200))
    kit.only_channels(amount, "RGB")
    scale = "thisGroup.size.get() / max(thisGroup.maximum.get(), 1e-6)"
    kit.expression(amount, "multiply", scale, (0, 1, 2))
    kit.expression(amount, "offset", f"-0.5 * thisGroup.depthOfField.get() * {scale}", (0, 1, 2))
    last = ZDEFOCUS_SLICES - 1
    slices, weights = [], []
    for k in range(ZDEFOCUS_SLICES):
        x = 600.0 + 160 * k
        # Keyer's luminance key is 0 at its centre and 1 a softness away, in straight lines: inverted, a tent
        # around this slice's blur, and the six tents add up to 1 everywhere.
        key = kit.node("net.sf.openfx.KeyerPlugin", f"Key{k}", (
            ("mode", "luminance"), ("luminanceMath", "max"), ("center", k / last), ("toleranceLower", 0.0),
            ("toleranceUpper", 0.0), ("softnessLower", -1.0 / last), ("softnessUpper", 1.0 / last)),
            [amount], at=(x, 260))
        spread = kit.node(SHUFFLE, f"Matte{k}", [(f"output{c}", channel("B", "A")) for c in "RGBA"], [key],
                          at=(x, 320))
        weight = kit.node("net.sf.openfx.Invert", f"Weight{k}", (), [spread], at=(x, 380))
        part = kit.node(MERGE, f"Slice{k}", (("operation", "multiply"),), [source, weight], at=(x, 440))
        if k == 0:
            slices.append(part)
            weights.append(weight)
            continue
        size = f"thisGroup.maximum.get() * {k / last!r}"
        for name, stream, out in ((f"BlurSlice{k}", part, slices), (f"BlurWeight{k}", weight, weights)):
            blur = kit.node(BLUR, name, (("boundary", "nearest"), ("expandRoD", False)), [stream],
                            at=(x, 500 if out is slices else 560))
            kit.only_channels(blur, "RGBA")
            kit.expression(blur, "size", size, (0, 1))
            kit.expression(blur, "filter", "thisGroup.blurFilter.get()")
            out.append(blur)
    total = kit.node(MERGE, "Sum", (("operation", "plus"),), _merge_inputs(slices), at=(600, 640))
    weight_total = kit.node(MERGE, "Weights", (("operation", "plus"),), _merge_inputs(weights), at=(800, 640))
    result = kit.node(MERGE, "Result", (("operation", "divide"),), [weight_total, total], at=(700, 700))
    switch = kit.node("net.sf.openfx.switchPlugin", "OutputSwitch", (), [result, amount], at=(700, 760))
    kit.expression(switch, "which", "thisGroup.output.get()")
    kit.output(switch)
    kit.group.getParam("onInputChanged").setValue("natron_layer.gizmos.zdefocus_input_changed")


def _merge_inputs(streams: list[Any]) -> list[Any]:
    """Merge's inputs for B, A, A2, A3…: 0 is B, 1 is A, 2 is the mask, 3 onwards A2, A3…"""
    found: list[Any] = [streams[0], streams[1] if len(streams) > 1 else None, None]
    found.extend(streams[2:])
    return found


def zdefocus_input_changed(inputIndex: int, thisNode: Any, thisGroup: Any, app: Any) -> None:  # noqa: N803
    """Natron's callback the first time ZDefocus gets an input: when it has a depth.Z, use it (Nuke's ZDefocus reads
    depth.Z by default). The callback then takes itself off the node, so a saved comp names nothing of the layer's
    (a Natron without the layer would otherwise complain it can't find it)."""
    try:
        if thisNode.getInput(0) is None:
            return
        param = thisNode.getParam("depthChannel")
        options = list(param.getOptions())
        current = options[param.get()] if 0 <= param.get() < len(options) else ""
        depth = [o for o in options if o.startswith("B.") and o.lower().endswith(".z") and "depth" in o.lower()]
        if current == channel("B", "A") and depth:
            param.setValue(options.index(depth[0]))
        thisNode.getParam("onInputChanged").setValue("")
    except Exception:  # noqa: BLE001  (a callback must never break Natron)
        return


# --- EdgeExtend ---

EDGE_EXTEND_STEPS = 6


def _edge_extend(kit: Kit) -> None:
    source = kit.input("Source")
    kit.double("size", "Size", 1.0, minimum=0.0, display=(0.0, 4.0),
               help="How far the colour reaches: the six fills blur by 2, 4 … 64 pixels times Size.")
    kit.integer("erode", "Erode", 0, minimum=0, display=(0, 10),
                help="Shrink the alpha by this many pixels first, to leave a dark or light fringe out.")
    kit.boolean("premultiply", "Premultiply", False,
                help="Off: the extended colour with the input's alpha, unpremultiplied (premultiply it to get the "
                "input back). On: multiplied by the alpha.")
    straight = kit.node("net.sf.openfx.Unpremult", "Unpremult", (), [source], at=(0, 80))
    eroded = kit.node("net.sf.cimg.CImgErode", "Erode", (), [straight], at=(0, 140))
    kit.only_channels(eroded, "A")
    kit.expression(eroded, "size", "max(1, thisGroup.erode.get())", (0, 1))
    kit.expression(eroded, "disableNode", "thisGroup.erode.get() <= 0")
    premult = kit.node("net.sf.openfx.Premult", "Premult", (), [eroded], at=(0, 200))
    fills = []
    for j in range(EDGE_EXTEND_STEPS):
        x = 200.0 + 160 * j
        blur = kit.node(BLUR, f"Blur{j}", (("boundary", "black"), ("expandRoD", False)), [premult], at=(x, 260))
        kit.only_channels(blur, "RGBA")
        kit.expression(blur, "size", f"{2.0 * 2**j!r} * thisGroup.size.get()", (0, 1))
        colour = kit.node("net.sf.openfx.Unpremult", f"Fill{j}", (), [blur], at=(x, 320))
        reach = kit.node("net.sf.openfx.GradePlugin", f"Reach{j}", (
            ("multiply", (1.0, 1.0, 1.0, 8.0)), ("clampBlack", True), ("clampWhite", True)), [colour], at=(x, 380))
        kit.only_channels(reach, "A")
        fills.append(kit.node("net.sf.openfx.Premult", f"FillPremult{j}", (), [reach], at=(x, 440)))
    layered = fills[-1]
    for j in range(EDGE_EXTEND_STEPS - 2, -1, -1):
        layered = kit.node(MERGE, f"Over{j}", (("operation", "over"),), [layered, fills[j]],
                           at=(200.0 + 160 * j, 500))
    original = kit.node(MERGE, "OverOriginal", (("operation", "over"),), [layered, premult], at=(0, 560))
    alpha = kit.node(SHUFFLE, "KeepAlpha", (
        ("outputR", channel("B", "R")), ("outputG", channel("B", "G")), ("outputB", channel("B", "B")),
        ("outputA", channel("A", "A"))), [original, source], at=(0, 620))
    result = kit.node("net.sf.openfx.Premult", "PremultResult", (), [alpha], at=(0, 680))
    kit.expression(result, "disableNode", "not thisGroup.premultiply.get()")
    kit.output(result)


# --- ChromaticAberration ---


def _chromatic_aberration(kit: Kit) -> None:
    source = kit.input("Source")
    kit.double("amount", "Amount", 0.003, display=(0.0, 0.02),
               help="How far the colours split towards the edges (a lens distortion per channel, centred).")
    kit.double("red", "Red", 1.0, display=(-2.0, 2.0), help="Red's share of the amount (negative: inwards).")
    kit.double("green", "Green", 0.0, display=(-2.0, 2.0), help="Green's share of the amount.")
    kit.double("blue", "Blue", -1.0, display=(-2.0, 2.0), help="Blue's share of the amount.")
    previous = source
    for number, (letter, share) in enumerate((("R", "red"), ("G", "green"), ("B", "blue"))):
        lens = kit.node("net.sf.openfx.LensDistortion", f"Shift{letter}", (("model", "nuke"),), [previous],
                        at=(0, 80 + 60 * number))
        kit.only_channels(lens, letter)
        kit.expression(lens, "k1", f"thisGroup.amount.get() * thisGroup.{share}.get()")
        kit.expression(lens, "disableNode", f"abs(thisGroup.amount.get() * thisGroup.{share}.get()) < 1e-12")
        previous = lens
    kit.output(previous)


# --- Vignette ---


def _vignette(kit: Kit) -> None:
    source = kit.input("Source")
    kit.double("amount", "Amount", 0.3, minimum=0.0, maximum=1.0, display=(0.0, 1.0),
               help="How much darker the edges get (1: black).")
    kit.double("softness", "Softness", 1.0, minimum=0.0, maximum=1.0, display=(0.0, 1.0),
               help="How gradual the falloff is, from the edge of the ellipse inwards.")
    kit.double("scale", "Scale", 1.4, minimum=0.01, display=(0.2, 3.0),
               help="The ellipse's size against the input's format (1: touching its edges; above 1 the corners "
               "darken only partly).")
    # Both colours opaque: Radial lays its ramp over its source, which must not show through.
    falloff = kit.node("net.sf.openfx.Radial", "Falloff", (
        ("extent", "size"), ("expandRoD", False), ("color0", (0.7, 0.7, 0.7, 1.0)), ("color1", (1.0, 1.0, 1.0, 1.0))),
        [source], at=(200, 80))
    kit.expression(falloff, "color0", "1.0 - thisGroup.amount.get()", (0, 1, 2))
    kit.expression(falloff, "softness", "thisGroup.softness.get()")
    kit.expression(falloff, "bottomLeft",
                   f"(lambda f: ((f.x1 + f.x2) if dimension == 0 else (f.y1 + f.y2)) * 0.5 - ((f.x2 - f.x1) "
                   f"if dimension == 0 else (f.y2 - f.y1)) * 0.5 * thisGroup.scale.get())({INPUT_FORMAT})", (0, 1))
    kit.expression(falloff, "size",
                   f"(lambda f: ((f.x2 - f.x1) if dimension == 0 else (f.y2 - f.y1)) * thisGroup.scale.get())"
                   f"({INPUT_FORMAT})", (0, 1))
    darkened = kit.node(MERGE, "Darken", (("operation", "multiply"), ("OutputChannelsA", False), ("bbox", "b")),
                        [source, falloff], at=(0, 140))
    kit.output(darkened)


# --- STMapIdentity ---


def _stmap_identity(kit: Kit) -> None:
    source = kit.input("Source", "Format")
    kit.boolean("pixelCentres", "Pixel centres", True,
                help="On: (x + 0.5) / width, the pixel's centre, as Nuke's and Natron's STMap read it. Off: x / width.")
    # Each expression reads one of the group's controls: Natron then rewrites it when the gizmo is renamed.
    shift = "(0.0 if thisGroup.pixelCentres.get() else 0.5)"
    ramps = []
    for name, letter, colour in (("RampU", "x", (1.0, 0.0, 0.0, 1.0)), ("RampV", "y", (0.0, 1.0, 0.0, 1.0))):
        ramp = kit.node("net.sf.openfx.Ramp", name, (
            ("type", "linear"), ("color0", (0.0, 0.0, 0.0, 1.0)), ("color1", colour)), [source],
            at=(200 * len(ramps), 80))
        kit.expression(ramp, "point0", f"(lambda f: f.x1 if dimension == 0 else f.y1)({INPUT_FORMAT}) + {shift}",
                       (0, 1))
        end = "f.x2 if dimension == 0 else f.y1" if letter == "x" else "f.x1 if dimension == 0 else f.y2"
        kit.expression(ramp, "point1", f"(lambda f: {end})({INPUT_FORMAT}) + {shift}", (0, 1))
        ramps.append(ramp)
    both = kit.node(MERGE, "Both", (("operation", "plus"), ("bbox", "b")), ramps, at=(100, 140))
    stmap = kit.node(SHUFFLE, "STMap", (
        ("outputR", channel("B", "R")), ("outputG", channel("B", "G")), ("outputB", "0"), ("outputA", "1")),
        [both], at=(100, 200))
    kit.output(stmap)


GIZMOS: tuple[Gizmo, ...] = (
    Gizmo("Grain", "Draw", "Film grain per channel, sized in pixels, following the image's brightness.",
          ("net.sf.openfx.Noise", BLUR, "net.sf.openfx.AddPlugin", "net.sf.openfx.MultiplyPlugin",
           "net.sf.openfx.GradePlugin", MERGE), _grain),
    Gizmo("ZDefocus", "Filter", "Defocus by depth: sharp at the focal point, blurred away from it.",
          (SHUFFLE, "net.sf.openfx.ConstantPlugin", MERGE, "net.sf.openfx.GradePlugin", "net.sf.openfx.KeyerPlugin",
           "net.sf.openfx.Invert", BLUR, "net.sf.openfx.switchPlugin"), _zdefocus),
    Gizmo("EdgeExtend", "Filter", "Push a premultiplied image's colour out past its alpha, to fix fringes.",
          ("net.sf.openfx.Unpremult", "net.sf.cimg.CImgErode", "net.sf.openfx.Premult", BLUR,
           "net.sf.openfx.GradePlugin", MERGE, SHUFFLE), _edge_extend),
    Gizmo("ChromaticAberration", "Filter", "Split the colours towards the edges, as a lens does.",
          ("net.sf.openfx.LensDistortion",), _chromatic_aberration),
    Gizmo("Vignette", "Draw", "Darken the edges with an ellipse fitted to the input's format.",
          ("net.sf.openfx.Radial", MERGE), _vignette),
    Gizmo("STMapIdentity", "Transform", "An ST map of the input's format: R = (x + 0.5) / width, G = (y + 0.5) / "
          "height, for STMap and lens distortion maps.", ("net.sf.openfx.Ramp", MERGE, SHUFFLE), _stmap_identity),
)

BY_NAME = {gizmo.name: gizmo for gizmo in GIZMOS}


def available() -> list[Gizmo]:
    """The gizmos whose Natron nodes this Natron has (feature check, not a version check)."""
    return [gizmo for gizmo in GIZMOS if all(compat.has_plugin(p) for p in gizmo.needs)]


# The colour of Nuke's menu each gizmo is in: Natron's own preference for that class of node (the look sets it).
MENU_COLOURS = {"Filter": "filterNodesColor", "Draw": "drawNodesColor", "Transform": "transformNodesColor"}


def build(name: str, app: Any, group: Any) -> Any:
    """Fill ``group`` (the Group Natron made for the PyPlug) with gizmo ``name``. Returns the group."""
    gizmo = BY_NAME[name]
    kit = Kit(app, group, "controls", name)
    gizmo.build(kit)
    kit.finish()
    colour = compat.setting_value(MENU_COLOURS.get(gizmo.menu, "defaultNodeColor"))
    if isinstance(colour, tuple) and len(colour) >= 3:
        group.setColor(*colour[:3])  # shown in Natron's window only (a node has no colour headless)
    return group


def make(name: str, app: Any = None) -> Any:
    """A new gizmo ``name`` at the project's top level, fed by the selected node when there is exactly one (what
    Tab search does). Returns the node."""
    gizmo = BY_NAME[name]
    app = compat.active_app() if app is None else app
    selected = compat.selected_nodes(app)
    node = compat.create_node(app, gizmo.plugin_id)
    if node is None:
        raise RuntimeError(f"Natron couldn't make {gizmo.plugin_id}.")
    if len(selected) == 1:
        compat.connect(node, 0, selected[0])
    return node
