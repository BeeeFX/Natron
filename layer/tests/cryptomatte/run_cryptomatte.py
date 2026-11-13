# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The Cryptomatte node's test against a portable release of the fork (any Python 3.10+, standard library only):

    python layer/tests/cryptomatte/run_cryptomatte.py --renderer "<release>/bin/NatronRenderer.exe"
        [--karma <folder of a Karma render's crypto_object_raw_####.exr>]
        [--cycles <a Blender multi-layer EXR with its Cryptomatte inside>]
        [--cycles-split <a Blender frame's crypto_object_raw_####.exr written apart, without a manifest>] [--keep]

It:

1. runs the arithmetic's own tests (test_cryptomatte_data.py: the hash, the list, the preview's colours);
2. makes renders whose every coverage is known (fixtures.py) and, given, takes the real ones (only read);
3. runs cryptomatte_checks.py inside NatronRenderer, with only the layer's plug-in folder on NATRON_PLUGIN_PATH and
   Natron's disk cache, home and TEMP in a temporary folder, Natron's own OpenGL setting untouched: the node made,
   the layers found by name, mattes rendered for lists of names, wildcards and raw IDs, picking walks, a frame
   without a manifest;
4. compares every matte with the truth summed here straight from the file's ranks (edges, motion blur and every
   rank included), pixel by pixel, and the outputs' colour channels, the preview's colours and the timings;
5. renders the saved comp in a NatronRenderer **without the layer** (the smoke test's project_checks.py): the same
   pixels from the Groups saved in the comp;
6. Natron's settings: every value under HKCU\\Software\\INRIA read before each NatronRenderer run and put back
   exactly afterwards (Natron records switches for the PyPlugs it registers), then compared with the smoke test's
   own state check (the registry, Natron's folders, the release folder): unchanged.

Exits with 1 when something fails.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAYER = HERE.parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAYER / "tests" / "smoke"))
sys.path.insert(0, str(LAYER / "ext" / "python"))

import exr_io  # noqa: E402
import fixtures  # noqa: E402
import run_smoke  # noqa: E402  (its state check and its Say)
from natron_layer import cryptomatte_data as data  # noqa: E402

TOLERANCE = 2e-6  # a 32-bit float sum of up to 16 ranks against the same sum in double precision

# --- Natron's settings in the registry: read before, put back after ---

KEY = r"Software\INRIA"


def registry_read(path: str = KEY) -> dict[str, dict[str, tuple[int, object]]]:
    if os.name != "nt":
        return {}
    import winreg

    found: dict[str, dict[str, tuple[int, object]]] = {}
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path)
    except OSError:
        return found
    with key:
        values, subkeys, i = {}, [], 0
        while True:
            try:
                name, value, kind = winreg.EnumValue(key, i)
            except OSError:
                break
            values[name] = (kind, value)
            i += 1
        i = 0
        while True:
            try:
                subkeys.append(winreg.EnumKey(key, i))
            except OSError:
                break
            i += 1
    found[path] = values
    for sub in subkeys:
        found.update(registry_read(path + "\\" + sub))
    return found


def registry_put_back(before: dict) -> list[str]:
    """Every value as it was before (new ones taken out, changed ones written back); the names it touched."""
    if os.name != "nt":
        return []
    import winreg

    after = registry_read()
    touched = []
    for path, values in after.items():
        for name, value in values.items():
            if before.get(path, {}).get(name) != value:
                touched.append(f"{path}\\{name}")
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as key:
                    if name in before.get(path, {}):
                        kind, data_ = before[path][name]
                        winreg.SetValueEx(key, name, 0, kind, data_)
                    else:
                        winreg.DeleteValue(key, name)
    for path, values in before.items():
        for name, (kind, data_) in values.items():
            if name not in after.get(path, {}):
                touched.append(f"{path}\\{name}")
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
                    winreg.SetValueEx(key, name, 0, kind, data_)
    return touched


def natron_run(renderer: str, script: Path, env: dict[str, str], what: str, say) -> str:
    before = registry_read()
    try:
        _, output = run_smoke.run([renderer, "-t", str(script)], env, what)
    finally:
        touched = registry_put_back(before)
        if touched:
            print(f"    Natron wrote {len(touched)} registry value(s) during the run, put back as they were: "
                  + ", ".join(t.rsplit("\\", 1)[-1] for t in touched[:6]) + ("…" if len(touched) > 6 else ""))
        say(registry_read() == before, "Natron's registry values are exactly as before this run")
    return output


# --- The plan ---


def plan(made: dict[str, str], args: argparse.Namespace) -> list[dict]:
    synth = made["objects"]
    image = exr_io.read(synth)
    manifest = fixtures.manifest_of(image, "CryptoObject")
    tree2 = fixtures.first_rank_pixel(image, "CryptoObject", manifest["/root/set/tree_02"])
    hero = fixtures.first_rank_pixel(image, "CryptoObject", manifest["/root/chars/hero"])
    raw = f"<{data.bits_to_float(manifest['/root/set/rock'])!r}>"
    cases = [
        {"name": "synth_hero", "source": synth, "list": "/root/chars/hero",
         "expect_layers": ["CryptoObject", "CryptoMaterial"], "expect_layer": "CryptoObject",
         "expect_manifest": len(fixtures.OBJECTS), "save": True},
        {"name": "synth_trees", "source": synth, "list": "/root/set/tree_0*"},
        {"name": "synth_all_but_hero", "source": synth, "list": "*\n-/root/chars/hero"},
        {"name": "synth_raw_id", "source": synth, "list": raw},
        {"name": "synth_comma_name", "source": synth, "list": '"car, red", lamp'},
        {"name": "synth_every_name", "source": synth, "list": "\n".join(fixtures.OBJECTS)},
        {"name": "synth_empty", "source": synth, "list": ""},
        {"name": "synth_material", "source": synth, "layer": "CryptoMaterial", "list": "mat_wood, mat_glass",
         "expect_layer": "CryptoMaterial", "save": True},
        {"name": "synth_image_alpha", "source": synth, "list": "/root/set/*", "output": 0},
        {"name": "synth_premultiplied", "source": synth, "list": "/root/set/*", "output": 1},
        {"name": "synth_preview", "source": synth, "list": "/root/chars/hero*", "preview": True},
        {"name": "lower_assets", "source": made["assets_lower"], "list": "*_asset\n-ground_asset",
         "expect_layers": ["ViewLayer.CryptoAsset"], "expect_manifest": len(fixtures.ASSETS)},
        {"name": "image_input", "source": made["no_manifest"], "image": made["assets_lower"],
         "list": "/root/chars/hero", "output": 0},
        {"kind": "pick", "name": "synth_picked", "source": synth, "wildcard": "/root/set/*",
         "manifest_names": fixtures.OBJECTS,
         "picks": [{"name": "/root/chars/hero", "bits": f"{manifest['/root/chars/hero']:08x}", "x": hero[0],
                    "y": hero[1]},
                   {"name": "/root/set/tree_02", "bits": f"{manifest['/root/set/tree_02']:08x}", "x": tree2[0],
                    "y": tree2[1]}]},
        {"kind": "no_manifest", "name": "no_manifest", "source": made["no_manifest"], "layer": "CryptoObject",
         "name_only": "/root/chars/hero", "wildcard": "/root/set/tree_*", "manifest_file": made["names_json"]},
        {"kind": "shared_read", "name": "shared_read", "source": synth,
         "nodes": [{"name": "shared_hero", "list": "/root/chars/hero"},
                   {"name": "shared_trees", "list": "/root/set/tree_0*"},
                   {"name": "shared_hero_again", "list": "/root/chars/hero"},
                   {"name": "shared_materials", "layer": "CryptoMaterial", "list": "mat_metal"}]},
        {"name": "crowd_one", "source": made["crowd"], "list": "/root/crowd/agent_0042"},
        {"name": "crowd_thousand", "source": made["crowd"], "list": "/root/crowd/agent_0*"},
        {"name": "crowd_all", "source": made["crowd"], "list": "*"},
    ]
    if args.karma:
        for frame in (1001, 1002, 1003):
            source = os.path.join(args.karma, f"crypto_object_raw_{frame}.exr")
            if os.path.isfile(source):
                cases.append({"name": f"karma_banana_{frame}", "source": source, "list": "*/banana",
                              "expect_layer": "CryptoPrimitives", "save": frame == 1001})
                cases.append({"name": f"karma_monkey_trees_{frame}", "source": source,
                              "list": "/assets/monkey_model/monkey_model/monkey_0/monkey\n*/tree*_leaves/*"})
        material = os.path.join(args.karma, "crypto_material_raw_1001.exr")
        if os.path.isfile(material):
            cases.append({"name": "karma_material", "source": material, "list": "*monkey_mat",
                          "expect_layer": "CryptoMaterials"})
    if args.cycles:
        cases += [{"name": "cycles_cube", "source": args.cycles, "list": "cube", "save": True,
                   "expect_layers": ["ViewLayer.CryptoObject", "ViewLayer.CryptoMaterial"]},
                  {"name": "cycles_all_but_ground", "source": args.cycles, "list": "*\n-ground"},
                  {"name": "cycles_red_mat", "source": args.cycles, "layer": "ViewLayer.CryptoMaterial",
                   "list": "red_mat"}]
    if args.cycles_split:
        cases.append({"name": "cycles_split_cube", "source": args.cycles_split, "list": "cube",
                      "expect_manifest": 0})
        if args.cycles:
            cases.append({"name": "cycles_split_by_beauty_manifest", "source": args.cycles_split,
                          "list": "*\n-ground", "manifest_file": args.cycles})
    return cases


# --- Checking the pixels ---


def parse_list(text: str) -> list[str]:
    return [cell.strip() for line in text.splitlines() for row in csv.reader([line], skipinitialspace=True)
            for cell in row if cell.strip()]


def colour_of(image: exr_io.Image) -> list[list[float]] | None:
    found = [image.get(c) for c in "RGB"]
    return None if any(v is None for v in found) else found  # type: ignore[return-value]


def check_render(entry: dict, say) -> None:
    name = entry["name"]
    if not entry.get("path") or not os.path.isfile(entry["path"]):
        say(False, f"{name}: its render is there")
        return
    source = exr_io.read(entry["source"])
    manifest = fixtures.manifest_of(source, entry["layer"], entry.get("manifest_file"),
                                    os.path.dirname(entry["source"]))
    wanted = fixtures.expected_ids(parse_list(entry["list"]), manifest)
    said = {int(b, 16) for b in entry["ids"]}
    say(said == wanted, f"{name}: the node took the {len(wanted)} IDs the list stands for "
        f"({entry['list'][:60]!r} in {entry['layer']})")
    truth = fixtures.truth(source, entry["layer"], wanted)
    out = exr_io.read(entry["path"])
    alpha = out.get("A")
    if alpha is None or len(alpha) != len(truth):
        say(False, f"{name}: the render has an alpha of the source's size")
        return
    worst = max((abs(a - t) for a, t in zip(alpha, truth)), default=0.0)
    soft = sum(1 for t in truth if 0.0 < t < 0.999)
    deep = 0
    for k, (r, _, b, _) in enumerate(fixtures.rank_layers(source, entry["layer"])):
        if k:
            floats = {fixtures.as_float(i) for i in wanted}
            deep += sum(1 for i in range(len(truth)) if r[i] in floats or b[i] in floats)
    ok = say(worst <= TOLERANCE, f"{name}: the matte is the true coverage at every pixel (largest difference "
             f"{worst:.2g}; {sum(1 for t in truth if t > 0)} pixels in it, {soft} soft edge pixels, {deep} hits "
             f"beyond the first two ranks; {entry['seconds']:.2f} s)")
    if not ok:
        bad = [i for i, (a, t) in enumerate(zip(alpha, truth)) if abs(a - t) > TOLERANCE][:3]
        for i in bad:
            print(f"      pixel ({i % out.width}, {i // out.width}): {alpha[i]!r} wanted {truth[i]!r}")
    colour = colour_of(out)
    if colour is None:
        return
    if entry.get("preview"):
        first = fixtures.rank_layers(source, entry["layer"])[0][0]
        floats = {fixtures.as_float(i) for i in wanted}
        mismatched = 0
        for i, ident in enumerate(first):
            expect = data.preview_colour(data.float_to_bits(ident), ident in floats)
            if tuple(c[i] for c in colour) != expect:
                mismatched += 1
        say(mismatched == 0, f"{name}: every pixel of the preview is its first-rank object's colour, exactly "
            f"({mismatched} differ), listed ones bright, the others dim")
        return
    if entry["output"] == 2:
        say(all(c == alpha for c in colour), f"{name}: matte only: R, G and B are the matte")
        return
    picture = colour_of(exr_io.read(entry["image"] or entry["source"]))
    if picture is None:
        return
    if entry["output"] == 0:
        say(all(c == p for c, p in zip(colour, picture)), f"{name}: the image's colour passes unchanged"
            + (" (from the Image input)" if entry.get("image") else ""))
    else:
        worst = max(abs(c[i] - p[i] * alpha[i]) for c, p in zip(colour, picture) for i in range(len(alpha)))
        say(worst <= 1e-6, f"{name}: the image multiplied by the matte (largest difference {worst:.2g})")


def speed(renders: list[dict]) -> None:
    times = {r["name"]: r["seconds"] for r in renders}
    if "crowd_one" in times:
        print(f"    speed at 480 x 270, 6 ranks: 1 name {times['crowd_one']:.2f} s, 1,000 names "
              f"{times.get('crowd_thousand', 0):.2f} s, 2,000 names {times.get('crowd_all', 0):.2f} s "
              "(the whole render: reading, the matte, writing)")


# --- Main ---


def unit_tests(say) -> None:
    print("--- the arithmetic (test_cryptomatte_data.py)", flush=True)
    suite = unittest.defaultTestLoader.discover(str(HERE), pattern="test_cryptomatte_data.py")
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=1).run(suite)
    say(result.wasSuccessful(), f"the arithmetic's tests pass ({result.testsRun})")


def main() -> int:
    sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--renderer", help="the release's NatronRenderer (default: NATRON_LAYER_RENDERER)")
    parser.add_argument("--karma", help="a folder with a Karma render's crypto_object_raw_####.exr (only read)")
    parser.add_argument("--cycles", help="a Blender multi-layer EXR with Cryptomatte inside (only read)")
    parser.add_argument("--cycles-split", help="a Blender frame's crypto_object_raw EXR written apart (only read)")
    parser.add_argument("--keep", action="store_true", help="keep the temporary folder")
    args = parser.parse_args()
    say = run_smoke.Say()
    unit_tests(say)
    renderer = run_smoke.find_renderer(args.renderer)
    if renderer is None:
        print("NatronRenderer wasn't found: pass --renderer (or set NATRON_LAYER_RENDERER).")
        return 1
    release = Path(renderer).resolve().parents[1]
    before = run_smoke.own_state(release)
    tmp = Path(tempfile.mkdtemp(prefix="natron_layer_crypto_"))
    try:
        started = time.monotonic()
        made = fixtures.make(tmp / "fixtures")
        print(f"--- made-up renders written ({time.monotonic() - started:.1f} s)", flush=True)
        out = tmp / "out"
        out.mkdir()
        (tmp / "plan.json").write_text(json.dumps({"cases": plan(made, args)}, indent=1), encoding="utf-8")
        env = run_smoke.base_environment(tmp / "session")
        if run_smoke.packaged(renderer):
            env.pop("NATRON_PLUGIN_PATH")
        env.update({"NATRON_LAYER_CRYPTO_PLAN": str(tmp / "plan.json"), "NATRON_LAYER_CRYPTO_OUT": str(out),
                    "NATRON_LAYER_CRYPTO_DIR": str(HERE)})
        output = natron_run(renderer, HERE / "cryptomatte_checks.py", env, "NatronRenderer -t cryptomatte_checks.py",
                            say)
        say("CRYPTOMATTE CHECKS PASSED" in output, "the checks inside Natron passed")
        listed = out / "renders.json"
        renders = json.loads(listed.read_text(encoding="utf-8")) if listed.is_file() else []
        print(f"--- the mattes against the truth ({len(renders)} renders)", flush=True)
        for entry in renders:
            check_render(entry, say)
        speed(renders)
        jobs = out / "project_jobs.json"
        saved = json.loads(jobs.read_text(encoding="utf-8")) if jobs.is_file() else []
        if saved and saved[0]["writers"]:
            plain = run_smoke.base_environment(tmp / "plain")
            plain.pop("NATRON_PLUGIN_PATH")
            plain.update({"NATRON_LAYER_SMOKE_JOBS": str(jobs), "NATRON_LAYER_SMOKE_OUT": str(tmp / "plain_out")})
            if run_smoke.packaged(renderer):
                plain["NATRON_LAYER_SMOKE_PACKAGED"] = "1"
            output = natron_run(renderer, LAYER / "tests" / "smoke" / "project_checks.py", plain,
                                "NatronRenderer without the layer -t project_checks.py (the saved comp)", say)
            say("PROJECT CHECKS PASSED" in output, "the saved comp renders the same mattes without the layer")
        else:
            say(False, "the checks saved a comp with Cryptomatte nodes for the run without the layer")
    finally:
        if args.keep:
            print(f"Kept {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    run_smoke.compare(before, run_smoke.own_state(release), say)
    print("All Cryptomatte checks passed." if say.ok else "Cryptomatte checks FAILED.")
    return 0 if say.ok else 1


if __name__ == "__main__":
    sys.exit(main())
