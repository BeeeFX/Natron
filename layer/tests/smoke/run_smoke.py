# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The layer's smoke test against a portable release of the fork (any Python 3.10+, standard library only):

    python layer/tests/smoke/run_smoke.py --renderer "<release>/bin/NatronRenderer.exe" [--gui] [--keep]

(or NATRON_LAYER_RENDERER). It:

1. runs the Nuke preferences reader's tests (test_nuke_prefs.py, no Natron needed);
2. checks the layer's files against the repository: the stylesheet still holds Natron's own mainstyle.qss unchanged,
   the patch series matches upstream.toml, the startup files are plain ASCII, every alias and gizmo has its PyPlug,
   every studio ToolSet its file, every expression recipe makes valid Python;
3. runs smoke_checks.py inside NatronRenderer, with only the layer's plug-in folder on NATRON_PLUGIN_PATH and
   Natron's disk cache, home folder, TEMP and the layer's config folder in a temporary folder (a clean session):
   the look, the aliases, the keys, the import, then the tools (tool_checks.py: gizmos, workflow scripts, expression
   recipes, ToolSet recipes, with their pixels);
4. with --gui, opens Natron's window for about half a minute with a probe (gui_probe/) that checks the menu, the
   keys, the stylesheet and the first-launch question, makes each gizmo by its ID, pastes each studio ToolSet with
   Natron's own paste, takes a picture of the window and closes Natron;
5. renders the comps saved by 3 and 4 in a NatronRenderer **without the layer** (project_checks.py): the gizmos as
   the plain Groups they were saved as, the comp Collect files wrote, the pasted ToolSets;
6. compares Natron's settings (HKCU\\Software\\INRIA in the registry), its folders in %LOCALAPPDATA% and the home
   folder, and the release folder before and after: unchanged. Natron itself records a few switches for every
   PyPlug it registers (the layer's aliases and gizmos, ``layer.*``); those it added during the test are taken out
   again, as Singerie's own Natron suite does for its test PyPlug.

Exits with 1 when something fails. Natron's settings live in the registry and the fork has no option to put them
elsewhere, so this test never runs two Natrons at once and never writes a setting itself.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAYER = HERE.parents[1]
REPO = LAYER.parent
TIMEOUT = 1500
LAYER_PREFIX = "layer."  # the layer's PyPlugs: aliases (layer.nuke.*) and gizmos (layer.gizmo.*)
sys.dont_write_bytecode = True


class Say:
    def __init__(self) -> None:
        self.ok = True
        self.count = 0

    def __call__(self, condition: object, what: str) -> bool:
        print(f"  ok  {what}" if condition else f"FAILED  {what}", flush=True)
        self.ok = self.ok and bool(condition)
        self.count += 1
        return bool(condition)


def find_renderer(explicit: str | None) -> str | None:
    for candidate in (explicit, os.environ.get("NATRON_LAYER_RENDERER"), os.environ.get("SINGERIE_NATRON_RENDERER")):
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


# --- Natron's own state, before and after ---


def registry_export() -> str:
    if os.name != "nt":
        return ""
    with tempfile.TemporaryDirectory(prefix="natron_layer_reg_") as folder:
        export = os.path.join(folder, "natron.reg")
        done = subprocess.run(["reg", "export", r"HKCU\Software\INRIA", export, "/y"], capture_output=True, check=False)
        if done.returncode != 0:
            return "(no key)"
        with open(export, encoding="utf-16") as file:
            return file.read()


def registry_values_by_key(export: str) -> dict[str, str]:
    """A registry export as ``{"<key>\\<value name>": "<data>"}``: the values, whatever order the export lists them
    in (Windows lists a key's values in the order they were made, which a value written again can change)."""
    values: dict[str, str] = {}
    section = ""
    pending = ""
    for raw in export.splitlines():
        line = pending + raw.strip()
        if line.endswith("\\"):
            pending = line[:-1]
            continue
        pending = ""
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            values[section + "\\"] = "(key)"
        elif "=" in line and section:
            name, data = line.split("=", 1)
            values[section + "\\" + name] = data
    return values


def own_state(release: Path) -> dict[str, str] | None:
    if os.name != "nt":
        return None
    state = {f"registry: {k}": v for k, v in registry_values_by_key(registry_export()).items()}
    for base in (Path(os.environ.get("LOCALAPPDATA", "")) / "INRIA", Path.home() / ".Natron", release):
        for path in sorted(base.rglob("*")) if base.is_dir() else []:
            info = path.stat()
            state[str(path)] = f"{info.st_size} {info.st_mtime_ns}" if path.is_file() else "folder"
    return state


def registry_values() -> list[str]:
    listed = subprocess.run(["reg", "query", r"HKCU\Software\INRIA\Natron"], capture_output=True, text=True,
                            check=False).stdout  # fmt: skip
    return [line.strip().split("    ")[0] for line in listed.splitlines() if line.startswith("    ")]


def forget_layer_switches(before: list[str]) -> list[str]:
    """Take out the switches Natron recorded during the test for the layer's PyPlugs (only those that weren't there
    before the test)."""
    if os.name != "nt":
        return []
    taken = []
    for name in registry_values():
        if name.startswith(LAYER_PREFIX) and name not in before:
            subprocess.run(["reg", "delete", r"HKCU\Software\INRIA\Natron", "/v", name, "/f"], capture_output=True,
                           check=False)  # fmt: skip
            taken.append(name)
    return taken


def compare(before: dict[str, str] | None, after: dict[str, str] | None, say: Say) -> None:
    if before is None or after is None:
        print("  --  Natron's settings aren't compared off Windows")
        return
    changed = sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))
    for key in changed[:10]:
        print(f"    changed: {key}: {before.get(key)!r} -> {after.get(key)!r}")
    say(not changed, "Natron's settings (every registry value), its folders in %LOCALAPPDATA% and home, and the "
        "release folder are unchanged" + (f" ({len(changed)} changed)" if changed else ""))


# --- The steps ---


def run(command: list[str], env: dict[str, str], what: str, timeout: int = TIMEOUT) -> tuple[int, str]:
    print(f"--- {what}", flush=True)
    started = time.monotonic()
    try:
        done = subprocess.run(command, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout, check=False)  # fmt: skip
    except subprocess.TimeoutExpired:
        print(f"    it didn't finish within {timeout} s (stopped)")
        return 1, ""
    output = done.stdout + done.stderr
    quiet = ("OpenFX: loading", "load failed on plugin", "Fontconfig", "Note: -t argument", "Write", "Restoring the",
             "Loading plugin cache", "Loading PyPlugs", "Info: init.py", "OpenImageIO exited", "retrieved via",
             "ImageOutput::create")
    for line in output.splitlines():
        if line.strip() and not line.startswith(quiet):
            print(line if line.startswith(("  ok", "FAILED")) else f"    {line}", flush=True)
    print(f"    (exit code {done.returncode}, {time.monotonic() - started:.1f} s)", flush=True)
    return done.returncode, output


def unit_tests(say: Say) -> None:
    code, output = run([sys.executable, str(HERE / "test_nuke_prefs.py")], dict(os.environ),
                       "the Nuke preferences reader's tests (no Natron)")  # fmt: skip
    say(code == 0 and "\nOK" in output, "test_nuke_prefs.py passed")


def repository_checks(say: Say) -> None:
    print("--- the layer's files against the repository", flush=True)
    qss = (LAYER / "ext" / "qss" / "nuke.qss").read_text(encoding="utf-8")
    begin, end = "/* ---- NATRON mainstyle.qss: begin ---- */\n", "\n/* ---- NATRON mainstyle.qss: end ---- */"
    natron = REPO / "Gui" / "Resources" / "Stylesheets" / "mainstyle.qss"
    if natron.is_file() and begin in qss and end in qss:
        copied = qss.split(begin, 1)[1].split(end, 1)[0]
        say(copied.rstrip("\n") == natron.read_text(encoding="utf-8").rstrip("\n"),
            "nuke.qss holds Natron's own mainstyle.qss unchanged (else copy it again between the markers)")
    else:
        say(False, "nuke.qss has its NATRON markers and the repository has Gui/Resources/Stylesheets/mainstyle.qss")
    say(all(f"%{n}" in qss for n in range(1, 12)), "nuke.qss keeps Natron's %1 to %11 colour markers")
    series = [line for line in (LAYER / "patches" / "series").read_text(encoding="utf-8").splitlines()
              if line.strip() and not line.startswith("#")]  # fmt: skip
    import tomllib

    upstream = tomllib.loads((LAYER / "upstream.toml").read_text(encoding="utf-8"))
    say(len(series) == upstream["patches"]["count"] <= upstream["patches"]["budget_count"],
        f"the patch series ({len(series)}) matches upstream.toml and the budget")
    plugin = LAYER / "ext" / "plugin"
    run_by_natron = [*plugin.rglob("*.py"), LAYER / "ext" / "python" / "natron_layer" / "flipbook_job.py",
                     *HERE.glob("*_checks.py"), *(HERE / "gui_probe").glob("*.py")]
    not_ascii = [p.name for p in run_by_natron if not p.read_bytes().isascii()]
    say(not not_ascii, "the files Natron runs (startup files, PyPlugs, the flipbook's job, the checks) are plain ASCII"
        + (f": not {not_ascii}" if not_ascii else ""))
    sys.path.insert(0, str(LAYER / "ext" / "python"))
    sys.path.insert(0, str(LAYER / "compat"))
    from natron_layer import aliases, expressions, gizmos, toolset_recipes

    files = {p.stem for p in (plugin / "aliases").glob("NukeAlias*.py")}
    say(files == {f"NukeAlias{a.nuke}" for a in aliases.ALIASES}, f"every alias has its PyPlug ({len(files)})")
    for alias in aliases.ALIASES:
        text = (plugin / "aliases" / f"NukeAlias{alias.nuke}.py").read_text(encoding="ascii")
        if f'return "{alias.plugin_id}"' not in text or f'return "{alias.grouping}"' not in text:
            say(False, f"NukeAlias{alias.nuke}.py names {alias.plugin_id} in {alias.grouping}")
    files = {p.stem for p in (plugin / "gizmos").glob("NukeGizmo*.py")}
    say(files == {f"NukeGizmo{g.name}" for g in gizmos.GIZMOS}, f"every gizmo has its PyPlug ({len(files)})")
    for gizmo in gizmos.GIZMOS:
        text = (plugin / "gizmos" / f"NukeGizmo{gizmo.name}.py").read_text(encoding="ascii")
        if (f'return "{gizmo.plugin_id}"' not in text or f'return "{gizmo.grouping}"' not in text
                or "getIsToolset" in text or "NatronGui" in text):
            say(False, f"NukeGizmo{gizmo.name}.py is a Group PyPlug {gizmo.plugin_id} in {gizmo.grouping}, no "
                "NatronGui")
    studio = LAYER / "ext" / "toolsets"
    wanted = sorted(toolset_recipes.file_name(name) for name in toolset_recipes.RECIPES)
    found = sorted(p.name for p in studio.glob("*.xml"))
    say(found == wanted and all("<Clipboard" in (studio / n).read_text(encoding="utf-8") for n in found),
        f"every studio ToolSet has its file of Natron's copied nodes ({', '.join(found) or 'none'}; "
        "layer/tools/make_toolsets.py makes them)")
    recipes = expressions.recipes()
    say(recipes and all(r.text() for r in recipes), f"every expression recipe makes valid Python ({len(recipes)})")


def base_environment(tmp: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("NATRON_", "OCIO", "SINGERIE_"))}
    folders = {name: tmp / name for name in ("natron_cache", "home", "temp", "config", "out")}
    for folder in folders.values():
        folder.mkdir(parents=True, exist_ok=True)
    shutil.copytree(HERE / "fixtures" / "nuke_home" / ".nuke", folders["home"] / ".nuke", dirs_exist_ok=True)
    env.update({
        "NATRON_PLUGIN_PATH": str(LAYER / "ext" / "plugin"),
        "NATRON_DISK_CACHE_PATH": str(folders["natron_cache"]),
        "USERPROFILE": str(folders["home"]),
        "HOME": str(folders["home"]),
        "TEMP": str(folders["temp"]),
        "TMP": str(folders["temp"]),
        "PYTHONDONTWRITEBYTECODE": "1",
        "NATRON_LAYER_CONFIG_DIR": str(folders["config"]),
        "NATRON_LAYER_SMOKE_OUT": str(folders["out"]),
        "NATRON_LAYER_SMOKE_HOME": str(folders["home"]),
        "NATRON_LAYER_SMOKE_DIR": str(HERE),
    })  # fmt: skip
    return env


def packaged(renderer: str) -> bool:
    """A build made by tools/package_build.py carries the layer itself (Plugins/PyPlugs/layer)."""
    return (Path(renderer).resolve().parents[1] / "Plugins" / "PyPlugs" / "layer" / "layer_plugin.txt").is_file()


def natron_checks(renderer: str, tmp: Path, say: Say) -> None:
    env = base_environment(tmp)
    if packaged(renderer):
        env.pop("NATRON_PLUGIN_PATH")  # the build's own copy of the layer is what's tested
        env["NATRON_LAYER_SMOKE_PACKAGED"] = str(Path(renderer).resolve().parents[1])
    code, output = run([renderer, "-t", str(HERE / "smoke_checks.py")], env, "NatronRenderer -t smoke_checks.py")
    say(code == 0 and "SMOKE CHECKS PASSED" in output, "the checks inside Natron passed")


def gui_checks(renderer: str, tmp: Path, say: Say) -> None:
    natron = Path(renderer).with_name("Natron.exe")
    if not natron.is_file():
        say(False, f"Natron.exe next to the renderer ({natron})")
        return
    env = base_environment(tmp / "gui")
    probe = str(HERE / "gui_probe")
    env["NATRON_PLUGIN_PATH"] = probe if packaged(renderer) else f"{LAYER / 'ext' / 'plugin'};{probe}"
    env["NATRON_LAYER_SMOKE_REFERENCES"] = str(tmp / "out" / "toolset_references.json")
    code, _output = run([str(natron)], env, "Natron's window with the layer and the probe (about 40 s)", timeout=300)
    report = tmp / "gui" / "out" / "gui_probe.json"
    if not report.is_file():
        say(False, "the probe in Natron's window wrote its report")
        return
    found = json.loads(report.read_text(encoding="utf-8"))
    for ok, what in found["results"]:
        say(ok, what)
    for modal in found.get("modal", []):
        print(f"    a dialog came up: {modal['title']!r}: {modal['text'][:120]!r} {modal['buttons']}")
    say(code == 0 and found["passed"], "the window checks passed")


def project_checks(renderer: str, tmp: Path, say: Say) -> None:
    """The comps saved by the checks, rendered by a NatronRenderer without the layer."""
    jobs = []
    for path in (tmp / "out" / "project_jobs.json", tmp / "gui" / "out" / "project_jobs_gui.json"):
        if path.is_file():
            jobs.extend(json.loads(path.read_text(encoding="utf-8")))
    if not jobs:
        say(False, "the checks inside Natron saved comps to render without the layer")
        return
    merged = tmp / "out" / "all_project_jobs.json"
    merged.write_text(json.dumps(jobs, indent=1), encoding="utf-8")
    env = base_environment(tmp / "plain")
    env.pop("NATRON_PLUGIN_PATH")
    env["NATRON_LAYER_SMOKE_JOBS"] = str(merged)
    env["NATRON_LAYER_SMOKE_OUT"] = str(tmp / "out")
    what = "without the layer"
    if packaged(renderer):
        what = "of the build (it carries the layer; the comps' gizmos still open from the comps)"
        env["NATRON_LAYER_SMOKE_PACKAGED"] = "1"
    code, output = run([renderer, "-t", str(HERE / "project_checks.py")], env,
                       f"NatronRenderer {what} -t project_checks.py ({len(jobs)} saved comps)")
    say(code == 0 and "PROJECT CHECKS PASSED" in output, "the saved comps render without the layer")


def main() -> int:
    sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--renderer", help="the release's NatronRenderer (default: NATRON_LAYER_RENDERER)")
    parser.add_argument("--gui", action="store_true", help="also open Natron's window briefly with the probe")
    parser.add_argument("--keep", action="store_true", help="keep the temporary folder")
    args = parser.parse_args()
    renderer = find_renderer(args.renderer)
    if renderer is None:
        print("NatronRenderer wasn't found: pass --renderer (or set NATRON_LAYER_RENDERER).")
        return 1
    release = Path(renderer).resolve().parents[1]
    say = Say()
    unit_tests(say)
    repository_checks(say)
    before = own_state(release)
    switches_before = registry_values() if os.name == "nt" else []
    tmp = Path(tempfile.mkdtemp(prefix="natron_layer_smoke_"))
    try:
        natron_checks(renderer, tmp, say)
        if args.gui:
            gui_checks(renderer, tmp, say)
        project_checks(renderer, tmp, say)
    finally:
        taken = forget_layer_switches(switches_before)
        if taken:
            print(f"    took out the {len(taken)} switches Natron recorded for the layer's PyPlugs during the test")
        if args.keep:
            print(f"Kept {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    compare(before, own_state(release), say)
    print("All layer smoke checks passed." if say.ok else "Layer smoke checks FAILED.")
    return 0 if say.ok else 1


if __name__ == "__main__":
    sys.exit(main())
