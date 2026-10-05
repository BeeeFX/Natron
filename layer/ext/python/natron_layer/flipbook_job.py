# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The flipbook's render, run by NatronRenderer -t from workflow.flipbook (never imported).

NATRON_LAYER_FLIPBOOK holds the job as JSON: the comp's copy, the node, the frames, the output (frames or a movie),
the original comp's folder (its [Project] path) and where to write the report. It opens the copy, points [Project]
at the original folder (so relative file paths still read), adds a Write to the node, renders, writes the report and
ends at once. The artist's comp and Natron's settings are never touched. This file stays plain ASCII.
"""


def _flipbook():
    import json
    import os
    import re
    import sys
    import traceback

    import NatronEngine

    job = json.loads(os.environ["NATRON_LAYER_FLIPBOOK"])
    report = {"ok": False, "output": job["output"]}
    try:
        app = NatronEngine.natron.getActiveInstance()
        loaded = app.loadProject(job["project"]) or app
        folder = job.get("project_folder") or ""
        paths = loaded.getProjectParam("projectPaths")
        if folder and paths is not None:
            value = str(paths.get())
            fixed = re.sub(r"(<Name>Project</Name><Value>)(.*?)(</Value>)", lambda m: m.group(1) + folder + m.group(3),
                           value)
            if fixed != value:
                paths.setValue(fixed)
        node = loaded.getNode(job["node"])
        if node is None:
            raise RuntimeError("the comp's copy has no node " + job["node"])
        write = loaded.createWriter(job["output"])
        if write.getInput(0) is not None:
            write.disconnectInput(0)
        write.connectInput(0, node)

        def choose(name, option):
            param = write.getParam(name)
            if param is None:
                return
            options = list(param.getOptions())
            if option in options:
                param.setValue(options.index(option))

        choose("frameRange", "manual")
        write.getParam("firstFrame").setValue(int(job["first"]))
        write.getParam("lastFrame").setValue(int(job["last"]))
        choose("formatType", "input")
        if job.get("movie"):
            choose("format", "mp4")
            choose("codec", "libx264")
        else:
            # Frames for RV keep the comp's linear values: RV shows them through its own display.
            space_in, space_out = write.getParam("ocioInputSpace"), write.getParam("ocioOutputSpace")
            if space_in is not None and space_out is not None:
                space_out.setValue(space_in.get())
        loaded.render(write, int(job["first"]), int(job["last"]))
        if job.get("movie"):
            report["ok"] = os.path.isfile(job["output"]) and os.path.getsize(job["output"]) > 0
        else:
            frames = [job["output"].replace("####", "%04d" % f) for f in range(int(job["first"]), int(job["last"]) + 1)]
            report["frames"] = [f for f in frames if os.path.isfile(f)]
            report["ok"] = len(report["frames"]) == len(frames)
        if not report["ok"]:
            report["error"] = "NatronRenderer finished without writing every frame"
    except Exception:
        report["error"] = traceback.format_exc()
    with open(job["done"], "w", encoding="utf-8") as file:
        json.dump(report, file, indent=1)
    sys.stdout.flush()
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        kernel32.TerminateProcess(kernel32.GetCurrentProcess(), 0 if report["ok"] else 1)
    os._exit(0 if report["ok"] else 1)


_flipbook()
