# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The layer's checks inside Natron, run by run_smoke.py as ``NatronRenderer -t smoke_checks.py`` with the layer's
plug-in folder on NATRON_PLUGIN_PATH and Natron's caches, home and the layer's config in a temporary folder.

It checks: the layer loaded by its init.py in a clean session; the adapter's view of this Natron; the Nuke look set
for the session, the artist's own preferences left, the imported ones over the look; every alias registered and
making its Natron node; a small comp of alias nodes rendered and its pixels compared (values worked out by hand, and
each alias against the same Natron node set up by hand); the hotkeys' table and the commands' work; the Nuke
preferences import and the first-launch question with the hand-written fixtures; the look's reset into a settings
file standing in for Natron's. run_smoke.py then compares Natron's settings (the registry) before and after.
This file stays plain ASCII.
"""

import hashlib
import json
import os
import sys
import traceback

RESULTS = {"ok": 0, "failed": 0}
OUT = os.environ.get("NATRON_LAYER_SMOKE_OUT", "")
FIXTURE_HOME = os.environ.get("NATRON_LAYER_SMOKE_HOME", "")


def say(condition, what):
    if condition:
        RESULTS["ok"] += 1
        print("  ok  " + what, flush=True)
    else:
        RESULTS["failed"] += 1
        print("FAILED  " + what, flush=True)
    return bool(condition)


def close(values, expected, tolerance=0.002):
    return len(values) >= len(expected) and all(abs(a - b) <= tolerance for a, b in zip(values, expected))


def end(code):
    sys.stdout.flush()
    sys.stderr.flush()
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        kernel32.TerminateProcess(kernel32.GetCurrentProcess(), code)
    os._exit(code)


# --- 1. The layer in a clean session ---


def check_loaded():
    import __main__

    layer = getattr(__main__, "natron_layer", None) or sys.modules.get("natron_layer")
    say(layer is not None, "the layer was loaded by its init.py (natron_layer in Natron's main namespace)")
    if layer is None:
        return None
    from natron_layer import compat, paths

    say(paths.upstream_file().is_file(), "the layer found its files (upstream.toml) from its plug-in folder: "
        + str(paths.layer_root()))
    build = os.environ.get("NATRON_LAYER_SMOKE_PACKAGED", "")
    if build:
        inside = os.path.normcase(str(paths.layer_root())).startswith(os.path.normcase(build))
        say(inside and (paths.layer_root() / "BUILD.toml").is_file(),
            "a packaged build: the layer comes from the build itself (Resources/layer, with BUILD.toml), with nothing "
            "on NATRON_PLUGIN_PATH")
    say(compat.version()[:2] == (2, 6), "this is Natron 2.6: " + ".".join(map(str, compat.version())))
    say(compat.has_3d(), "with the fork's 3D workspace (feature check through getPluginIDs)")
    say(sys.version_info[:2] >= (3, 14), "its Python is " + sys.version.split()[0])
    qt = compat.qt_modules()
    say(qt is not None and qt.QtCore is not None, "Qt comes through qtpy (bundled with the fork): " + _qt_name())
    say(compat.is_background(), "headless (NatronRenderer)")
    return layer


def _qt_name():
    try:
        import qtpy

        return "qtpy " + qtpy.__version__ + " on " + qtpy.API_NAME
    except Exception as exc:
        return "no qtpy (" + str(exc) + ")"


def own_values():
    """The artist's stored Natron preferences, read independently from the layer (the registry on Windows)."""
    names = set()
    if os.name != "nt":
        return names
    import winreg

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\INRIA\Natron")
    except OSError:
        return names
    index = 0
    while True:
        try:
            name, _value, _kind = winreg.EnumValue(key, index)
        except OSError:
            break
        names.add(name)
        index += 1
    return names


# --- 2. The Nuke look ---


def check_look(layer):
    from natron_layer import compat, look

    report = layer.last_report
    say(report is not None, "the Nuke look was applied at start: " + (report.summary() if report else "no report"))
    if report is None:
        return
    wanted = look.load_look()
    say(not report.missing and not report.failed, "every preference of the look exists in this Natron and took")
    stored = own_values()
    expected_kept = sorted(n for n in wanted if any(k in stored for k in compat.stored_keys(n)))
    say(sorted(report.kept) == expected_kept,
        "exactly the artist's own stored preferences were left alone: " + (", ".join(expected_kept) or "none here"))
    qss = compat.setting_value("stylesheetFile")
    if "stylesheetFile" not in report.kept:
        say(str(qss).endswith("ext/qss/nuke.qss") and os.path.isfile(qss), "the stylesheet is the layer's nuke.qss")
    for name in ("readerColor", "defaultMergeColor", "selection"):
        if name in report.kept:
            continue
        say(close(compat.setting_value(name), wanted[name], 1e-4),
            name + " is the look's " + str(wanted[name]) + " for this session")
    for name in ("mergeConnectToA", "autoHideInputs", "writeUseDialog", "usePluginIcons"):
        if name not in report.kept:
            say(compat.setting_value(name) == wanted[name], name + " is " + str(wanted[name]))

    # Precedence: the artist's stored value over the imported Nuke preference over the look.
    panels = compat.setting("maxPanels")
    panels.setValue(7)
    snap = compat.setting("enableSnapToNode")
    second = look.apply(stored=compat.StoredSettings({"maxPanels": 3, "readerColor.r": 0.1}),
                        imported={"maxPanels": 25, "enableSnapToNode": False})
    say(panels.get() == 7 and "maxPanels" in second.kept, "a preference the artist stored isn't touched (maxPanels)")
    say("readerColor" in second.kept, "a colour counts as the artist's when any of its r, g, b is stored")
    say(snap.get() is False and "enableSnapToNode" in second.imported,
        "an imported Nuke preference wins over the look (enableSnapToNode off)")
    say(compat.stored_keys("readerColor") == ["readerColor.r", "readerColor.g", "readerColor.b"]
        and compat.stored_keys("maxPanels") == ["maxPanels"], "Natron's keys per preference (name, name.r ...)")
    look.apply()  # back to the session's look

    # A value set from Python with "Save settings on change" left on: run_smoke.py checks it isn't written.
    save = compat.setting("saveSettings")
    say(save.get() is True, "Natron's hidden Save settings on change is on again after the look")
    compat.setting("disconnectedArrowLength").setValue(compat.setting("disconnectedArrowLength").get() + 7)
    say(True, "a preference changed from Python with saving on (the registry is compared afterwards)")


# --- 3. The aliases ---


def check_aliases(app):
    from natron_layer import aliases, compat

    say(len(aliases.available()) == len(aliases.ALIASES), "every alias's Natron node exists in this Natron ("
        + str(len(aliases.ALIASES)) + ")")
    for alias in aliases.ALIASES:
        say(compat.has_plugin(alias.plugin_id), alias.nuke + " is registered as " + alias.plugin_id + " in "
            + alias.grouping)
        before = {n.getScriptName() for n in compat.children(app)}
        made = app.createNode(alias.plugin_id)
        new = [n for n in compat.children(app) if n.getScriptName() not in before]
        node = new[0] if len(new) == 1 else None
        say(made is None and node is not None and node.getPluginID() == alias.plugin
            and node.getScriptName().startswith(alias.nuke),
            "creating " + alias.nuke + " (a toolset) makes Natron's own " + alias.plugin + " named "
            + (node.getScriptName() if node else "?"))
        if node is not None:
            good = all(compat.param_value(node.getParam(p)) == v for p, v in alias.values)
            say(good, alias.nuke + " is set up as Nuke's: " + (", ".join(p + "=" + str(v) for p, v in alias.values)
                                                               or "Natron's defaults"))


def write_node(app, source, path):
    from natron_layer import compat

    writer = app.createWriter(path.replace("\\", "/"))
    compat.connect(writer, 0, source)
    for name, value in (("frameRange", "manual"), ("firstFrame", 1), ("lastFrame", 1), ("formatType", "input")):
        if writer.getParam(name) is not None:
            compat.set_node_value(writer, name, value)
    space_in = writer.getParam("ocioInputSpace")
    space_out = writer.getParam("ocioOutputSpace")
    if space_in is not None and space_out is not None:
        space_out.setValue(space_in.get())  # no colour conversion: the file holds the comp's values
        if writer.getParam("ocioOutputSpaceSet") is not None:
            compat.set_node_value(writer, "ocioOutputSpaceSet", True)
    return writer


def average(path):
    import OpenImageIO as oiio

    buf = oiio.ImageBuf(path)
    stats = oiio.ImageBufAlgo.computePixelStats(buf)
    return tuple(stats.avg)


def constant(app, rgba, name):
    from natron_layer import compat

    node = compat.create_node(app, "net.sf.openfx.ConstantPlugin")
    node.setScriptName(name)
    compat.set_node_value(node, "extent", "format")
    compat.set_node_value(node, "NatronParamFormatChoice", "square_256")
    node.getParam("color").setValue(rgba[0], 0)
    node.getParam("color").setValue(rgba[1], 1)
    node.getParam("color").setValue(rgba[2], 2)
    node.getParam("color").setValue(rgba[3], 3)
    return node


def render(app, node, path):
    writer = write_node(app, node, path)
    app.render(writer, 1, 1)
    frame = path.replace("####", "0001")
    return frame if os.path.isfile(frame) else None


def check_comp(app):
    from natron_layer import aliases, compat

    out = os.path.join(OUT, "renders")
    os.makedirs(out, exist_ok=True)
    plate_b = constant(app, (0.2, 0.4, 0.6, 1.0), "PlateB")
    plate_a = constant(app, (0.9, 0.1, 0.1, 0.25), "PlateA")
    copy = aliases.make("Copy", app)
    compat.connect(copy, 0, plate_b)
    compat.connect(copy, 1, plate_a)
    merge = aliases.make("ChannelMerge", app)
    compat.connect(merge, 0, copy)
    merge_a = merge.getInputLabel(1)
    compat.connect(merge, 1, plate_a)
    clip = aliases.make("TimeClip", app)
    compat.connect(clip, 0, merge)
    bbox = aliases.make("AdjustBBox", app)
    compat.connect(bbox, 0, clip)
    frame = render(app, bbox, os.path.join(out, "chain.####.exr"))
    say(frame is not None, "the comp of Nuke-named nodes (Copy, ChannelMerge, TimeClip, AdjustBBox) rendered")
    if frame is not None:
        values = average(frame)
        expected = (0.2, 0.4, 0.6, 0.25 + 0.25 - 0.25 * 0.25)
        say(close(values, expected), "its pixels: B's colour, A's alpha copied, alphas merged as a union ("
            + merge_a + " input): " + str(tuple(round(v, 4) for v in values)))

    # Each alias renders like Natron's own node set up by hand.
    source = compat.create_node(app, "net.sf.openfx.CheckerBoardPlugin")
    compat.set_node_value(source, "extent", "format")
    compat.set_node_value(source, "NatronParamFormatChoice", "square_256")
    for name in ("Keylight", "IBKGizmo", "Glow", "FilterErode", "CornerPin2D", "CurveTool", "ShuffleCopy"):
        alias = aliases.BY_NAME[name]
        made = aliases.make(name, app)
        by_hand = compat.create_node(app, alias.plugin)
        for param, value in alias.values:
            compat.set_node_value(by_hand, param, value)
        for node in (made, by_hand):
            compat.connect(node, 0, source)
            if name == "IBKGizmo":
                compat.connect(node, 2, source)  # PIK's C input: a clean plate (IBKGizmo's c)
        a = render(app, made, os.path.join(out, name + "_alias.####.exr"))
        b = render(app, by_hand, os.path.join(out, name + "_natron.####.exr"))
        same = a is not None and b is not None and close(average(a), average(b), 1e-5)
        say(same, name + " renders the same pixels as Natron's " + alias.plugin.rsplit(".", 1)[-1]
            + " set up by hand")


# --- 4. The hotkeys ---


class FakeNode:
    def __init__(self, x, y):
        self.position = (x, y)

    def getPosition(self):
        return self.position

    def setPosition(self, x, y):
        self.position = (x, y)


def check_hotkeys(app):
    from natron_layer import compat, hotkeys

    table = hotkeys.table()
    added = hotkeys.added()
    say(len(table) > 30 and {k.keys for k in added} == {"I", "K", "\\", "Shift+Y", "Alt+B"},
        "the hotkey table reads (" + str(len(table)) + " Nuke keys; added: " + ", ".join(k.keys for k in added) + ")")
    say(all(callable(getattr(hotkeys, k.command, None)) and k.menu.startswith("Nuke/") for k in added),
        "every added key has its command and its place in the Nuke menu")
    say(all(k.status in ("same", "added", "differs", "missing") for k in table), "every key says how it stands")
    say(all(compat.key_and_modifiers(k.keys) is not None for k in added), "Qt reads every added key")
    nodes = [FakeNode(103, 50), FakeNode(220, 24), FakeNode(-60, -13)]
    moved = hotkeys.snap_nodes(nodes)
    say(moved == 2 and [n.position for n in nodes] == [(110, 48), (220, 24), (-110, -24)],
        "snap to grid puts nodes on the 110 x 24 grid: " + str([n.position for n in nodes]))
    plate = constant(app, (0.5, 0.5, 0.5, 1.0), "InfoPlate")
    grade = compat.create_node(app, "net.sf.openfx.GradePlugin")
    compat.connect(grade, 0, plate)
    grade.getParam("white").setValue(2.0, 0)
    text = hotkeys.describe(grade, app)
    say("net.sf.openfx.GradePlugin" in text and "InfoPlate" in text, "node info reads a node: "
        + text.replace("\n", " | ")[:160])
    copy = hotkeys.branch_copy(app, grade)
    say(copy is not None and copy.getPluginID() == grade.getPluginID() and copy.getInput(0) is not None
        and copy.getInput(0).getScriptName() == "InfoPlate" and abs(copy.getParam("white").getValue(0) - 2.0) < 1e-6,
        "duplicate and branch: a copy with the same values, fed by the same input")
    say(hotkeys.in_node_graph() is True, "headless, a command acts (there's no other widget to hand the key to)")


# --- 5. The Nuke preferences import and the first-launch question ---


def fingerprints(folder):
    found = {}
    for base, _dirs, files in os.walk(folder):
        for name in files:
            path = os.path.join(base, name)
            with open(path, "rb") as file:
                found[path] = hashlib.sha256(file.read()).hexdigest()
    return found


def check_import():
    from natron_layer import compat, gui, look, nuke_prefs, user_config

    say(bool(FIXTURE_HOME) and nuke_prefs.has_something(), "the test's home holds the hand-written .nuke fixtures")
    before = fingerprints(os.path.join(FIXTURE_HOME, ".nuke"))
    told = []
    asked = []

    def choose(text, buttons):
        asked.append((text, buttons))
        return "Import"

    answer = gui.first_launch(choose=choose)
    say(answer == "Import" and asked and "looks and behaves like Nuke" in asked[0][0],
        "the first-launch question is asked when Nuke preferences exist: " + str(asked[0][1] if asked else None))
    imported = user_config.nuke_import()
    say(imported.get("settings", {}).get("maxPanels") == 5 and user_config.pop_up_answer() == "imported",
        "Import keeps what maps in the layer's own file: " + str(imported.get("settings")))
    norm = lambda p: os.path.normcase(os.path.normpath(str(p)))  # noqa: E731
    say(norm(user_config.path()).startswith(norm(os.environ.get("NATRON_LAYER_CONFIG_DIR", "?"))),
        "that file is in the layer's config folder (the test's): " + str(user_config.path()))
    say([s["keys"] for s in imported.get("shortcuts", [])] == ["Ctrl+B", "Alt+C", "Ctrl+Shift+K", "Shift+D"],
        "the menu.py shortcuts that map: " + ", ".join(s["keys"] + " " + s["label"] for s in imported["shortcuts"]))
    say(compat.setting_value("maxPanels") == 5 or "maxPanels" in look.apply().kept,
        "and the imported preferences are used for this session (maxPanels 5)")
    say(gui.first_launch(choose=choose) is None and len(asked) == 1, "once answered, the question isn't asked again")
    say(fingerprints(os.path.join(FIXTURE_HOME, ".nuke")) == before, "nothing in the .nuke folder changed")
    confirmed = gui.import_nuke_preferences(confirm=lambda title, text: told.append(text) or True,
                                            done=lambda title, text: told.append(text))
    say(confirmed and any("Preferences taken" in t for t in told), "the menu's import shows the plan before its yes")
    refused = gui.import_nuke_preferences(confirm=lambda title, text: False, done=lambda title, text: None)
    say(refused is False, "and does nothing on a no")
    forgot = gui.forget_nuke_preferences(confirm=lambda t, x: True, done=lambda t, x: None)
    say(forgot and not user_config.nuke_import(), "Forget my imported Nuke preferences empties the import")
    data = user_config.load()
    data.pop("pop_up", None)
    user_config.save(data)
    say(gui.first_launch(choose=lambda t, b: "Don't ask again") == "Don't ask again"
        and user_config.pop_up_answer() == "never", "Don't ask again is kept")
    look.apply()


# --- 6. The look's reset, into a settings file standing in for Natron's ---


def check_reset():
    from natron_layer import compat, gui

    path = os.path.join(OUT, "stand_in_natron.ini")
    writer = compat.SettingsWriter.ini_file(path)
    writer.set("readerColor.r", 0.1)
    writer.set("readerColor.g", 0.1)
    writer.set("readerColor.b", 0.1)
    writer.set("maxPanels", 3)
    writer.set("autoProxyScrubbing", False)
    writer.sync()
    questions = []
    done = gui.reset_look(confirm=lambda t, text: questions.append(text) or True, done=lambda t, x: None,
                          writer=writer)
    left = compat.StoredSettings(writer.target)
    say(done and questions and "readerColor" in questions[0] and "maxPanels" in questions[0],
        "Use this build's look again asks first, naming the artist's own values in the way")
    say(not left.contains("readerColor.r") and not left.contains("maxPanels") and left.contains("autoProxyScrubbing"),
        "and removes only those (a preference outside the look stays)")
    say(gui.reset_look(confirm=lambda t, x: True, done=lambda t, x: None, writer=writer) is False,
        "with nothing in the way it says so and changes nothing")
    text = gui.about(done=lambda t, x: None)
    say("RB-2.6...sng/main" in text and "2.6" in text, "About this fork names the base and the compare link")


def main():
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    try:
        app = None
        import NatronEngine

        app = NatronEngine.natron.getActiveInstance()
        layer = check_loaded()
        if layer is not None:
            for check in (lambda: check_look(layer), lambda: check_aliases(app), lambda: check_comp(app),
                          lambda: check_hotkeys(app), check_import, check_reset):
                try:
                    check()
                except Exception:
                    say(False, "a check raised:\n" + traceback.format_exc())
    except Exception:
        say(False, "the checks couldn't run:\n" + traceback.format_exc())
    if OUT:
        with open(os.path.join(OUT, "smoke_results.json"), "w", encoding="utf-8") as file:
            json.dump(RESULTS, file)
    print("SMOKE CHECKS " + ("PASSED" if RESULTS["failed"] == 0 else "FAILED") + " (" + str(RESULTS["ok"])
          + " ok, " + str(RESULTS["failed"]) + " failed)", flush=True)
    end(0 if RESULTS["failed"] == 0 else 1)


main()
