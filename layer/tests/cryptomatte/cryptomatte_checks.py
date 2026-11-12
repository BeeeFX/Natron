# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The Cryptomatte node's checks inside NatronRenderer, run by run_cryptomatte.py (``NatronRenderer -t``) with the
layer's plug-in folder on NATRON_PLUGIN_PATH and Natron's caches and home in a temporary folder.

NATRON_LAYER_CRYPTO_PLAN names a JSON plan: renders to make (a source, a layer, a matte list, an output) and the
picking walks. Each render is written to NATRON_LAYER_CRYPTO_OUT and listed in ``renders.json`` for
run_cryptomatte.py, which compares its pixels with the truth summed straight from the file. What can only be seen
in here (the layers found, the list after a pick, the status line) is checked here. This file stays plain ASCII.
"""

import json
import os
import sys
import time
import traceback

RESULTS = {"ok": 0, "failed": 0}
OUT = os.environ.get("NATRON_LAYER_CRYPTO_OUT", "")
HERE = os.environ.get("NATRON_LAYER_CRYPTO_DIR", "")
RENDERS = []
JOBS = []
_COUNT = [0]


def say(condition, what):
    RESULTS["ok" if condition else "failed"] += 1
    print(("  ok  " if condition else "FAILED  ") + what, flush=True)
    return bool(condition)


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


def natron_app():
    import NatronEngine

    return NatronEngine.natron.getActiveInstance()


def reader(path, name=None):
    from natron_layer import compat

    read = compat.create_node(natron_app(), "fr.inria.openfx.ReadOIIO")
    read.getParam("filename").set(path.replace("\\", "/"))
    if name:
        read.setScriptName(name)
    return read


def make_node(source, name=None):
    from natron_layer import compat, gizmos

    node = compat.create_node(natron_app(), gizmos.BY_NAME["Cryptomatte"].plugin_id)
    _COUNT[0] += 1
    node.setScriptName(name or ("Crypto" + str(_COUNT[0])))
    if source is not None:
        compat.connect(node, 0, source)
    return node


def setup(node, case):
    from natron_layer import cryptomatte

    if case.get("manifest_file"):
        node.getParam("manifestFile").set(case["manifest_file"].replace("\\", "/"))
    if case.get("layer"):
        node.getParam("layerName").set(case["layer"])
    node.getParam("matteList").set(case.get("list", ""))
    node.getParam("output").setValue(int(case.get("output", 2)))
    node.getParam("preview").setValue(bool(case.get("preview", False)))
    return cryptomatte.refresh(node, natron_app())


def write(node, name, frame=1):
    """Render ``node`` into OUT/<name>_####.exr: 32-bit float, the values as they are (no colour conversion, no
    premultiplication by the Write)."""
    from natron_layer import compat

    path = os.path.join(OUT, name + "_####.exr").replace("\\", "/")
    w = natron_app().createWriter(path)
    w.setScriptName("Write_" + name)
    compat.connect(w, 0, node)
    for param, value in (("frameRange", "manual"), ("firstFrame", frame), ("lastFrame", frame),
                         ("formatType", "input"), ("bitDepth", "32f"), ("inputPremult", "premult")):
        compat.set_node_value(w, param, value)
    space_in, space_out = w.getParam("ocioInputSpace"), w.getParam("ocioOutputSpace")
    if space_in is not None and space_out is not None:
        space_out.setValue(space_in.get())
    started = time.monotonic()
    natron_app().render(w, frame, frame)
    took = time.monotonic() - started
    done = path.replace("####", "%04d" % frame)
    return (done if os.path.isfile(done) else None), took, w


def record(case, node, found, path, took, extra=None):
    entry = {"name": case["name"], "source": case["source"], "image": case.get("image"),
             "layer": found["layer"], "list": str(node.getParam("matteList").get()),
             "manifest_file": case.get("manifest_file"), "output": int(node.getParam("output").get()),
             "preview": bool(node.getParam("preview").get()), "path": path, "seconds": round(took, 3),
             "ids": sorted("%08x" % b for b in found["ids"]), "status": str(node.getParam("status").get())}
    entry.update(extra or {})
    RENDERS.append(entry)
    return entry


# --- The plan's renders ---


def run_render(case):
    read = reader(case["source"])
    node = make_node(read)
    if case.get("image"):
        from natron_layer import cryptomatte as crypto_module

        node.connectInput(1, reader(case["image"]))
        crypto_module.image_switch(node)
    found = setup(node, case)
    if case.get("expect_layers") is not None:
        say(found["layers"] == case["expect_layers"], case["name"] + ": the layers found are " + str(found["layers"])
            + " (wanted " + str(case["expect_layers"]) + ")")
    if case.get("expect_layer"):
        say(found["layer"] == case["expect_layer"], case["name"] + ": the layer used is " + found["layer"])
    if case.get("expect_manifest") is not None:
        say(found["manifest"] == case["expect_manifest"], case["name"] + ": " + str(found["manifest"])
            + " names in the manifest (" + found["where"] + ")")
    say(found["updated"], case["name"] + ": the inner nodes were set (" + str(node.getParam("status").get()) + ")")
    path, took, w = write(node, case["name"])
    say(path is not None, case["name"] + ": rendered (" + ("%.2f" % took) + " s)")
    record(case, node, found, path, took)
    if case.get("save"):
        JOBS.append({"writer": w.getScriptName(), "gizmo": node.getScriptName(), "reference": path})
    return node


def check_built():
    from natron_layer import compat, cryptomatte

    ids = {str(i) for i in compat.plugin_ids(refresh=True)}
    say("layer.gizmo.Cryptomatte" in ids, "the Cryptomatte gizmo is registered as layer.gizmo.Cryptomatte")
    say(all(compat.has_plugin(p) for p in cryptomatte.NEEDS), "its Natron nodes exist in this Natron: "
        + ", ".join(cryptomatte.NEEDS))
    node = make_node(None, "Built")
    kinds = sorted({c.getPluginID() for c in node.getChildren()})
    say(len(node.getChildren()) > 20 and node.getInputLabel(0) == "Source" and node.getInputLabel(1) == "Image",
        "made by its ID: a Group of " + str(len(node.getChildren())) + " Natron nodes (" + ", ".join(kinds)
        + "), inputs " + node.getInputLabel(0) + " and " + node.getInputLabel(1))
    say(not [k for k in kinds if k.startswith("layer.") or "Shadertoy" in k],
        "only Natron's own CPU nodes inside (no Shadertoy, no OpenGL)")
    import NatronEngine

    gl = NatronEngine.natron.getSettings().getParam("enableOpenGLRendering")
    say(True, "OpenGL rendering in this session is Natron's default, untouched: " + str(gl.getOption(gl.get())))
    node.destroy()


# --- Picking ---


def preview_colour(path, x, y):
    sys.path.insert(0, HERE)
    import exr_io

    image = exr_io.read(path)
    i = y * image.width + x
    return tuple(image.channels[c][i] for c in "RGB")


def run_pick(case):
    from natron_layer import cryptomatte, cryptomatte_data

    read = reader(case["source"])
    node = make_node(read, "Picking")
    setup(node, dict(case, list="", preview=True))
    path, _, _ = write(node, case["name"] + "_preview0")
    first = case["picks"][0]
    colour = preview_colour(path, first["x"], first["y"])
    say(cryptomatte_data.decode_preview(*colour) == int(first["bits"], 16),
        "the preview's colour at (" + str(first["x"]) + ", " + str(first["y"]) + ") gives back the ID of "
        + first["name"] + " exactly: " + str(colour))
    entry = cryptomatte.pick(node, colour, True, natron_app())
    say(entry == first["name"] and first["name"] in str(node.getParam("matteList").get()),
        "Pick (add) on it puts " + repr(entry) + " in the list: " + repr(str(node.getParam("matteList").get())))

    # Natron's own way in: the colour control set as Natron's viewer picker does, then Natron's callback.
    second = case["picks"][1]
    path, _, _ = write(node, case["name"] + "_preview1")
    colour2 = preview_colour(path, second["x"], second["y"])
    say(cryptomatte_data.decode_preview(*colour2) == int(second["bits"], 16),
        "an object not in the list is drawn dimmed and still gives back its ID: " + second["name"])
    pick_param = node.getParam("pickAdd")
    before = str(node.getParam("matteList").get())
    for d in range(3):
        pick_param.setValue(colour2[d], d)
    automatic = str(node.getParam("matteList").get()) != before
    if not automatic:
        cryptomatte.param_changed(pick_param, node, None, natron_app(), True)
    listed = str(node.getParam("matteList").get())
    say(second["name"] in listed, "the Pick (add) colour control, set as the viewer's picker sets it, adds "
        + second["name"] + (" (Natron ran the callback itself)" if automatic else " (the callback called as Natron "
                            "calls it: headless, Natron runs no callback for a value set by a script)"))

    edge = tuple((a + b) / 2 for a, b in zip(colour, colour2))
    picked = cryptomatte.pick(node, edge, True, natron_app())
    say(picked is None and "Nothing to pick" in str(node.getParam("status").get()),
        "a colour from an edge (two objects averaged) adds nothing and says why: "
        + repr(str(node.getParam("status").get())))
    removed = cryptomatte.pick(node, colour, False, natron_app())
    listed = str(node.getParam("matteList").get())
    say(removed == first["name"] and first["name"] not in listed.splitlines(),
        "Pick (remove) on the first object takes it out: " + repr(listed))
    node.getParam("preview").setValue(False)
    say(cryptomatte.pick(node, (0.3, 0.2, 0.1), True, natron_app()) is None and node.getParam("preview").get(),
        "a pick while Preview is off turns Preview on and asks to pick again: "
        + repr(str(node.getParam("status").get())))

    # The wildcard case: a pick (remove) on an object a wildcard took leaves it out with -name.
    node.getParam("matteList").set(case["wildcard"])
    cryptomatte.refresh(node, natron_app())
    cryptomatte.pick(node, colour2, False, natron_app())
    listed = str(node.getParam("matteList").get())
    say(("-" + second["name"]) in listed.splitlines(), "Pick (remove) on an object the wildcard " + case["wildcard"]
        + " took writes -" + second["name"] + ": " + repr(listed))
    node.getParam("addName").setValue(1 + sorted(case["manifest_names"]).index(first["name"]))
    cryptomatte.param_changed(node.getParam("addName"), node, None, natron_app(), True)
    listed = str(node.getParam("matteList").get())
    say(first["name"] in listed.splitlines() and node.getParam("addName").get() == 0,
        "Add by name lists every manifest name and adds the one chosen: " + repr(listed))
    node.getParam("preview").setValue(False)
    found = cryptomatte.refresh(node, natron_app())
    path, took, _ = write(node, case["name"])
    record(dict(case, output=2), node, found, path, took)


def run_no_manifest(case):
    """A frame without any manifest: names still work (hashed), wildcards wait for a manifest file."""
    from natron_layer import cryptomatte

    read = reader(case["source"])
    node = make_node(read, "NoManifest")
    found = setup(node, dict(case, list=case["name_only"], manifest_file=None))
    say(found["updated"] and found["manifest"] == 0 and found["layer"] == case["layer"],
        "without a manifest the layer is still found (" + found["layer"] + ") and a plain name is hashed: "
        + repr(str(node.getParam("status").get())))
    path, took, _ = write(node, case["name"] + "_name")
    record(dict(case, name=case["name"] + "_name", manifest_file=None), node, found, path, took)
    ranks0 = cryptomatte.inner(node, "Ranks0")
    kept = str(ranks0.getParam("expression").get())
    node.getParam("matteList").set(case["wildcard"])
    found = cryptomatte.refresh(node, natron_app())
    say(not found["updated"] and str(ranks0.getParam("expression").get()) == kept
        and "No manifest" in str(node.getParam("status").get()),
        "a wildcard without a manifest leaves the matte as it was and says what to do: "
        + repr(str(node.getParam("status").get())))
    node.getParam("manifestFile").set(case["manifest_file"].replace("\\", "/"))
    found = cryptomatte.refresh(node, natron_app())
    say(found["updated"] and found["manifest"] > 0, "with Manifest file set to the sidecar .json, the wildcard works: "
        + repr(str(node.getParam("status").get())))
    path, took, _ = write(node, case["name"] + "_wildcard")
    record(dict(case, name=case["name"] + "_wildcard"), node, found, path, took)


def run_shared_read(case):
    """Several Cryptomattes on one Read, set up the same way (so their inner nodes have the same history): each must
    render its own matte, not one cached by another (Natron's cache knows inner nodes by their own names)."""
    from natron_layer import cryptomatte

    read = reader(case["source"])
    nodes = []
    for each in case["nodes"]:
        node = make_node(read)
        found = setup(node, dict(case, **each))
        path, took, _ = write(node, each["name"])
        record(dict(case, **each), node, found, path, took)
        nodes.append(node)
    names = sorted(c.getScriptName() for n in nodes for c in n.getChildren()
                   if c.getScriptName().startswith("Rank0_"))
    say(len(set(names)) == len(nodes), "each node's inner nodes carry its name: " + ", ".join(names))
    first = nodes[0]
    first.setScriptName("Renamed" + str(_COUNT[0]))
    cryptomatte.input_changed(0, first, None, natron_app())
    say(cryptomatte.inner(first, "Rank0").getScriptName().endswith(first.getScriptName()),
        "a renamed node's inner nodes follow its new name when it's connected again: "
        + cryptomatte.inner(first, "Rank0").getScriptName())
    each = case["nodes"][0]
    path, took, _ = write(first, each["name"] + "_renamed")
    record(dict(case, **dict(each, name=each["name"] + "_renamed")), first, cryptomatte.refresh(first, natron_app()),
           path, took)


def run_save():
    """The comp with every node rendered above, saved for the run without the layer."""
    from natron_layer import compat

    project = os.path.join(OUT, "cryptomatte_comp.ntp")
    saved = compat.save_temp_project(natron_app(), project)
    text = open(project, encoding="utf-8").read() if saved else ""
    say(saved and "layer.gizmo.Cryptomatte" in text, "the comp with the Cryptomatte nodes saved (" + str(len(JOBS))
        + " of them kept for the run without the layer)")
    with open(os.path.join(OUT, "project_jobs.json"), "w", encoding="utf-8") as file:
        json.dump([{"name": "cryptomatte", "project": project.replace("\\", "/"), "frame": 1, "tolerance": 0.0,
                    "writers": [{"writer": j["writer"], "gizmo": j["gizmo"], "reference": j["reference"]}
                                for j in JOBS], "groups": [j["gizmo"] for j in JOBS]}], file, indent=1)


def main():
    try:
        with open(os.environ["NATRON_LAYER_CRYPTO_PLAN"], encoding="utf-8") as file:
            plan = json.load(file)
        kinds = {"render": run_render, "pick": run_pick, "no_manifest": run_no_manifest,
                 "shared_read": run_shared_read}
        steps = [("the node", check_built)]
        steps += [(c["name"], (lambda c=c: kinds[c.get("kind", "render")](c))) for c in plan["cases"]]
        steps.append(("the saved comp", run_save))
        for title, step in steps:
            try:
                step()
            except Exception:
                say(False, title + " raised:\n" + traceback.format_exc())
        with open(os.path.join(OUT, "renders.json"), "w", encoding="utf-8") as file:
            json.dump(RENDERS, file, indent=1)
    except Exception:
        say(False, "the checks couldn't run:\n" + traceback.format_exc())
    print("CRYPTOMATTE CHECKS " + ("PASSED" if RESULTS["failed"] == 0 else "FAILED") + " (" + str(RESULTS["ok"])
          + " ok, " + str(RESULTS["failed"]) + " failed)", flush=True)
    end(0 if RESULTS["failed"] == 0 else 1)


main()
