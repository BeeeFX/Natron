# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Comps saved by the smoke test, opened and rendered by a NatronRenderer **without the layer** (run_smoke.py runs
``NatronRenderer -t project_checks.py`` with nothing on NATRON_PLUGIN_PATH), as the farm or a plain Natron would:

- the comp of every gizmo: each opens as a plain Group (its inner nodes were saved with it) and renders the pixels
  the layer rendered;
- the comp written by Collect files: its Read points into the collected folder and renders the plate;
- the ToolSets pasted in Natron's window (with --gui): they render as their recipes did.

NATRON_LAYER_SMOKE_JOBS names the JSON list of jobs. This file stays plain ASCII.
"""

import json
import os
import sys
import traceback

RESULTS = {"ok": 0, "failed": 0}
OUT = os.environ.get("NATRON_LAYER_SMOKE_OUT", "")


def say(condition, what):
    RESULTS["ok" if condition else "failed"] += 1
    print(("  ok  " if condition else "FAILED  ") + what, flush=True)
    return bool(condition)


def max_diff(a, b):
    import OpenImageIO as oiio

    if not (a and b and os.path.isfile(a) and os.path.isfile(b)):
        return 1e9
    diff = oiio.ImageBufAlgo.absdiff(oiio.ImageBuf(a), oiio.ImageBuf(b))
    return max(oiio.ImageBufAlgo.computePixelStats(diff).max)


def pixel(path, x, y):
    import OpenImageIO as oiio

    image = oiio.ImageBuf(path)
    return tuple(image.getpixel(x, image.spec().height - 1 - y))


def point_writer(app, write, path, frame):
    write.getParam("filename").setValue(path.replace("\\", "/"))
    for name, value in (("firstFrame", frame), ("lastFrame", frame)):
        if write.getParam(name) is not None:
            write.getParam(name).setValue(value)


def run_job(job):
    import NatronEngine

    app = NatronEngine.natron.getActiveInstance()
    loaded = app.loadProject(job["project"]) or app
    say(loaded is not None, job["name"] + ": the comp opens without the layer: " + os.path.basename(job["project"]))
    frame = int(job.get("frame", 1))
    target = os.path.join(OUT, "without_layer", job["name"])
    os.makedirs(target, exist_ok=True)
    packaged = bool(os.environ.get("NATRON_LAYER_SMOKE_PACKAGED"))
    for name in job.get("groups", []):
        node = loaded.getNode(name)
        kind = node.getPluginID() if node is not None else "?"
        # Natron opens a saved Group PyPlug from the comp; where the PyPlug's file is found (the layer installed) the
        # Group takes the PyPlug's name and ID (AppInstance::setGroupLabelIDAndVersion), else it stays a plain Group.
        fine = kind == "fr.inria.built-in.Group" or (packaged and kind.startswith("layer.gizmo."))
        say(node is not None and fine and len(node.getChildren()) > 2,
            name + " opens from the comp as a Group of " + (str(len(node.getChildren())) if node else "?")
            + " Natron nodes (" + kind + ")")
    for entry in job.get("writers", []):
        write = loaded.getNode(entry["writer"])
        if write is None:
            say(False, job["name"] + ": the comp has " + entry["writer"])
            continue
        path = os.path.join(target, entry["writer"] + ".####.exr")
        point_writer(loaded, write, path, frame)
        loaded.render(write, frame, frame)
        done = path.replace("####", "%04d" % frame)
        difference = max_diff(done, entry["reference"])
        say(difference <= float(job.get("tolerance", 1e-5)),
            entry["writer"] + " renders the same pixels as with the layer (largest difference "
            + ("%.2g" % difference) + ")")
    if job.get("add_writer"):
        source = loaded.getNode(job["add_writer"])
        if source is None:
            say(False, job["name"] + ": the comp has " + job["add_writer"])
            return
        if job.get("file_starts"):
            value = str(source.getParam("filename").get())
            say(value.startswith(job["file_starts"][1]), job["add_writer"] + " reads " + value)
        path = os.path.join(target, "added.####.exr")
        write = loaded.createWriter(path.replace("\\", "/"))
        write.connectInput(0, source)
        for name, option in (("frameRange", "manual"), ("formatType", "input")):
            param = write.getParam(name)
            options = list(param.getOptions())
            param.setValue(options.index(option))
        point_writer(loaded, write, path, frame)
        space_in, space_out = write.getParam("ocioInputSpace"), write.getParam("ocioOutputSpace")
        if space_in is not None and space_out is not None:
            space_out.setValue(space_in.get())
        loaded.render(write, frame, frame)
        done = path.replace("####", "%04d" % frame)
        if job.get("reference"):
            difference = max_diff(done, job["reference"])
            say(difference <= float(job.get("tolerance", 1e-5)), job["name"] + ": " + job["add_writer"]
                + " renders what its recipe rendered with the layer (largest difference " + ("%.2g" % difference) + ")")
            return
        got = pixel(done, 3, 3) if os.path.isfile(done) else ()
        wanted = job["expected"]
        say(len(got) >= 4 and all(abs(a - b) <= job.get("tolerance", 1e-4) for a, b in zip(got, wanted)),
            job["name"] + ": " + job["add_writer"] + " renders " + str(tuple(round(v, 4) for v in got))
            + " (wanted " + str(tuple(wanted)) + ")")


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


def main():
    try:
        import NatronEngine

        layer_ids = [str(i) for i in NatronEngine.natron.getPluginIDs() if str(i).startswith("layer.")]
        if os.environ.get("NATRON_LAYER_SMOKE_PACKAGED"):
            say(True, "(a packaged build carries the layer; its comps still open as the plain Groups saved in them)")
        else:
            say(not layer_ids and "natron_layer" not in sys.modules,
                "this NatronRenderer runs without the layer (none of its plug-ins, no natron_layer)")
        with open(os.environ["NATRON_LAYER_SMOKE_JOBS"], encoding="utf-8") as file:
            jobs = json.load(file)
        for job in jobs:
            try:
                run_job(job)
            except Exception:
                say(False, job.get("name", "?") + " raised:\n" + traceback.format_exc())
    except Exception:
        say(False, "the checks without the layer couldn't run:\n" + traceback.format_exc())
    print("PROJECT CHECKS " + ("PASSED" if RESULTS["failed"] == 0 else "FAILED") + " (" + str(RESULTS["ok"])
          + " ok, " + str(RESULTS["failed"]) + " failed)", flush=True)
    end(0 if RESULTS["failed"] == 0 else 1)


main()
