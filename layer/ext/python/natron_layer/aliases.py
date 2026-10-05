# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Nuke's node names for Natron's nodes: the "Nuke" menu of the toolbar and Tab search.

Each alias is a small **toolset** PyPlug in ``ext/plugin/aliases/`` (Natron's PyPlug kind that makes nodes in the
graph instead of wrapping them in a Group). Typing a Nuke name in Tab search (``Copy  [Nuke]``) or picking it in the
toolbar's Nuke menu makes **Natron's own node**, set up the way the Nuke node behaves, named after it (``Copy1``)
and connected to the selected node. So a comp holds only plain Natron nodes: it opens and renders on any Natron,
the farm included, with or without this layer.

Only names Natron doesn't already use are aliased (Natron's Blur, Grade, Merge, Transform… are found by their own
names), so Tab search doesn't list everything twice.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from . import compat

ID_PREFIX = "layer.nuke."
COLOUR_PLANE = "uk.co.thefoundry.OfxImagePlaneColour"


@dataclasses.dataclass(frozen=True)
class Alias:
    nuke: str  # Nuke's node name, also the label and the new node's name (Copy1)
    menu: str  # Nuke's toolbar menu it's in (Channel, Keyer…)
    plugin: str  # the Natron plug-in it makes
    values: tuple[tuple[str, Any], ...] = ()  # parameters set on the new node (choices by option id)
    main_input: int | None = 0  # where the selected node is connected (None: not connected)
    note: str = ""  # how it differs from Nuke's node

    @property
    def plugin_id(self) -> str:
        return ID_PREFIX + self.nuke

    @property
    def grouping(self) -> str:
        return f"Nuke/{self.menu}"


ALIASES: tuple[Alias, ...] = (
    Alias(
        "Copy",
        "Channel",
        "net.sf.openfx.ShufflePlugin",
        (("outputA", f"A.{COLOUR_PLANE}.A"),),
        note="A Shuffle that keeps B's colour and takes A's alpha, like Copy's default (alpha to alpha). Pick other "
        "channels in its R, G, B, A menus.",
    ),
    Alias(
        "ShuffleCopy",
        "Channel",
        "net.sf.openfx.ShufflePlugin",
        note="Natron's Shuffle has both inputs (B and A) and every channel of each, which is what ShuffleCopy does.",
    ),
    Alias(
        "ChannelMerge",
        "Channel",
        "net.sf.openfx.MergePlugin",
        (
            ("operation", "screen"),
            ("OutputChannelsR", False),
            ("OutputChannelsG", False),
            ("OutputChannelsB", False),
            ("OutputChannelsA", True),
        ),
        note="A Merge working on alpha only, with screen (a + b - ab, ChannelMerge's union); B's colour passes.",
    ),
    Alias(
        "Keylight",
        "Keyer",
        "net.sf.openfx.PIK",
        (("screenType", "pick"),),
        note="Natron's PIK keyer with the screen colour picked by hand, Keylight's way of working. PIK is IBK-like, "
        "not Keylight's algorithm, so mattes differ.",
    ),
    Alias(
        "IBKGizmo",
        "Keyer",
        "net.sf.openfx.PIK",
        (("screenType", "green"),),
        note="PIK is Natron's IBK-inspired keyer; set Screen Type to blue for a blue screen. Feed a clean plate to "
        "its C input as IBKGizmo's c input.",
    ),
    Alias(
        "Glow",
        "Filter",
        "net.sf.cimg.CImgBloom",
        note="Natron's Bloom: a stack of growing blurs added together, close to Glow without its tolerance controls.",
    ),
    Alias(
        "Denoise",
        "Filter",
        "net.sf.openfx.DenoiseSharpen",
        note="Natron's DenoiseSharpen (wavelets). Analyse the noise first, as with Denoise.",
    ),
    Alias(
        "FilterErode",
        "Filter",
        "net.sf.cimg.CImgErode",
        note="Natron's Erode (CImg): a negative size dilates.",
    ),
    Alias("CornerPin2D", "Transform", "net.sf.openfx.CornerPinPlugin", note="Natron's CornerPin."),
    Alias("AdjustBBox", "Transform", "net.sf.openfx.AdjustRoDPlugin", note="Natron's AdjustRoD (Add Pixels)."),
    Alias(
        "CurveTool",
        "Image",
        "net.sf.openfx.ImageStatistics",
        note="Natron's ImageStatistics: min, max, mean and more over a rectangle, per frame or a sequence.",
    ),
    Alias(
        "TimeClip",
        "Time",
        "net.sf.openfx.FrameRange",
        note="Natron's FrameRange: frames outside the range held, black or looped.",
    ),
)

BY_NAME = {alias.nuke: alias for alias in ALIASES}


def available() -> list[Alias]:
    """The aliases whose Natron node this Natron has (feature check, not a version check)."""
    return [alias for alias in ALIASES if compat.has_plugin(alias.plugin)]


def make(name: str, app: Any = None, group: Any = None) -> Any:
    """Make the Natron node for Nuke's ``name`` in ``group`` (the project's top level by default), set up, named
    after it and fed by the selected node when there is exactly one. Returns the new node."""
    alias = BY_NAME[name]
    app = compat.active_app() if app is None else app
    selected = compat.selected_nodes(app)
    node = compat.create_node(app, alias.plugin, group)
    if node is None:
        raise RuntimeError(f"Natron couldn't make a {alias.plugin} node for {name}.")
    with _suppress():
        node.setScriptName(compat.unique_name(app, alias.nuke))
        node.setLabel(node.getScriptName())
    for param, value in alias.values:
        if not compat.set_node_value(node, param, value):
            raise RuntimeError(f"{name}: {alias.plugin} has no {param} taking {value!r} (the alias needs updating).")
    if len(selected) == 1 and alias.main_input is not None:
        source = selected[0]
        compat.connect(node, alias.main_input, source)
        with _suppress():
            x, y = source.getPosition()
            node.setPosition(x, y + 80)
    compat.select_only(app, node)
    return node


class _suppress:
    """Ignore what Natron refuses for cosmetic steps (a name taken, a position headless)."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, *_exc: object) -> bool:
        return True
