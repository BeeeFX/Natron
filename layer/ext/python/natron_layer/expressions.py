# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The expression snippet menu: Nuke-style recipes written as Natron's Python expressions (menu bar › Nuke ›
Expressions).

The recipes are in ``ext/presets/nuke_expressions.toml`` (each with how Nuke writes it). Picking one opens a small
window: the selected node's parameter, the recipe's fields (a frame, an amplitude…), the expression it makes (which
can be edited), then **Apply** (on every dimension of the parameter) or **Copy** (to paste it into Natron's own
expression editor). ``apply`` does the same from a script and headless (the smoke test checks each recipe's values).
"""

from __future__ import annotations

import dataclasses
import string
from typing import Any

from . import compat, paths

KINDS = ("DoubleParam", "IntParam", "BooleanParam", "ColorParam", "Double2DParam", "Double3DParam", "Int2DParam",
         "Int3DParam")


@dataclasses.dataclass(frozen=True)
class Recipe:
    id: str
    label: str
    nuke: str
    expression: str
    help: str = ""
    fields: tuple[tuple[str, str], ...] = ()

    def text(self, values: dict[str, Any] | None = None) -> str:
        """The expression with its fields filled in (defaults where ``values`` says nothing)."""
        filled = {name: default for name, default in self.fields}
        filled.update({k: str(v) for k, v in (values or {}).items()})
        names = {name for _, name, _, _ in string.Formatter().parse(self.expression) if name}
        missing = names - set(filled)
        if missing:
            raise ValueError(f"{self.id}: no value for {', '.join(sorted(missing))}")
        text = self.expression.format(**filled)
        compile(text, f"<{self.id}>", "eval")  # a recipe always makes valid Python
        return text


def recipes() -> list[Recipe]:
    import tomllib  # noqa: PLC0415

    with open(paths.preset("nuke_expressions.toml"), "rb") as file:
        data = tomllib.load(file)
    return [Recipe(r["id"], r["label"], r["nuke"], r["expression"], r.get("help", ""),
                   tuple((k, str(v)) for k, v in r.get("fields", {}).items())) for r in data.get("recipe", [])]


def by_id(recipe_id: str) -> Recipe:
    for recipe in recipes():
        if recipe.id == recipe_id:
            return recipe
    raise KeyError(recipe_id)


def apply(node: Any, param_name: str, recipe_id: str, values: dict[str, Any] | None = None,
          dimensions: list[int] | None = None, text: str | None = None) -> str:
    """Set recipe ``recipe_id`` (or ``text``) as the expression of ``node``'s ``param_name`` on ``dimensions`` (all
    of them by default). Returns the expression."""
    param = node.getParam(param_name)
    if param is None:
        raise ValueError(f"{node.getScriptName()} has no parameter {param_name}.")
    expression = text if text is not None else by_id(recipe_id).text(values)
    for dimension in dimensions if dimensions is not None else range(param.getNumDimensions()):
        if not compat.set_expression(param, expression, dimension):
            raise ValueError(f"Natron refused the expression on {node.getScriptName()}.{param_name}: {expression}")
    return expression


def animatable(node: Any) -> list[tuple[str, str]]:
    """(script name, label) of ``node``'s parameters an expression can drive."""
    found = []
    for param in node.getParams():
        if type(param).__name__ in KINDS and param.getIsAnimationEnabled() and param.getIsVisible():
            found.append((param.getScriptName(), param.getLabel() or param.getScriptName()))
    return found


# --- The menu and its window (interface only) ---


def _open(recipe_id: str) -> None:
    app = compat.active_app()
    selected = compat.selected_nodes(app)
    recipe = by_id(recipe_id)
    if len(selected) != 1:
        compat.information(f"Expression: {recipe.label}", "Select the one node whose parameter gets the expression.")
        return
    _Window.show(selected[0], recipe)


class _Window:
    """A small Qt window: parameter, fields, the expression (editable), Apply, Copy."""

    kept: list[Any] = []

    @classmethod
    def show(cls, node: Any, recipe: Recipe) -> None:
        qt = compat.qt_modules()
        if qt is None or qt.QtWidgets is None:
            return
        w = qt.QtWidgets
        dialog = w.QDialog(compat.application().activeWindow())
        dialog.setWindowTitle(f"Expression: {recipe.label}")
        form = w.QFormLayout(dialog)
        help_label = w.QLabel(f"{recipe.help}\nIn Nuke: {recipe.nuke}")
        help_label.setWordWrap(True)
        form.addRow(help_label)
        params = w.QComboBox()
        for name, label in animatable(node):
            params.addItem(f"{label} ({name})", name)
        form.addRow(f"{node.getScriptName()}'s parameter", params)
        fields = {}
        for name, default in recipe.fields:
            edit = w.QLineEdit(default)
            fields[name] = edit
            form.addRow(name.replace("_", " ").capitalize(), edit)
        expression = w.QLineEdit(recipe.text())
        form.addRow("Expression", expression)

        def refresh() -> None:
            try:
                expression.setText(recipe.text({k: e.text() for k, e in fields.items()}))
            except (ValueError, SyntaxError):
                pass

        for edit in fields.values():
            edit.textChanged.connect(lambda _text: refresh())
        buttons = w.QDialogButtonBox()
        apply_button = buttons.addButton("Apply", w.QDialogButtonBox.ButtonRole.AcceptRole)
        copy_button = buttons.addButton("Copy", w.QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton("Cancel", w.QDialogButtonBox.ButtonRole.RejectRole)
        form.addRow(buttons)

        def do_apply() -> None:
            try:
                apply(node, params.currentData(), recipe.id, text=expression.text())
            except ValueError as exc:
                compat.warning("Expression", str(exc))
                return
            dialog.accept()

        apply_button.clicked.connect(do_apply)
        copy_button.clicked.connect(lambda: compat.set_clipboard_text(expression.text()))
        buttons.rejected.connect(dialog.reject)
        cls.kept[:] = [dialog]
        dialog.show()


def install_menu() -> list[str]:
    """One menu entry per recipe (Nuke › Expressions › …). Interface only."""
    done = []
    for recipe in recipes():
        name = f"recipe_{recipe.id}"
        globals()[name] = (lambda rid: lambda: _open(rid))(recipe.id)
        if compat.add_menu_command(f"Nuke/Expressions/{recipe.label}", f"natron_layer.expressions.{name}"):
            done.append(recipe.label)
    return done
