# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The layer's menu (menu bar › Nuke) and the first-launch question about the artist's Nuke preferences.

Natron takes menu entries only from initGui.py, so ``install`` runs from there. Every dialog goes through ``ask``
and ``tell`` (Qt message boxes in Natron; plain functions in the tests), so the logic runs headless too.
"""

from __future__ import annotations

import datetime
from collections.abc import Callable
from typing import Any

from . import compat, hotkeys, look, nuke_prefs, paths, user_config

COMPARE_LINK = "https://github.com/BeeeFX/Natron/compare/RB-2.6...sng/main"

Ask = Callable[[str, str], bool]
Tell = Callable[[str, str], None]


# --- Dialogs ---


def _main_window() -> Any:
    app = compat.application()
    return app.activeWindow() if app is not None else None


def ask(title: str, text: str) -> bool:
    """A yes/no question; False headless."""
    qt = compat.qt_modules()
    if qt is None or qt.QtWidgets is None or compat.application() is None:
        return False
    box = qt.QtWidgets.QMessageBox(_main_window())
    box.setWindowTitle(title)
    box.setText(text)
    yes = box.addButton("Yes", qt.QtWidgets.QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Cancel", qt.QtWidgets.QMessageBox.ButtonRole.RejectRole)
    box.exec()
    return box.clickedButton() is yes


def tell(title: str, text: str) -> None:
    qt = compat.qt_modules()
    if qt is None or qt.QtWidgets is None or compat.application() is None:
        compat.say(f"{title}: {text}")
        return
    qt.QtWidgets.QMessageBox.information(_main_window(), title, text)


# --- The Nuke preferences import ---


def plan() -> nuke_prefs.Plan:
    return nuke_prefs.plan_for(
        has_plugin=compat.has_plugin, has_setting=lambda name: compat.setting(name) is not None
    )


def import_nuke_preferences(confirm: Ask | None = None, done: Tell | None = None) -> bool:
    """Menu › Nuke › Import my Nuke preferences…: read the artist's .nuke folder, say what maps, and only after their
    yes keep it in the layer's own config (never in Natron's settings, never in .nuke). Returns True when imported."""
    confirm = ask if confirm is None else confirm
    done = tell if done is None else done
    found = plan()
    if not found.read:
        done("Import my Nuke preferences", "No Nuke preferences were found (looked in your .nuke folder).")
        return False
    text = (
        "From your Nuke preferences:\n\n" + found.report() + "\n\n"
        "Use these in this Natron? Your .nuke folder isn't changed and Natron's own settings aren't written: they're "
        "kept in this build's own file, and a preference you set in Natron's Preferences window still wins."
    )
    if not confirm("Import my Nuke preferences", text):
        return False
    keep(found)
    report = look.apply(imported=found.settings)
    done(
        "Import my Nuke preferences",
        f"Done. {report.summary()}\n\nShortcuts from menu.py ({len(found.shortcuts)}) take effect when Natron starts "
        "again (menu bar › Nuke › My Nuke shortcuts).",
    )
    return True


def keep(found: nuke_prefs.Plan) -> None:
    data = user_config.load()
    data["nuke_import"] = {
        "when": datetime.datetime.now().isoformat(timespec="seconds"),
        "read": found.read,
        "settings": found.settings,
        "shortcuts": found.shortcuts,
        "notes": [list(note) for note in found.notes],
    }
    data["pop_up"] = "imported"
    user_config.save(data)


def forget_nuke_preferences(confirm: Ask | None = None, done: Tell | None = None) -> bool:
    """Menu › Nuke › Forget my imported Nuke preferences…: back to the build's look at the next start."""
    confirm = ask if confirm is None else confirm
    done = tell if done is None else done
    if not user_config.nuke_import():
        done("Forget my imported Nuke preferences", "Nothing was imported.")
        return False
    if not confirm("Forget my imported Nuke preferences", "Forget what was imported from your Nuke preferences? "
                   "This Natron goes back to its Nuke look when it starts again."):
        return False
    data = user_config.load()
    data.pop("nuke_import", None)
    user_config.save(data)
    done("Forget my imported Nuke preferences", "Forgotten: restart Natron to see the build's look again.")
    return True


def first_launch(choose: Callable[[str, list[str]], str] | None = None) -> str | None:
    """The first-launch question, only when the artist has Nuke preferences and hasn't answered for good. Returns
    the button chosen ("Import", "Not now", "Don't ask again"), or None when nothing was asked."""
    if user_config.pop_up_answer() is not None or not nuke_prefs.has_something():
        return None
    folder = nuke_prefs.nuke_folder()
    text = (
        "This Natron looks and behaves like Nuke by default.\n\n"
        f"Your own Nuke preferences are in {folder}. Import what maps to Natron (preferences and the node shortcuts "
        "of your menu.py)?\n\nNothing in your .nuke folder is changed. You can do it later from the menu bar: Nuke › "
        "Import my Nuke preferences."
    )
    buttons = ["Import", "Not now", "Don't ask again"]
    chosen = (choose or _choose)(text, buttons)
    if chosen == "Import":
        import_nuke_preferences(confirm=lambda _t, _x: True)
    elif chosen == "Don't ask again":
        data = user_config.load()
        data["pop_up"] = "never"
        user_config.save(data)
    return chosen


def _choose(text: str, buttons: list[str]) -> str:
    qt = compat.qt_modules()
    if qt is None or qt.QtWidgets is None or compat.application() is None:
        return "Not now"
    box = qt.QtWidgets.QMessageBox(_main_window())
    box.setWindowTitle("Your Nuke preferences")
    box.setText(text)
    made = [box.addButton(label, qt.QtWidgets.QMessageBox.ButtonRole.ActionRole) for label in buttons]
    box.exec()
    clicked = box.clickedButton()
    return next((label for label, button in zip(buttons, made, strict=True) if button is clicked), "Not now")


# --- The look ---


def reset_look(confirm: Ask | None = None, done: Tell | None = None, writer: Any = None) -> bool:
    """Menu › Nuke › Use this build's look again…: after the artist's yes, remove their own values of the look's
    preferences from Natron's settings (the only time the layer writes them), so the look applies."""
    confirm = ask if confirm is None else confirm
    done = tell if done is None else done
    stored = compat.StoredSettings(writer.target) if writer is not None else None
    own = look.own_values_in_the_way(stored)
    if not own:
        done("Use this build's look again", "Nothing of yours is in the way: this Natron already uses its Nuke look.")
        return False
    if not confirm(
        "Use this build's look again",
        "These preferences are your own in Natron's settings, so they're used instead of this build's Nuke look:\n\n"
        + ", ".join(own)
        + "\n\nRemove your values for them from Natron's settings so the Nuke look is used? Nothing else is touched.",
    ):
        return False
    writer = compat.SettingsWriter.of_natron() if writer is None else writer
    report = look.reset(writer, own)
    done("Use this build's look again", report.summary() + " Some colours show fully after a restart.")
    return True


def about(done: Tell | None = None) -> str:
    done = tell if done is None else done
    upstream = paths.read_upstream()
    base = upstream.get("upstream", {})
    tested = upstream.get("tested", {})
    text = (
        f"Natron {'.'.join(map(str, compat.version()))} with this fork's layer.\n\n"
        f"Based on Niik-l's {base.get('branch', 'RB-2.6')} ({base.get('tag', '?')}); the layer was last tested with "
        f"the {tested.get('release', '?')} release.\n\nWhat this fork adds: FORK.md in the repository, or every "
        f"change at once: {COMPARE_LINK}"
    )
    done("About this fork", text)
    return text


# --- Installing ---


def install() -> dict[str, list[str]]:
    """The menu bar's Nuke menu and keys, the imported shortcuts, and the first-launch question once Natron's
    window is up. Interface only (initGui.py)."""
    from . import expressions, skin, toolsets, workflow  # noqa: F401, PLC0415  (menu functions: natron_layer.<module>.<function>)

    done = {"keys": hotkeys.register()}
    done["imported"] = hotkeys.register_imported(user_config.nuke_import().get("shortcuts", []))
    done["workflow"] = workflow.install_menu()
    done["toolsets"] = toolsets.install_menu()
    done["expressions"] = expressions.install_menu()
    for grouping, function in (
        ("Nuke/Import my Nuke preferences...", "natron_layer.gui.import_nuke_preferences"),
        ("Nuke/Forget my imported Nuke preferences...", "natron_layer.gui.forget_nuke_preferences"),
        ("Nuke/Use this build's look again...", "natron_layer.gui.reset_look"),
        ("Nuke/Look/Natron's own look for me...", "natron_layer.skin.choose_natron_look"),
        ("Nuke/Look/Nuke look for me...", "natron_layer.skin.choose_nuke_look"),
        ("Nuke/About this fork...", "natron_layer.gui.about"),
    ):
        compat.add_menu_command(grouping, function)
    qt = compat.qt_modules()
    if qt is not None and compat.application() is not None:
        _when_window_is_up(qt)
    return done


_waiting: list[Any] = []


def _when_window_is_up(qt: Any) -> None:
    """Once Natron's main window exists: reload the stylesheet with the look's values (Natron loaded it before any
    startup script ran), then ask the first-launch question."""
    timer = qt.QtCore.QTimer()
    timer.setInterval(500)
    started = datetime.datetime.now()

    def look_for_window() -> None:
        app = compat.application()
        windows = [w for w in app.topLevelWidgets() if isinstance(w, qt.QtWidgets.QMainWindow) and w.isVisible()]
        waited = (datetime.datetime.now() - started).total_seconds()
        if not windows and waited < 300:
            return
        timer.stop()
        _waiting.clear()
        refresh_look()
        if windows:
            from . import skin  # noqa: PLC0415

            # once Natron has finished sizing its window (its splitters settle after the window shows)
            window = windows[0]
            qt.QtCore.QTimer.singleShot(1000, lambda: skin.polish(window))
        qt.QtCore.QTimer.singleShot(1500, first_launch)

    timer.timeout.connect(look_for_window)
    timer.start()
    _waiting.append(timer)  # kept alive until the window is up


def refresh_look() -> bool:
    """Natron loads its stylesheet (and the interface colours it carries) before any startup script runs and
    reloads it only when the setting changes while its window exists: set it again once the window is up."""
    import natron_layer  # noqa: PLC0415

    report = natron_layer.last_report
    if report is None or not (report.applied or report.imported):
        return False
    return compat.refresh_setting("stylesheetFile")
