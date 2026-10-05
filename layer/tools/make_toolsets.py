# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Make the studio ToolSets' files (``layer/ext/toolsets/*.xml``) from their recipes (any Python 3.10+, standard
library only):

    python layer/tools/make_toolsets.py --renderer "<release>/bin/NatronRenderer.exe"

A ToolSet file is what Natron's own Copy puts on the clipboard (its nodes as Natron's XML), which only Natron's
window can make. So this opens Natron's window for a few seconds with a small probe (``toolset_maker/initGui.py``)
that builds each recipe of ``natron_layer/toolset_recipes.py``, selects it, copies it with Natron's Copy and saves
the text, then ends Natron at once. The files are checked (Natron's format, no path of this PC inside: the gizmos'
PyPlug paths are cut to their file names) and written to ``ext/toolsets``. Run it again when a recipe changes, or
when a release of Natron changes its copy format; the smoke test pastes every file in the window.

Like the smoke test: Natron's home, caches and TEMP in a temporary folder, the artist's clipboard put back, and
Natron's settings (the registry) compared before and after, with the switches Natron records for the layer's PyPlugs
taken out again.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAYER = HERE.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(LAYER / "tests" / "smoke"))
import run_smoke  # noqa: E402  (its clean environment and its before/after comparison)


def clean(text: str) -> str:
    """A ToolSet file without paths of the PC it was made on: a gizmo's PyPlug path becomes its file name (Natron
    finds it on its plug-in paths by name, and a paste uses the saved nodes anyway)."""
    return re.sub(r"<PythonModule>[^<]*[/\\]([^/\\<]+\.py)</PythonModule>", r"<PythonModule>\1</PythonModule>", text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--renderer", help="the release's NatronRenderer (Natron.exe is next to it)")
    args = parser.parse_args()
    renderer = run_smoke.find_renderer(args.renderer)
    if renderer is None:
        print("NatronRenderer wasn't found: pass --renderer.")
        return 1
    natron = Path(renderer).with_name("Natron.exe")
    release = Path(renderer).resolve().parents[1]
    say = run_smoke.Say()
    before = run_smoke.own_state(release)
    switches = run_smoke.registry_values()
    tmp = Path(tempfile.mkdtemp(prefix="natron_layer_toolsets_"))
    try:
        env = run_smoke.base_environment(tmp)
        shutil.rmtree(tmp / "home" / ".nuke", ignore_errors=True)  # no first-launch question about Nuke preferences
        env["NATRON_PLUGIN_PATH"] = f"{LAYER / 'ext' / 'plugin'};{HERE / 'toolset_maker'}"
        code, _output = run_smoke.run([str(natron)], env, "Natron's window making the ToolSets", timeout=240)
        report_path = tmp / "out" / "toolsets.json"
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {"made": {}}
        say(code == 0 and report.get("made"), "Natron's window copied every recipe: "
            + ", ".join(report.get("made", {})) + (f" ({report.get('error')})" if report.get("error") else ""))
        target = LAYER / "ext" / "toolsets"
        target.mkdir(exist_ok=True)
        home = str(Path.home()).replace("\\", "/")
        for file_name in report.get("made", {}).values():
            text = clean((tmp / "out" / file_name).read_text(encoding="utf-8"))
            fine = "<Clipboard" in text and home.lower() not in text.lower().replace("\\", "/")
            say(fine, f"{file_name}: Natron's copied nodes, no path of this PC inside")
            if fine:
                (target / file_name).write_text(text, encoding="utf-8", newline="\n")
    finally:
        taken = run_smoke.forget_layer_switches(switches)
        if taken:
            print(f"    took out the {len(taken)} switches Natron recorded for the layer's PyPlugs")
        shutil.rmtree(tmp, ignore_errors=True)
    run_smoke.compare(before, run_smoke.own_state(release), say)
    print("ToolSets made." if say.ok else "Making the ToolSets FAILED.")
    return 0 if say.ok else 1


if __name__ == "__main__":
    sys.exit(main())
