# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""A headless session as the farm has it, run by run_smoke.py as ``NatronRenderer -t background_checks.py`` with the
layer on NATRON_PLUGIN_PATH and no NATRON_LAYER_LOOK: the layer loads, stands aside from the look (no preference set,
no report), and its gizmos are still made by their plug-in IDs (a comp holding one renders on a render PC).
This file stays plain ASCII.
"""

import os
import sys
import traceback

RESULTS = {"ok": 0, "failed": 0}


def say(condition, what):
    RESULTS["ok" if condition else "failed"] += 1
    print(("  ok  " if condition else "FAILED  ") + what, flush=True)


def end(code):
    sys.stdout.flush()
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

        layer = sys.modules.get("natron_layer")
        say(layer is not None, "the layer was loaded by its init.py in a headless session")
        say(layer is not None and layer.last_report is None,
            "headless without NATRON_LAYER_LOOK, the Nuke look isn't applied (no preference set, no report)")
        say(not os.environ.get("NATRON_LAYER_LOOK"), "this run has no NATRON_LAYER_LOOK")
        from natron_layer import gizmos

        app = NatronEngine.natron.getActiveInstance()
        made = app.createNode(gizmos.GIZMOS[0].plugin_id)
        say(made is not None, "a gizmo is still made headless without the look: " + gizmos.GIZMOS[0].name)
    except Exception:
        say(False, "the headless checks raised:\n" + traceback.format_exc())
    print("BACKGROUND CHECKS " + ("PASSED" if RESULTS["failed"] == 0 else "FAILED"), flush=True)
    end(0 if RESULTS["failed"] == 0 else 1)


main()
