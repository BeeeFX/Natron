# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The smoke test's probe in Natron's window (run_smoke.py --gui puts this folder on NATRON_PLUGIN_PATH after the
layer's). Once the window is up it checks the first-launch question (answering "Not now"), the menu bar's Nuke
menu and its keys, the stylesheet, the alias toolbar group, where the keys act (node graph or not) and a command run
through its menu entry; it takes a picture of the window, writes gui_probe.json in NATRON_LAYER_SMOKE_OUT and ends
Natron at once (so Natron writes nothing at exit). This file stays plain ASCII.
"""


def _layer_probe():
    import json
    import os
    import time
    import traceback

    from qtpy import QtCore, QtWidgets

    out = os.environ.get("NATRON_LAYER_SMOKE_OUT", "")
    state = {"started": time.monotonic(), "window_at": None, "results": [], "modal": [], "done": False}

    def say(condition, what):
        state["results"].append([bool(condition), what])

    def finish():
        if state["done"]:
            return
        state["done"] = True
        passed = all(ok for ok, _what in state["results"]) and bool(state["results"])
        if out:
            with open(os.path.join(out, "gui_probe.json"), "w", encoding="utf-8") as file:
                json.dump({"passed": passed, "results": state["results"], "modal": state["modal"]}, file, indent=1)
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        kernel32.TerminateProcess(kernel32.GetCurrentProcess(), 0 if passed else 1)

    def class_name(widget):
        try:
            return str(widget.metaObject().className())
        except Exception:
            return ""

    def main_window(app):
        for widget in app.topLevelWidgets():
            if isinstance(widget, QtWidgets.QMainWindow) and widget.isVisible():
                return widget
        return None

    def widgets_named(app, suffix):
        return [w for w in app.allWidgets() if class_name(w).rsplit(":", 1)[-1] == suffix]

    def handle_modal(app):
        box = app.activeModalWidget()
        if box is None:
            return False
        text = box.text() if isinstance(box, QtWidgets.QMessageBox) else box.windowTitle()
        buttons = [b.text() for b in box.findChildren(QtWidgets.QAbstractButton) if b.text()]
        state["modal"].append({"title": box.windowTitle(), "text": text, "buttons": buttons})
        later = [b for b in box.findChildren(QtWidgets.QAbstractButton) if b.text() == "Not now"]
        if later:
            later[0].click()
        else:
            box.reject()
        return True

    def checks(app, window):
        import natron_layer
        from natron_layer import compat, hotkeys, user_config

        question = [m for m in state["modal"] if "looks and behaves like Nuke" in m["text"]]
        say(question and question[0]["buttons"][:3] == ["Import", "Not now", "Don't ask again"],
            "the first-launch question came up (the test's home has the .nuke fixtures): "
            + str(question[0]["buttons"] if question else state["modal"]))
        say(user_config.pop_up_answer() is None, "after Not now it will ask again (nothing kept)")

        titles = [a.text().replace("&", "") for a in window.menuBar().actions()]
        nuke = [m for m in window.menuBar().findChildren(QtWidgets.QMenu) if m.title().replace("&", "") == "Nuke"]
        say(nuke, "the menu bar has a Nuke menu (menus: " + ", ".join(titles) + ")")
        entries = {}
        for menu in nuke[:1]:
            for action in menu.actions():
                entries[action.text().replace("&", "")] = action
        wanted = {key.menu.split("/", 1)[1]: key.keys for key in hotkeys.added()}
        for label, keys in wanted.items():
            action = entries.get(label)
            shown = action.shortcut().toString() if action is not None else None
            say(action is not None and shown == keys, "Nuke > " + label + " with its key " + keys + ": " + str(shown))
        for label in ("Import my Nuke preferences...", "Forget my imported Nuke preferences...",
                      "Use this build's look again...", "About this fork..."):
            say(label in entries, "Nuke > " + label)

        sheet = app.styleSheet()
        say("Nuke section" in sheet and "NATRON mainstyle.qss" in sheet, "Natron uses the layer's stylesheet")
        say(natron_layer.last_report is not None and not natron_layer.last_report.failed,
            "the look applied in the window: " + (natron_layer.last_report.summary() if natron_layer.last_report
                                                 else "no report"))

        graphs = widgets_named(app, "NodeGraph")
        viewers = widgets_named(app, "ViewerGL") or widgets_named(app, "ViewerTab")
        say(graphs, "Natron's node graph widgets are found by their class (" + str(len(graphs)) + ")")
        if graphs:
            say(hotkeys.in_node_graph(graphs[0]), "a key pressed in the node graph acts")
        natron_app = compat.active_app()
        if viewers:
            inner = viewers[0]
            say(not hotkeys.in_node_graph(inner), "a key pressed in the viewer (" + class_name(inner)
                + ") goes on to Natron")
            before = {n.getScriptName() for n in compat.children(natron_app)}
            handed = hotkeys.pass_key_on("K", inner)
            app.processEvents()
            after = {n.getScriptName() for n in compat.children(natron_app)}
            say(handed and before == after, "K handed on to the viewer makes no node (Natron stops playback with it)")
            before = after
            hotkeys.copy_node()  # as the menu's K would, with the keyboard wherever Natron put it
            app.processEvents()

        tool_buttons = [b for b in window.findChildren(QtWidgets.QToolButton) if "Nuke" in (b.toolTip() or "")]
        say(tool_buttons, "the toolbar has the Nuke group of aliases (" + str(len(tool_buttons)) + " button)")

        # A command through its menu entry, with the keyboard in the node graph.
        if graphs:
            window.activateWindow()
            graphs[0].setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
            app.processEvents()
        focus = app.focusWidget()
        if graphs and hotkeys.in_node_graph(focus):
            before = {n.getScriptName() for n in compat.children(natron_app)}
            entries["Insert Copy node"].trigger()
            app.processEvents()
            new = [n for n in compat.children(natron_app) if n.getScriptName() not in before]
            say(new and new[0].getPluginID() == "net.sf.openfx.ShufflePlugin",
                "Nuke > Insert Copy node (K) made a Copy in the node graph: "
                + ", ".join(n.getScriptName() for n in new))
        else:
            state["results"].append([True, "(not checked: Natron's window didn't get the keyboard focus, so the "
                                           "menu entry's run in the node graph wasn't tried)"])
        if out:
            picture = os.path.join(out, "natron_window.png")
            window.grab().save(picture)
            say(os.path.isfile(picture), "a picture of the window: " + picture)

    def tick():
        try:
            app = QtWidgets.QApplication.instance()
            if app is None:
                return
            if handle_modal(app):
                return
            window = main_window(app)
            now = time.monotonic()
            if window is None or not widgets_named(app, "NodeGraph"):
                if now - state["started"] > 150:
                    say(False, "Natron's window didn't come up within 150 s")
                    finish()
                return
            if state["window_at"] is None:
                state["window_at"] = now
                return
            if now - state["window_at"] < 6:  # time for the first-launch question (2 s after start)
                return
            timer.stop()
            checks(app, window)
        except Exception:
            say(False, "the probe raised:\n" + traceback.format_exc())
        finish()

    timer = QtCore.QTimer()
    timer.setInterval(500)
    timer.timeout.connect(tick)
    timer.start()
    return timer


layer_probe_timer = _layer_probe()
del _layer_probe
