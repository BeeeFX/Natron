# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Make a build of this fork from one of Niik-l's portable releases: a copy of the release with the layer added,
zipped, ready to be published for Singerie's software manager (any Python 3.11+, standard library only):

    python layer/tools/package_build.py --release "<folder holding bin/ and Plugins/>" --tag natron-2.6-2026.09.20
                                        [--number 1] [--out <folder>] [--no-archive]

or from this fork's own source build (layer/README.md, "Building from source"), the folder Niik-l's
``tools/win-build/06-install.sh`` staged (App/, Renderer/, lib/, Plugins/, Resources/, etc/):

    python layer/tools/package_build.py --source-build "<NATRON_ROOT>/Natron-install" --tag natron-2.6-2026.10.02 \\
                                        --number 3 --msys2-lock "<NATRON_ROOT>/mingw64-2026-10-02.lock"

A source build is laid out like Niik-l's portable releases (bin/ holding both programs, their DLLs and platforms/;
lib/, Plugins/, Resources/, etc/ beside it), so Singerie's software manager and the smoke test find it the same way;
its SOURCE.txt names the commit it was built from (Niik-l's code with this fork's core patches) and the MSYS2
package list it was built with (kept as ``Resources/layer/MSYS2-PACKAGES.lock``).

The release (or source build) folder is only read. In the copy:

- ``Plugins/PyPlugs/layer/`` gets the layer's startup scripts, alias nodes and gizmos (``layer/ext/plugin``): Natron
  reads its bundled PyPlugs folder at every start, so the build is Nuke-like with nothing set by whoever launches it;
- ``Resources/layer/`` gets the rest of the layer (compat/, ext/python, ext/qss, ext/presets, ext/toolsets, ext/icons,
  ext/fonts,
  upstream.toml, the licence, FORK.md and GAPS.md), with ``BUILD.toml`` (the version, the release it's based on, the
  layer's commit)
  and ``SOURCE.txt`` (where the corresponding source is, as the GPL asks when a build is handed to someone).

The version is ``2.6.0+<release date>.sng<number>`` (``2.6.0+2026.09.20.sng1``): Singerie's software manager reads
a fork build's version as ``2.6.0+<build>``, so pins like ``2.6.x``, ``2.6.0`` and the exact build all match it, and
``.sng2`` sorts after ``.sng1`` and after the plain release ``2.6.0+2026.09.20``. The archive's name can't hold
``+`` (Singerie's build list refuses it), so it's ``Natron-2.6.0-2026.09.20.sng1-win64.zip``, holding one folder,
``Natron-2.6.0-2026.09.20.sng1``, which the software manager makes the install itself.

Nothing is published or uploaded: publishing a build on Singerie is an admin's step (Admin › Desktop app › Builds),
with the archive's SHA-256 printed here.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

LAYER = Path(__file__).resolve().parents[1]
REPO = LAYER.parent
TAG = re.compile(r"^natron-(\d+)\.(\d+)-(\d{4}\.\d{2}\.\d{2})$")
RESOURCE_PARTS = ("compat", "ext/python", "ext/qss", "ext/presets", "ext/toolsets", "ext/icons", "ext/fonts",
                  "upstream.toml", "LICENSE",
                  "README.md", "GAPS.md")


def version_for(tag: str, number: int) -> str:
    """``natron-2.6-2026.09.20`` and 1 → ``2.6.0+2026.09.20.sng1``."""
    found = TAG.match(tag)
    if not found:
        raise SystemExit(f"'{tag}' isn't one of Niik-l's release tags (natron-2.6-YYYY.MM.DD).")
    major, minor, date = found.groups()
    return f"{major}.{minor}.0+{date}.sng{number}"


def file_safe(version: str) -> str:
    return version.replace("+", "-")


def git(*args: str) -> str:
    done = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, check=False)
    return done.stdout.strip() if done.returncode == 0 else ""


def release_root(folder: Path) -> Path:
    """The folder holding bin/Natron.exe (the release folder itself, or its only child: Natron-release)."""
    for candidate in (folder, *[c for c in folder.iterdir() if c.is_dir()]):
        if (candidate / "bin" / "NatronRenderer.exe").is_file() or (candidate / "bin" / "NatronRenderer").is_file():
            return candidate
    raise SystemExit(f"No Natron release in {folder} (bin/NatronRenderer was looked for).")


def stage_source_build(install: Path, target: Path) -> None:
    """Lay a win-build install (App/, Renderer/, lib/, Plugins/, Resources/, etc/) out as Niik-l's portable
    releases are: bin/ with both programs (App/ and Renderer/ hold the same DLLs), the rest beside it."""
    app = install / "App"
    if not (app / "Natron.exe").is_file() or not (install / "Renderer" / "NatronRenderer.exe").is_file():
        raise SystemExit(f"No source build in {install} (App/Natron.exe and Renderer/NatronRenderer.exe were looked for).")
    print(f"Copying {install} as a portable layout ...", flush=True)
    shutil.copytree(app, target / "bin")
    shutil.copy2(install / "Renderer" / "NatronRenderer.exe", target / "bin" / "NatronRenderer.exe")
    for part in ("lib", "Plugins", "Resources", "etc"):
        if (install / part).is_dir():
            shutil.copytree(install / part, target / part)
    (target / "THIRD-PARTY.txt").write_text(
        "Natron 2.6 (Niik-l's fork, with the BeeeFX fork's core patches and layer): third-party software\n"
        "=====================================================================================\n\n"
        "Natron is free software (GNU General Public License). This build was compiled from source; see\n"
        "Resources/layer/SOURCE.txt for its corresponding source.\n\n"
        "It bundles: the Cycles renderer (Apache-2.0, https://github.com/Niik-l/cycles, branch feature/cycles-deep);\n"
        "the openfx-misc, openfx-io and openfx-arena OFX plug-ins (GPL, https://github.com/NatronGitHub);\n"
        "the community PyPlugs (various licences, https://github.com/NatronGitHub/natron-plugins);\n"
        "the OpenColorIO configurations (https://github.com/NatronGitHub/OpenColorIO-Configs);\n"
        "wgpu-native (MIT or Apache-2.0, https://github.com/gfx-rs/wgpu-native);\n"
        "Qt 6, Python, Boost, Cairo, OpenImageIO, OpenEXR, OpenColorIO, OpenVDB, OpenImageDenoise, Embree,\n"
        "OpenSubdiv, FFmpeg and other runtime libraries as DLLs from the MSYS2 MinGW-w64 distribution\n"
        "(https://www.msys2.org), each under its own licence, the exact packages listed in\n"
        "Resources/layer/MSYS2-PACKAGES.lock (their sources are in MSYS2's package repositories).\n",
        encoding="utf-8",
    )


def lay_out(release: Path, target: Path, version: str, tag: str, source_build: bool = False,
            msys2_lock: Path | None = None) -> None:
    if target.exists():
        raise SystemExit(f"{target} exists already: remove it or choose another --out.")
    if (release / "Plugins" / "PyPlugs" / "layer").exists():
        raise SystemExit(f"{release} already holds a layer (Plugins/PyPlugs/layer): start from Niik-l's release.")
    if source_build:
        stage_source_build(release, target)
    else:
        print(f"Copying {release} ...", flush=True)
        shutil.copytree(release, target)
    plugin = target / "Plugins" / "PyPlugs" / "layer"
    shutil.copytree(LAYER / "ext" / "plugin", plugin, ignore=shutil.ignore_patterns("__pycache__"))
    resources = target / "Resources" / "layer"
    for part in RESOURCE_PARTS:
        source = LAYER / part
        if source.is_dir():
            shutil.copytree(source, resources / part, ignore=shutil.ignore_patterns("__pycache__"))
        elif source.is_file():
            (resources / part).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, resources / part)
    shutil.copy2(REPO / "FORK.md", resources / "FORK.md")
    commit = git("rev-parse", "HEAD") or "unknown"
    dirty = bool(git("status", "--porcelain", "--", "layer", "FORK.md", *(("Engine", "Gui") if source_build else ())))
    if msys2_lock is not None:
        shutil.copy2(msys2_lock, resources / "MSYS2-PACKAGES.lock")
    (resources / "BUILD.toml").write_text(
        "# What this build is (layer/tools/package_build.py).\n"
        f'version = "{version}"\n'
        f'based_on = "{tag}"\n'
        f'built_from_source = {"true" if source_build else "false"}\n'
        f'layer_commit = "{commit}"\n'
        f"layer_changes_not_committed = {'true' if dirty else 'false'}\n"
        f'made = "{datetime.datetime.now().isoformat(timespec="seconds")}"\n',
        encoding="utf-8",
    )
    source_text = (
        "This build was compiled from the fork's repository (https://github.com/BeeeFX/Natron) at commit " + commit
        + ":\nNiik-l's Natron 2.6 source at " + tag + " (https://github.com/Niik-l/Natron, GPL-2.0-or-later) with this\n"
        "fork's core patches (layer/patches/, also carried as commits) and its layer (layer/, GPL-3.0-or-later, see\n"
        "LICENSE here), built with Niik-l's own scripts (tools/win-build) against the MSYS2 packages listed in\n"
        "MSYS2-PACKAGES.lock here (sources in MSYS2's repositories) and the plug-ins at the refs of\n"
        "tools/win-build/config.sh. Whoever hands this build on must make that source available with it, as the\n"
        "GPL asks.\n"
    )
    (resources / "SOURCE.txt").write_text(
        source_text if source_build else
        "This build is Niik-l's Natron 2.6 release " + tag + " (https://github.com/Niik-l/Natron, GPL-2.0-or-later,\n"
        "with its own bundled parts' licences) with this fork's layer added (GPL-3.0-or-later, see LICENSE here).\n"
        "Its corresponding source: the fork's repository at commit " + commit + " (branch sng/main), which holds\n"
        "Niik-l's source at " + tag + " and the layer (layer/). Whoever hands this build on must make that source\n"
        "available with it, as the GPL asks.\n",
        encoding="utf-8",
    )
    if dirty:
        print("Note: the layer has changes that aren't committed; BUILD.toml says so. Commit before publishing.")


def archive(folder: Path, destination: Path) -> tuple[str, int]:
    print(f"Zipping into {destination} ...", flush=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                zipped.write(path, Path(folder.name) / path.relative_to(folder))
    digest = hashlib.sha256()
    with open(destination, "rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest(), destination.stat().st_size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    origin = parser.add_mutually_exclusive_group(required=True)
    origin.add_argument("--release", help="Niik-l's portable release folder (holding bin/)")
    origin.add_argument("--source-build", help="a source build's install folder (App/, Renderer/: win-build's 06)")
    parser.add_argument("--msys2-lock", help="the MSYS2 package list the source build was made with")
    parser.add_argument("--tag", required=True, help="its release tag, natron-2.6-YYYY.MM.DD")
    parser.add_argument("--number", type=int, default=1, help="the layer's build number on that release (sng<n>)")
    parser.add_argument("--out", default=str(LAYER / "dist"), help="where the build goes (default: layer/dist)")
    parser.add_argument("--no-archive", action="store_true", help="lay the folder out without zipping it")
    args = parser.parse_args()
    version = version_for(args.tag, args.number)
    release = Path(args.source_build) if args.source_build else release_root(Path(args.release))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    folder = out / f"Natron-{file_safe(version)}"
    lay_out(release, folder, version, args.tag, source_build=bool(args.source_build),
            msys2_lock=Path(args.msys2_lock) if args.msys2_lock else None)
    print(f"Laid out: {folder}")
    if not args.no_archive:
        zipped = out / f"Natron-{file_safe(version)}-win64.zip"
        sha256, size = archive(folder, zipped)
        print(f"Archive: {zipped.name}\nVersion: {version}\nSHA-256: {sha256}\nSize: {size} bytes")
        print("Publishing it on Singerie is an admin's step (Admin > Desktop app > Builds); nothing was uploaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
