# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""What the gizmos are built with: a Natron Group filled with Natron's own nodes, its controls on the Group, the
inner nodes driven by plain Python expressions (``thisGroup.size.get()``).

The rules every gizmo keeps, so that a comp holding one opens and renders anywhere:

- **Only Natron's own nodes inside** (openfx-misc, CImg and Natron's built-in ones), checked with ``getPluginIDs``.
- **Expressions use Natron's names only** (``thisGroup``, ``thisNode``, ``frame``, ``dimension``), never the layer's
  modules: Natron saves a Group PyPlug's inner nodes with the comp, and where the layer's PyPlug file isn't found it
  opens the node as a plain Group with them (Engine/NodeGroupSerialization.cpp), so the farm and a Natron without the
  layer render it the same.
- **Every expression reads at least one of the group's controls** (``thisGroup.<control>.get()``): Natron compiles an
  expression with the group's name in it and recompiles it when the group is renamed only if it reads one of its
  parameters (checked on the fork: an expression reading only the input's format kept the old name).
- **Inner nodes keep fixed names** (``Noise``, ``SizeR``…): when Natron opens a comp it builds the gizmo again and then
  gives each inner node its saved values by name. Renaming one in a later version loses those values.
- No NatronGui: the gizmos render headless (NatronRenderer, the farm).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from . import compat

INPUT = "fr.inria.built-in.Input"
OUTPUT = "fr.inria.built-in.Output"
COLOUR = "uk.co.thefoundry.OfxImagePlaneColour"


class GizmoError(RuntimeError):
    """A node or a parameter the gizmo needs isn't in this Natron (the gizmo needs updating)."""


def channel(side: str, letter: str, layer: str = COLOUR) -> str:
    """A Shuffle option: ``channel("B", "A")`` is B's alpha, ``channel("B", "Z", "depth")`` is B's depth.Z."""
    return f"{side}.{layer}.{letter}"


class Kit:
    """Fills ``group`` (the Group Natron made for the PyPlug, or any Group) for ``app``."""

    def __init__(self, app: Any, group: Any, page: str = "controls", page_label: str = "Controls") -> None:
        self.app = app
        self.group = group
        self._inputs: list[Any] = []
        self._column = 0
        self.page = compat.add_user_param(group, "page", page, page_label)
        self.page_name = page

    # --- Nodes ---

    def node(self, plugin_id: str, name: str, values: Sequence[tuple[str, Any]] = (), inputs: Sequence[Any] = (),
             at: tuple[float, float] | None = None) -> Any:
        """A node of ``plugin_id`` named ``name`` inside the group, set up and connected (``inputs[n]`` to input
        n; None leaves an input free)."""
        node = compat.create_node(self.app, plugin_id, self.group)
        if node is None:
            raise GizmoError(f"Natron couldn't make a {plugin_id} node.")
        node.setScriptName(name)
        node.setLabel(name)
        self.set(node, values)
        for number, source in enumerate(inputs):
            if source is not None:
                self.connect(node, number, source)
        if at is not None:
            node.setPosition(*at)
        return node

    def set(self, node: Any, values: Sequence[tuple[str, Any]]) -> None:
        for name, value in values:
            if not compat.set_node_value(node, name, value):
                raise GizmoError(f"{node.getPluginID()} has no {name} taking {value!r}.")

    def only_channels(self, node: Any, letters: str) -> None:
        """Let ``node`` process only the channels in ``letters`` (``"R"``, ``"A"``, ``"RGB"``); the others pass."""
        for letter in "RGBA":
            compat.set_node_value(node, f"NatronOfxParamProcess{letter}", letter in letters)

    def input(self, name: str, label: str | None = None, optional: bool = False, mask: bool = False) -> Any:
        """The group's next input, named ``name`` (Natron shows the Input node's label on the group's arrow). The
        first one is the group's own Input1 when Natron made one."""
        node = None
        if not self._inputs:
            node = compat.child_by_plugin(self.group, INPUT)
        if node is None:
            node = compat.create_node(self.app, INPUT, self.group)
        node.setScriptName(name)
        node.setLabel(label or name)
        if optional:
            compat.set_node_value(node, "optional", True)
        if mask:
            compat.set_node_value(node, "isMask", True)
        node.setPosition(len(self._inputs) * 200.0, 0.0)
        self._inputs.append(node)
        return node

    def output(self, source: Any) -> Any:
        node = compat.child_by_plugin(self.group, OUTPUT) or compat.create_node(self.app, OUTPUT, self.group)
        self.connect(node, 0, source)
        return node

    def connect(self, node: Any, number: int, source: Any) -> None:
        if not compat.connect(node, number, source):
            raise GizmoError(f"{node.getScriptName()} input {number} wouldn't take {source.getScriptName()}.")

    # --- The group's controls ---

    def _param(self, kind: str, name: str, label: str, help: str, alpha: bool = False) -> Any:  # noqa: A002
        param = compat.add_user_param(self.group, kind, name, label, alpha)
        if help:
            param.setHelp(help)
        self.page.addParam(param)
        return param

    def double(self, name: str, label: str, default: float, minimum: float | None = None,
               maximum: float | None = None, display: tuple[float, float] | None = None,
               help: str = "") -> Any:  # noqa: A002
        param = self._param("double", name, label, help)
        self._limits(param, [default], minimum, maximum, display)
        return param

    def integer(self, name: str, label: str, default: int, minimum: int | None = None, maximum: int | None = None,
                display: tuple[int, int] | None = None, help: str = "") -> Any:  # noqa: A002
        param = self._param("int", name, label, help)
        self._limits(param, [default], minimum, maximum, display)
        return param

    def colour(self, name: str, label: str, default: Sequence[float], minimum: float | None = None,
               maximum: float | None = None, display: tuple[float, float] | None = None,
               help: str = "") -> Any:  # noqa: A002
        param = self._param("color", name, label, help, alpha=len(default) == 4)
        self._limits(param, list(default), minimum, maximum, display)
        return param

    def boolean(self, name: str, label: str, default: bool, help: str = "") -> Any:  # noqa: A002
        param = self._param("bool", name, label, help)
        param.setDefaultValue(bool(default))
        param.restoreDefaultValue()
        return param

    def choice(self, name: str, label: str, options: Sequence[str], default: int = 0,
               help: str = "") -> Any:  # noqa: A002
        param = self._param("choice", name, label, help)
        param.setOptions([(option, "") for option in options])
        param.setDefaultValue(default)
        param.restoreDefaultValue()
        return param

    def alias(self, name: str, label: str, node: Any, target: str, help: str = "") -> Any:  # noqa: A002
        """A control on the group that is ``node``'s own ``target`` parameter (Natron's alias: the same options,
        the same value)."""
        inner = node.getParam(target)
        if inner is None:
            raise GizmoError(f"{node.getPluginID()} has no {target}.")
        kind = {"ChoiceParam": "choice", "DoubleParam": "double", "IntParam": "int", "BooleanParam": "bool",
                "ColorParam": "color", "Double2DParam": "double2d"}[type(inner).__name__]
        alpha = kind == "color" and inner.getNumDimensions() == 4
        dimensions = inner.getNumDimensions()
        # Natron's alias gives the inner parameter the new control's value: start the control at the inner value.
        saved = [inner.get()] if kind in ("choice", "bool") else [inner.getValue(d) for d in range(dimensions)]
        param = self._param(kind, name, label, help, alpha=alpha)
        if kind == "choice":
            param.setOptions([(option, "") for option in inner.getOptions()])
        for dimension, value in enumerate(saved):
            if kind in ("choice", "bool"):
                param.setDefaultValue(value)
                param.restoreDefaultValue()
            else:
                param.setDefaultValue(value, dimension)
                param.restoreDefaultValue(dimension)
        if not compat.make_alias(param, inner):
            raise GizmoError(f"{name} couldn't be made {node.getScriptName()}.{target}'s alias.")
        for dimension, value in enumerate(saved):
            current = inner.get() if kind in ("choice", "bool") else inner.getValue(dimension)
            if current != value:
                if kind in ("choice", "bool"):
                    inner.setValue(value)
                else:
                    inner.setValue(value, dimension)
        return param

    @staticmethod
    def _limits(param: Any, defaults: list[float], minimum: float | None, maximum: float | None,
                display: tuple[float, float] | None) -> None:
        for dimension, value in enumerate(defaults):
            if minimum is not None:
                param.setMinimum(minimum, dimension)
            if maximum is not None:
                param.setMaximum(maximum, dimension)
            if display is not None:
                param.setDisplayMinimum(display[0], dimension)
                param.setDisplayMaximum(display[1], dimension)
            param.setDefaultValue(value, dimension)
            param.restoreDefaultValue(dimension)

    # --- Expressions ---

    def expression(self, node: Any, name: str, text: str, dimensions: Sequence[int] = (0,)) -> None:
        """``text`` on ``node``'s ``name``, for each of ``dimensions`` (``dimension`` holds the one evaluated)."""
        param = node.getParam(name)
        if param is None:
            raise GizmoError(f"{node.getPluginID()} has no {name}.")
        for dimension in dimensions:
            if not compat.set_expression(param, text, dimension):
                raise GizmoError(f"Natron refused the expression on {node.getScriptName()}.{name}: {text}")

    def finish(self) -> None:
        compat.refresh_user_params(self.group, [self.page_name, "Node"])


# The format of the gizmo's first input (x1, y1, x2, y2), in an expression: the format of the node feeding the group;
# when that node is itself a Group (another gizmo), its region of definition, because Natron reports a Group's
# format as the project's (checked on the fork) while it computes its region through it; with nothing connected,
# the project's format. Expressions are cached per frame by Natron, so after the input changes to another format the
# value updates on the next frame shown (or when the comp opens again).
INPUT_FORMAT = ("(lambda n: thisGroup.getOutputFormat() if n is None else (n.getRegionOfDefinition(frame, view) "
                "if n.getChildren() else n.getOutputFormat()))(thisGroup.getInput(0))")
