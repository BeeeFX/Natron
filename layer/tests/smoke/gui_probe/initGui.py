# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The smoke test's probe in Natron's window (run_smoke.py --gui puts this folder on NATRON_PLUGIN_PATH after the
layer's). Once the window is up it checks the first-launch question (answering "Not now"), the menu bar's Nuke
menu and its keys (the tools' entries included), the stylesheet, the alias toolbar group, where the keys act (node
graph or not) and a command run through its menu entry; then the tools: each gizmo made by its ID, Select similar
colour, each studio ToolSet pasted with Natron's own paste (the clipboard put back), Save selection as ToolSet, an
expression's window, and the pasted comp saved for the run without the layer (project_jobs_gui.json). It takes a
picture of the window, writes gui_probe.json in NATRON_LAYER_SMOKE_OUT and ends Natron at once (so Natron writes
nothing at exit). This file stays plain ASCII.
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

        def collect(menu, prefix):
            for action in menu.actions():
                label = prefix + action.text().replace("&", "")
                if action.menu() is not None:
                    collect(action.menu(), label + "/")
                else:
                    entries[label] = action

        for menu in nuke[:1]:
            collect(menu, "")
        wanted = {key.menu.split("/", 1)[1]: key.keys for key in hotkeys.added()}
        for label, keys in wanted.items():
            action = entries.get(label)
            shown = action.shortcut().toString() if action is not None else None
            say(action is not None and shown == keys, "Nuke > " + label + " with its key " + keys + ": " + str(shown))
        for label in ("Import my Nuke preferences...", "Forget my imported Nuke preferences...",
                      "Use this build's look again...", "About this fork..."):
            say(label in entries, "Nuke > " + label)
        from natron_layer import expressions, toolsets, workflow

        missing = [g.split("/", 1)[1] for g, _f in workflow.MENU if g.split("/", 1)[1] not in entries]
        say(not missing, "Nuke > the workflow scripts' entries (" + ", ".join(g.split("/", 1)[1] for g, _f
                                                                             in workflow.MENU) + ")"
            + (": missing " + str(missing) if missing else ""))
        studio = ["ToolSets/Studio/" + t.name for t in toolsets.all_toolsets() if t.place == "Studio"]
        wanted_sets = studio + ["ToolSets/Paste a ToolSet...", "ToolSets/Save selection as ToolSet..."]
        say(studio and all(w in entries for w in wanted_sets), "Nuke > ToolSets: " + ", ".join(wanted_sets))
        recipes = ["Expressions/" + r.label for r in expressions.recipes()]
        say(all(r in entries for r in recipes), "Nuke > Expressions: one entry per recipe (" + str(len(recipes)) + ")")
        state["entries"] = entries

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
        try:
            with compat.kept_clipboard():  # the PC's clipboard is given back after the pastes' checks
                tools(app, natron_app)
        except Exception:
            say(False, "the tools' checks in the window raised:\n" + traceback.format_exc())
        try:
            skin_checks(app, window)
        except Exception:
            say(False, "the skin's checks in the window raised:\n" + traceback.format_exc())
        try:
            drawing_checks(app, natron_app)
        except Exception:
            say(False, "the node graph's drawing checks raised:\n" + traceback.format_exc())
        if out:
            picture = os.path.join(out, "natron_window.png")
            window.grab().save(picture)
            say(os.path.isfile(picture), "a picture of the window: " + picture)

    def drawing_checks(app, natron_app):
        """The node graph's drawing in this fork's builds (core patch 0001): a node in error is drawn in the error
        colour, unlike a node without one, and says why under the mouse; a Read whose file is missing is in error at
        once (postage stamps off, nothing renders it)."""
        import NatronEngine
        from qtpy import QtCore

        settings = NatronEngine.natron.getSettings()
        if settings.getParam("nodeErrorTint") is None:
            return  # Niik-l's plain release: Natron's own drawing
        graph = widgets_named(app, "NodeGraph")[0]
        area = graph.mapToScene(graph.viewport().rect()).boundingRect()
        missing = natron_app.createReader("C:/no/such/folder/smoke_missing.####.exr")
        normal = natron_app.createNode("net.sf.openfx.GradePlugin")
        for node, dx in ((missing, 0), (normal, 220)):
            for i in range(node.getMaxInputCount()):
                if node.getInput(i) is not None:
                    node.disconnectInput(i)
            node.setPosition(area.left() + 80 + dx, area.top() + 80)
        app.processEvents()

        def redness(node):
            x, y = node.getPosition()
            w, h = node.getSize()
            top_left = graph.mapFromScene(QtCore.QPointF(x + w * 0.15, y + h * 0.2))
            bottom_right = graph.mapFromScene(QtCore.QPointF(x + w * 0.85, y + h * 0.8))
            image = graph.viewport().grab(QtCore.QRect(top_left, bottom_right)).toImage()
            total, count = [0, 0, 0], 0
            for i in range(image.width()):
                for j in range(image.height()):
                    c = image.pixelColor(i, j)
                    total[0], total[1], total[2] = total[0] + c.red(), total[1] + c.green(), total[2] + c.blue()
                    count += 1
            if not count:
                return 0.0
            return total[0] / count - (total[1] + total[2]) / (2.0 * count)

        red_missing, red_normal = redness(missing), redness(normal)
        say(red_missing > 60 and red_normal < 30,
            "a node in error is drawn in the error colour (a Read of a missing file: redness %d; a Grade: %d)"
            % (red_missing, red_normal))
        x, y = missing.getPosition()
        w, h = missing.getSize()
        point = graph.mapFromScene(QtCore.QPointF(x + w / 2.0, y + h / 2.0))
        tips = [item.toolTip() for item in graph.items(point) if item.toolTip()]
        say(any("not found" in t for t in tips), "and says why under the mouse: " + (tips[0][:80] if tips else "none"))
        missing.destroy()
        normal.destroy()

    def fingerprint(image, side=16):
        from qtpy import QtGui

        small = image.convertToFormat(QtGui.QImage.Format.Format_ARGB32).scaled(
            side, side, QtCore.Qt.AspectRatioMode.IgnoreAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation)
        values = []
        for y in range(side):
            for x in range(side):
                c = small.pixelColor(x, y)
                a = c.alphaF()
                values.append((c.redF() * a, c.greenF() * a, c.blueF() * a, a))
        return values

    def distance(one, two):
        return sum(abs(p - q) for a, b in zip(one, two) for p, q in zip(a, b)) / (4.0 * len(one))

    def skin_checks(app, window):
        """The skin in the window: the font Qt uses wherever Natron asks for Droid Sans, and the icon buttons of the
        toolbar, viewer, playback bar and panels showing our pictures, none still showing Natron's picture among
        those we drew; a two-state button keeps ours when clicked."""
        from qtpy import QtGui
        from natron_layer import paths, skin

        report = skin.last_report
        say(report is not None and not report.off and report.icons >= 100 and not report.missing,
            "the skin was installed before the window: " + (report.summary() if report else "no report"))
        family = QtGui.QFontInfo(QtGui.QFont("Droid Sans", 10)).family()
        say(family == "DejaVu Sans" and app.font().family() == "DejaVu Sans",
            "Qt draws Natron's Droid Sans with the skin's font: " + family + ", the application's " + app.font().family())
        sheet = app.styleSheet()
        say("@layer/" not in sheet and "/ext/icons/qss/" in sheet and "The skin's font size" in sheet,
            "the window's stylesheet is the skin's session copy (paths filled in, the skin's font size)")
        icons = paths.ext() / "icons"
        ours, natrons = [], []
        for row in skin.icon_table():
            mine = QtGui.QImage(str(icons / row["file"]))
            theirs = QtGui.QImage(":/Resources/Images/" + row["file"])
            if not mine.isNull():
                ours.append((row["file"], fingerprint(mine)))
            if not theirs.isNull():
                natrons.append((row["file"], fingerprint(theirs)))
        say(len(natrons) >= 100, "Natron's own pictures are readable from its resources to compare (" + str(len(natrons))
            + ")")
        counts = {"ours": 0, "natron": [], "other": 0}
        for button in window.findChildren(QtWidgets.QAbstractButton):
            if not button.isVisible() or button.icon().isNull():
                continue
            size = button.iconSize()
            seen = fingerprint(button.icon().pixmap(size).toImage())
            best_ours = min((distance(seen, f), n) for n, f in ours) if ours else (1.0, "")
            best_theirs = min((distance(seen, f), n) for n, f in natrons) if natrons else (1.0, "")
            if best_ours[0] < 0.04 and best_ours[0] <= best_theirs[0]:
                counts["ours"] += 1
            elif best_theirs[0] < 0.04:
                counts["natron"].append(best_theirs[1] + " (" + (button.toolTip() or "")[:30] + ")")
            else:
                counts["other"] += 1
        say(counts["ours"] >= 40 and not counts["natron"],
            "the window's icon buttons show our pictures: " + str(counts["ours"]) + " ours, "
            + str(len(counts["natron"])) + " still Natron's" + (": " + ", ".join(counts["natron"][:6]) if counts["natron"]
                                                               else "") + ", " + str(counts["other"]) + " others")
        checker = [b for b in window.findChildren(QtWidgets.QAbstractButton) if b.isVisible() and b.isCheckable()
                   and "checkerboard" in (b.toolTip() or "")]
        on = dict(ours).get("checkerboard_on.png")
        if checker and on is not None:
            button = checker[0]
            was = button.isChecked()
            button.click()
            app.processEvents()
            mode = QtGui.QIcon.State.On if button.isChecked() else QtGui.QIcon.State.Off
            seen = fingerprint(button.icon().pixmap(button.iconSize(), QtGui.QIcon.Mode.Normal, mode).toImage())
            wanted = dict(ours).get("checkerboard_on.png" if button.isChecked() else "checkerboard_off.png")
            say(distance(seen, wanted) < 0.04, "the viewer's checkerboard button, clicked, shows our "
                + ("on" if button.isChecked() else "off") + " picture")
            if button.isChecked() != was:
                button.click()
                app.processEvents()
        else:
            say(False, "the viewer's checkerboard button is found to click")
        # The File menu's icons come from the skin's icon theme (Natron asks Qt for them by name).
        say(report is not None and report.theme == skin.THEME and QtGui.QIcon.themeName() == skin.THEME,
            "the skin's icon theme is Qt's: " + QtGui.QIcon.themeName())
        # The menu by its title among the window's own children (a QAction's menu() can hand back a wrapper whose
        # C++ object Qt has already replaced).
        menus = [m for m in window.findChildren(QtWidgets.QMenu) if m.title().replace("&", "") == "File"]
        named = [a.icon().name() for a in (menus[0].actions() if menus else []) if not a.icon().isNull()]
        say("document-open" in named and "document-save" in named,
            "the File menu's actions take their icons from the theme by name (" + ", ".join(sorted(set(named))) + ")")
        # This fork's builds name the properties panels' header (core patch 0002); Niik-l's plain release doesn't.
        try:
            import NatronEngine

            patched = NatronEngine.natron.getSettings().getParam("nodeTileWidth") is not None
        except Exception:  # noqa: BLE001  (the check reports what it saw)
            patched = False
        if patched:
            headers = window.findChildren(QtWidgets.QFrame, "DockablePanelHeader")
            say(len(headers) >= 1, "the properties panels' header is named for the stylesheet (" + str(len(headers)) + ")")
        polished = [b for bar in window.findChildren(QtWidgets.QToolBar) for b in bar.findChildren(QtWidgets.QToolButton)]
        side = int(skin.settings().get("toolbar_icon", 20))
        say(polished and all(b.iconSize().width() >= side for b in polished),
            "the left toolbar's buttons show their icons at " + str(side) + " pixels")

    def tools(app, natron_app):
        """Roadmap items 5 to 7 in the window: gizmos by their ID, similar colour, the ToolSets pasted with Natron's
        own paste (the clipboard put back), Save selection as ToolSet, an expression's window; the pasted comp is
        saved for run_smoke.py's run without the layer."""
        import OpenImageIO as oiio
        from natron_layer import compat, expressions, gizmos, toolsets, workflow

        made = []
        for gizmo in gizmos.GIZMOS:
            node = natron_app.createNode(gizmo.plugin_id)
            made.append(node)
            wanted = compat.setting_value(gizmos.MENU_COLOURS.get(gizmo.menu, "defaultNodeColor"))
            colour = tuple(round(c, 2) for c in node.getColor()) if node is not None else ()
            say(node is not None and len(node.getChildren()) > 2 and colour == tuple(round(c, 2) for c in wanted[:3]),
                "in the window, " + gizmo.name + " is made by its ID (" + gizmo.plugin_id + "), a Group of "
                + (str(len(node.getChildren())) if node else "?") + " nodes, coloured as Nuke's " + gizmo.menu
                + " nodes " + str(colour))
        app.processEvents()
        one = natron_app.createNode("net.sf.openfx.GradePlugin")
        two = natron_app.createNode("net.sf.cimg.CImgBlur")
        app.processEvents()
        one.setColor(0.9, 0.1, 0.1)
        two.setColor(0.9, 0.1, 0.1)
        found = sorted(n.getScriptName() for n in workflow.similar(natron_app, one, "colour"))
        say(found == sorted([one.getScriptName(), two.getScriptName()]),
            "Select similar colour finds the two nodes painted the same red: " + ", ".join(found))
        for node in made + [one, two]:
            node.destroy()
        app.processEvents()

        # A render with Cycles' passes, and a checker, to paste the studio ToolSets on.
        passes = {"DiffDir": 0.1, "DiffInd": 0.05, "DiffCol": 0.8, "GlossDir": 0.2, "GlossInd": 0.1, "GlossCol": 0.5,
                  "Emit": 0.03}
        channels, values = ["R", "G", "B", "A"], [0.3, 0.3, 0.3, 0.75]
        for name, value in passes.items():
            for letter in "RGB":
                channels.append("ViewLayer." + name + "." + letter)
                values.append(value)
        exr = os.path.join(out, "window_cycles_passes.exr")
        spec = oiio.ImageSpec(64, 64, len(channels), oiio.FLOAT)
        spec.channelnames = tuple(channels)
        image = oiio.ImageBuf(spec)
        oiio.ImageBufAlgo.fill(image, tuple(values))
        image.write(exr)
        render = natron_app.createReader(exr.replace("\\", "/"))
        compat.select_nodes(natron_app, [])
        checker = natron_app.createNode("net.sf.openfx.CheckerBoardPlugin")
        if checker.getInput(0) is not None:  # the window connects a new node to the selected one
            checker.disconnectInput(0)
        compat.set_node_value(checker, "extent", "format")
        compat.set_node_value(checker, "NatronParamFormatChoice", "square_256")
        app.processEvents()
        compat.set_clipboard_text("the artist's own clipboard")
        studio = {t.name: t for t in toolsets.all_toolsets() if t.place == "Studio"}
        jobs, references = [], {}
        try:
            with open(os.environ.get("NATRON_LAYER_SMOKE_REFERENCES", ""), encoding="utf-8") as file:
                references = json.load(file)
        except (OSError, ValueError):
            pass
        project = os.path.join(out, "pasted_toolsets.ntp").replace("\\", "/")
        for name, source in (("CG beauty rebuild (Cycles passes)", render), ("Grain and lens", checker)):
            toolset = studio.get(name)
            if toolset is None:
                say(False, "the studio ToolSet " + name + " is listed")
                continue
            compat.select_only(natron_app, source)
            before = {n.getScriptName() for n in compat.children(natron_app)}
            report = toolsets.paste(natron_app, toolset)
            app.processEvents()
            new = [n for n in compat.children(natron_app) if n.getScriptName() not in before]
            end = toolsets.find(new, "ToolSetOut")
            say(len(new) == len(report.nodes) and len(new) > 4 and report.connected_to == source.getScriptName()
                and end is not None, "Natron's paste of the ToolSet " + name + ": " + report.summary(name))
            if name.startswith("CG"):
                say(sorted(report.matched) == sorted(passes), "its AOV Shuffles found the render's passes")
                jobs.append({"name": "pasted rebuild", "project": project, "add_writer": end.getScriptName(),
                             "frame": 1, "expected": [0.3, 0.3, 0.3, 0.75], "tolerance": 1e-3})
            elif references.get(name):
                jobs.append({"name": "pasted grain and lens", "project": project, "add_writer": end.getScriptName(),
                             "frame": 1, "reference": references[name], "tolerance": 1e-5})
        held = compat.clipboard_text()
        say(held == "the artist's own clipboard", "the clipboard holds what it held before the pastes (put back): "
            + repr(held[:60]))
        compat.select_nodes(natron_app, [render, checker])
        saved = toolsets.save_selection(natron_app, "Smoke test set")
        mine = [t for t in toolsets.all_toolsets() if t.place == "Mine"]
        # Paths compared once normalised, as smoke_checks.py does: started from Git Bash (MSYSTEM set), Natron's
        # MinGW Python writes "/" where the variable has "\".
        norm = lambda p: os.path.normcase(os.path.normpath(str(p)))  # noqa: E731
        say(saved.is_file() and norm(saved).startswith(norm(os.environ.get("NATRON_LAYER_CONFIG_DIR", "?")))
            and [t.name for t in mine] == ["Smoke test set"],
            "Save selection as ToolSet keeps it in the artist's own ToolSets (the test's config folder): " + str(saved))
        before = {n.getScriptName() for n in compat.children(natron_app)}
        again = toolsets.paste(natron_app, mine[0])
        app.processEvents()
        new = [n for n in compat.children(natron_app) if n.getScriptName() not in before]
        say(len(new) == 2 and len(again.nodes) == 2, "and it pastes back: " + ", ".join(again.nodes))
        # The comp took the first Read's format (64 x 64); give it the headless run's (HD) so both render alike.
        formats = natron_app.getProjectParam("outputFormat")
        options = list(formats.getOptions())
        hd = [o for o in options if o.startswith("HD") and "720" not in o]
        if hd:
            formats.setValue(options.index(hd[0]))
        compat.save_temp_project(natron_app, project)
        say(os.path.isfile(project), "the comp with the pasted ToolSets saved for the run without the layer")
        with open(os.path.join(out, "project_jobs_gui.json"), "w", encoding="utf-8") as file:
            json.dump(jobs, file, indent=1)
        expressions._Window.show(checker, expressions.by_id("sine"))
        app.processEvents()
        windows = [w for w in app.topLevelWidgets() if isinstance(w, QtWidgets.QDialog) and w.isVisible()
                   and w.windowTitle().startswith("Expression:")]
        say(windows, "Nuke > Expressions > Oscillate (sine) opens its window: " + (windows[0].windowTitle()
                                                                                  if windows else "none"))
        for w in windows:
            w.close()

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
                if os.environ.get("NATRON_LAYER_PROBE_OFFSCREEN") == "1":
                    # Someone is working at this PC: the window is moved out of sight (the checks grab it there).
                    window.move(-6000, 0)
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
