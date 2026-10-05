# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""make_toolsets.py's probe in Natron's window (on NATRON_PLUGIN_PATH after the layer's): once the window is up it
builds each recipe of natron_layer.toolset_recipes, selects its nodes, copies them with Natron's own Copy and saves
the clipboard's text as <recipe>.xml in NATRON_LAYER_SMOKE_OUT (the artist's clipboard is put back), writes
toolsets.json and ends Natron at once (so Natron writes nothing at exit). This file stays plain ASCII.
"""


def _toolset_maker():
    import json
    import os
    import time
    import traceback

    from qtpy import QtCore, QtWidgets

    out = os.environ.get("NATRON_LAYER_SMOKE_OUT", "")
    state = {"started": time.monotonic(), "window_at": None, "done": False}
    report = {"made": {}}

    def finish(code):
        if state["done"]:
            return
        state["done"] = True
        with open(os.path.join(out, "toolsets.json"), "w", encoding="utf-8") as file:
            json.dump(report, file, indent=1)
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        kernel32.TerminateProcess(kernel32.GetCurrentProcess(), code)

    def make_all():
        from natron_layer import compat, toolset_recipes

        app = compat.active_app()
        qt_app = QtWidgets.QApplication.instance()
        for title, recipe in toolset_recipes.RECIPES.items():
            made = list(recipe(app).values())
            qt_app.processEvents()  # the new nodes get their place in the node graph before being selected
            compat.select_nodes(app, made)
            qt_app.processEvents()
            selected = len(compat.selected_nodes(app))
            with compat.kept_clipboard():
                compat.copy_selected_nodes(app)
                qt_app.processEvents()
                text = compat.clipboard_text()
            for number, node in enumerate(made):
                # Natron's window keeps a deleted node (for its undo) and its name: free the name for the next recipe.
                node.setScriptName("Copied" + str(len(report["made"])) + "_" + str(number))
                node.destroy()
            if "<Clipboard" not in text:
                raise RuntimeError("Natron's Copy gave nothing for " + title + " (" + str(selected) + " of "
                                   + str(len(made)) + " nodes selected; clipboard text: " + repr(text[:200]) + ")")
            name = toolset_recipes.file_name(title)
            with open(os.path.join(out, name), "w", encoding="utf-8") as file:
                file.write(text)
            report["made"][title] = name

    def tick():
        try:
            app = QtWidgets.QApplication.instance()
            if app is None:
                return
            box = app.activeModalWidget()
            if box is not None:
                box.reject()
                return
            window = [w for w in app.topLevelWidgets() if isinstance(w, QtWidgets.QMainWindow) and w.isVisible()]
            now = time.monotonic()
            if not window:
                if now - state["started"] > 150:
                    report["error"] = "Natron's window didn't come up within 150 s"
                    finish(1)
                return
            if state["window_at"] is None:
                state["window_at"] = now
                return
            if now - state["window_at"] < 3:
                return
            timer.stop()
            make_all()
            finish(0)
        except Exception:
            report["error"] = traceback.format_exc()
            finish(1)

    timer = QtCore.QTimer()
    timer.setInterval(500)
    timer.timeout.connect(tick)
    timer.start()
    return timer


layer_toolset_maker_timer = _toolset_maker()
del _toolset_maker
