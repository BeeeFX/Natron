# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The Nuke preferences reader and the layer's config file, with any Python 3.10+ and no Natron:

    python layer/tests/smoke/test_nuke_prefs.py

(also run by run_smoke.py first). The Nuke files are the hand-written ones in fixtures/nuke_home/.nuke: the reader
hasn't met a real Nuke preferences file yet.
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAYER = HERE.parents[1]
sys.path.insert(0, str(LAYER / "ext" / "python"))
sys.path.insert(0, str(LAYER / "compat"))
sys.dont_write_bytecode = True

from natron_layer import nuke_prefs, user_config  # noqa: E402

HOME = HERE / "fixtures" / "nuke_home"


def fingerprints(folder: Path) -> dict[str, str]:
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.rglob("*")) if p.is_file()}


class Keys(unittest.TestCase):
    def test_nuke_spellings_become_qt_spellings(self) -> None:
        cases = {
            "ctrl+b": "Ctrl+B",
            "Ctrl+Shift+B": "Ctrl+Shift+B",
            "shift+ctrl+b": "Ctrl+Shift+B",
            "^b": "Ctrl+B",
            "#c": "Alt+C",
            "^+k": "Ctrl+Shift+K",
            "+x": "Shift+X",
            "M": "M",
            "b": "B",
            "shift+d": "Shift+D",
            "alt+shift+k": "Alt+Shift+K",
            "F5": "F5",
            "ctrl+return": "Ctrl+Return",
            "shift+.": "Shift+.",
            ".": ".",
            "+": "+",
        }
        for nuke, qt in cases.items():
            with self.subTest(nuke=nuke):
                self.assertEqual(nuke_prefs.qt_keys(nuke), qt)

    def test_what_isnt_a_key_is_refused(self) -> None:
        for text in ("", "ctrl+", "hyper+b", "ctrl+banana"):
            with self.subTest(text=text):
                self.assertIsNone(nuke_prefs.qt_keys(text))


class Preferences(unittest.TestCase):
    def test_the_newest_preferences_file_is_read(self) -> None:
        folder = nuke_prefs.nuke_folder(HOME)
        self.assertIsNotNone(folder)
        self.assertEqual(nuke_prefs.preferences_file(folder).name, "preferences14.0.nk")

    def test_knobs_are_read_with_quotes_and_braces(self) -> None:
        knobs = nuke_prefs.read_preferences(HOME / ".nuke" / "preferences14.0.nk")
        self.assertEqual(knobs["maxPanels"], "5")
        self.assertEqual(knobs["SnapToNode"], "false")
        self.assertEqual(knobs["DAGBackColor"], "0x3a3a3aff")
        self.assertEqual(knobs["label"], 'Written by hand for the layer\'s tests: {braces} and "quotes"')
        self.assertEqual(knobs["multiLineKnob"], "first line second { nested }")
        self.assertNotIn("first", knobs)

    def test_another_node_block_is_not_mistaken_for_preferences(self) -> None:
        text = "Root {\n maxPanels 3\n}\nPreferences {\n maxPanels 7\n}\n"
        self.assertEqual(nuke_prefs.node_knobs(text), {"maxPanels": "7"})
        self.assertEqual(nuke_prefs.node_knobs("Root {\n x 1\n}\n"), {})

    def test_values_convert(self) -> None:
        self.assertEqual(nuke_prefs.convert("0x3a3a3aff", "colour"), (0.2275, 0.2275, 0.2275))
        self.assertIs(nuke_prefs.convert("true", "bool"), True)
        self.assertIs(nuke_prefs.convert("0", "bool"), False)
        self.assertIsNone(nuke_prefs.convert("maybe", "bool"))
        self.assertEqual(nuke_prefs.convert("12.6", "int"), 13)
        self.assertEqual(nuke_prefs.convert("{2.5}", "float"), 2.5)


class MenuPy(unittest.TestCase):
    def setUp(self) -> None:
        self.shortcuts = nuke_prefs.read_menu_shortcuts((HOME / ".nuke" / "menu.py").read_text(encoding="utf-8"))

    def test_shortcuts_and_the_nodes_they_make(self) -> None:
        found = [(s.keys, s.nuke_class, s.name) for s in self.shortcuts]
        self.assertEqual(
            found,
            [
                ("Ctrl+B", "Blur", "Filter/Blur"),
                ("M", "Merge2", "Merge/Merge"),
                ("Alt+C", "Copy", "Channel/Copy"),
                ("Ctrl+Shift+E", "", "Edit/My tool"),
                ("Ctrl+Shift+K", "Keylight", "Keyer/Keylight"),
                ("Shift+D", "Dot", "Other/Dot"),
                ("Z", "ZDefocus2", "Filter/Fancy defocus"),
                ("Ctrl+B", "Blur", "Filter/Blur again"),
            ],
        )

    def test_a_menu_py_that_doesnt_parse_gives_nothing(self) -> None:
        self.assertEqual(nuke_prefs.read_menu_shortcuts("def broken(:\n"), [])


class Translation(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = nuke_prefs.plan_for(HOME, has_plugin=lambda _id: True, has_setting=lambda _name: True)

    def test_preferences_that_map(self) -> None:
        self.assertEqual(
            self.plan.settings,
            {
                "maxPanels": 5,
                "enableSnapToNode": False,
                "autoSaveDelay": 60,
                "maxUndoRedo": 50,
                "autoHideInputs": True,
            },
        )

    def test_shortcuts_that_map(self) -> None:
        taken = [(s["keys"], s["label"], s.get("replaces", "")) for s in self.plan.shortcuts]
        self.assertEqual(
            taken,
            [
                ("Ctrl+B", "Blur", ""),
                ("Alt+C", "Copy", "duplicate"),
                ("Ctrl+Shift+K", "Keylight", "clear all caches"),
                ("Shift+D", "Dot", ""),
            ],
        )
        copy = next(s for s in self.plan.shortcuts if s["label"] == "Copy")
        self.assertEqual((copy["alias"], copy["plugin"]), ("Copy", "net.sf.openfx.ShufflePlugin"))

    def test_everything_else_is_said_with_why(self) -> None:
        notes = "\n".join(f"{what}: {why}" for what, why in self.plan.notes)
        self.assertIn("UIFontSize: Natron reads its font before any script runs", notes)
        self.assertIn("DAGBackColor: Natron draws the node graph's background", notes)
        self.assertIn("echoAllCommands, label, multiLineKnob", notes)
        self.assertIn("M (Merge/Merge, menu.py line 8): already Natron's own key for that node", notes)
        self.assertIn("runs a Nuke command, not a node", notes)
        self.assertIn("Nuke's ZDefocus2 has no Natron equivalent", notes)
        self.assertIn("the same keys were already taken for Blur", notes)
        self.assertIn("in the node graph it takes the place of Natron's Alt+C (duplicate)", notes)
        self.assertEqual(len(self.plan.read), 2)
        self.assertIn("Preferences taken: maxPanels = 5", self.plan.report())

    def test_a_natron_without_the_node_or_preference(self) -> None:
        plan = nuke_prefs.plan_for(HOME, has_plugin=lambda pid: pid != "net.sf.cimg.CImgBlur",
                                   has_setting=lambda name: name != "maxUndoRedo")  # fmt: skip
        self.assertNotIn("maxUndoRedo", plan.settings)
        self.assertNotIn("Blur", [s["label"] for s in plan.shortcuts])
        notes = "\n".join(why for _what, why in plan.notes)
        self.assertIn("this Natron has no net.sf.cimg.CImgBlur", notes)
        self.assertIn("this Natron has no such preference", notes)

    def test_no_nuke_folder(self) -> None:
        with tempfile.TemporaryDirectory() as empty:
            plan = nuke_prefs.plan_for(empty)
            self.assertEqual((plan.read, plan.settings, plan.shortcuts), ([], {}, []))
            self.assertFalse(nuke_prefs.has_something(empty))
        self.assertTrue(nuke_prefs.has_something(HOME))

    def test_the_nuke_folder_is_only_read(self) -> None:
        before = fingerprints(HOME)
        nuke_prefs.plan_for(HOME)
        self.assertEqual(fingerprints(HOME), before)


class Config(unittest.TestCase):
    def test_answers_are_kept_in_the_layers_own_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            old = os.environ.get("NATRON_LAYER_CONFIG_DIR")
            os.environ["NATRON_LAYER_CONFIG_DIR"] = folder
            try:
                self.assertEqual(user_config.load(), {})
                self.assertIsNone(user_config.pop_up_answer())
                user_config.save({"pop_up": "later"})
                self.assertIsNone(user_config.pop_up_answer())  # "Not now" asks again
                user_config.save({"pop_up": "never", "nuke_import": {"settings": {"maxPanels": 5}}})
                self.assertEqual(user_config.pop_up_answer(), "never")
                self.assertEqual(user_config.nuke_import()["settings"], {"maxPanels": 5})
                self.assertEqual(user_config.load()["version"], user_config.VERSION)
                self.assertEqual(sorted(os.listdir(folder)), ["config.json"])
            finally:
                if old is None:
                    os.environ.pop("NATRON_LAYER_CONFIG_DIR", None)
                else:
                    os.environ["NATRON_LAYER_CONFIG_DIR"] = old


if __name__ == "__main__":
    unittest.main(verbosity=2)
