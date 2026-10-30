# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Download MSYS2's MINGW64 packages as they stood on a given day, for a repeatable source build.

MSYS2 is "rolling": its package list only ever holds the newest versions, and packages Natron needs leave the
MINGW64 list from time to time (PySide6 and OpenImageIO had left it by late October 2026). Its package server
keeps the older package files though, each with its date. This script picks, for every package Natron's build
needs and everything those need, the newest file published on or before the given day, downloads it (with its
signature) from the official server into a cache folder, and writes a lock file listing what it picked. Then
`pacman -U` installs exactly that set (pacman checks every signature against MSYS2's keys).

    python -I msys2_snapshot.py --date 2026-10-02 --cache <folder> --bsdtar <msys64>/usr/bin/bsdtar.exe \
        --lock <folder>/mingw64-2026-10-02.lock mingw-w64-x86_64-qt6-base mingw-w64-x86_64-pyside6 ...

Only the Python standard library; reads nothing but MSYS2's own server.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import hashlib
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

REPO = "https://repo.msys2.org/mingw/mingw64/"
PREFIX = "mingw-w64-x86_64-"
ENTRY = re.compile(
    r'<a href="(' + re.escape(PREFIX) + r'[^"]+?-any\.pkg\.tar\.(?:zst|xz))">[^<]*</a>\s+(\d\d-\w\w\w-\d{4} \d\d:\d\d)'
)


def read_index(cache: str) -> list[tuple[str, str, str, datetime.datetime]]:
    """The server's file list: (file, package name, version, date)."""
    path = os.path.join(cache, "index.html")
    if not os.path.exists(path):
        urllib.request.urlretrieve(REPO, path)
    with open(path, encoding="utf-8") as f:
        html = f.read()
    rows = []
    for m in ENTRY.finditer(html):
        file, date = m.groups()
        file = urllib.parse.unquote(file)
        base = file[len(PREFIX) :].rsplit("-any.pkg.tar", 1)[0]
        name, ver, rel = base.rsplit("-", 2)
        rows.append((file, PREFIX + name, ver + "-" + rel, datetime.datetime.strptime(date, "%d-%b-%Y %H:%M")))
    return rows


def pick(rows, cutoff: datetime.datetime) -> dict[str, tuple[str, str]]:
    """For each package name, the newest file published on or before the cut-off: name -> (file, version)."""
    best: dict[str, tuple[datetime.datetime, str, str]] = {}
    for file, name, ver, date in rows:
        if date <= cutoff and (name not in best or date > best[name][0]):
            best[name] = (date, file, ver)
    return {n: (f, v) for n, (_d, f, v) in best.items()}


def fetch(cache: str, file: str) -> str:
    path = os.path.join(cache, file)
    for target in (file, file + ".sig"):
        out = os.path.join(cache, target)
        if not os.path.exists(out):
            urllib.request.urlretrieve(REPO + urllib.parse.quote(target), out + ".part")
            os.replace(out + ".part", out)
    return path


def pkginfo(bsdtar: str, path: str) -> dict[str, list[str]]:
    text = subprocess.run([bsdtar, "-xOf", path, ".PKGINFO"], check=True, capture_output=True, text=True).stdout
    info: dict[str, list[str]] = {}
    for line in text.splitlines():
        if " = " in line and not line.startswith("#"):
            key, value = line.split(" = ", 1)
            info.setdefault(key, []).append(value)
    return info


def dep_name(dep: str) -> str:
    return re.split(r"[<>=]", dep, maxsplit=1)[0].strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date", required=True, help="the day to stand on, YYYY-MM-DD (packages published that day count)")
    ap.add_argument("--cache", required=True, help="folder for the downloaded packages")
    ap.add_argument("--bsdtar", required=True, help="MSYS2's bsdtar.exe (reads each package's dependency list)")
    ap.add_argument("--lock", required=True, help="where to write the list of packages picked")
    ap.add_argument("--jobs", type=int, default=6, help="downloads at once")
    ap.add_argument(
        "--provider",
        action="append",
        default=[],
        metavar="VIRTUAL=PACKAGE",
        help="who provides a virtual name the script can't see before downloading (e.g. fc-libs=libgfortran)",
    )
    ap.add_argument("packages", nargs="+", help="what the build needs (MINGW64 package names)")
    args = ap.parse_args()
    os.makedirs(args.cache, exist_ok=True)
    cutoff = datetime.datetime.strptime(args.date, "%Y-%m-%d") + datetime.timedelta(days=1) - datetime.timedelta(minutes=1)
    chosen = pick(read_index(args.cache), cutoff)

    provides: dict[str, str] = {}
    extra_roots = set()
    for item in args.provider:
        virtual, real = (PREFIX + x if not x.startswith(PREFIX) else x for x in item.split("=", 1))
        provides[virtual] = real
        extra_roots.add(real)
    done: dict[str, tuple[str, str]] = {}
    missing: set[str] = set()
    todo = set(args.packages) | extra_roots
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        while todo:
            batch = {}
            for name in sorted(todo):
                if name in done or name in provides:
                    continue
                if name not in chosen:
                    # A virtual name (e.g. "libwinpthread" provided by "libwinpthread-git") or gone before the day.
                    alt = name + "-git"
                    if alt in chosen:
                        provides[name] = alt
                        if alt not in done:
                            batch[alt] = chosen[alt]
                    else:
                        missing.add(name)
                    continue
                batch[name] = chosen[name]
            todo = set()
            futures = {pool.submit(fetch, args.cache, f): (n, f, v) for n, (f, v) in batch.items()}
            for fut in concurrent.futures.as_completed(futures):
                name, file, ver = futures[fut]
                path = fut.result()
                info = pkginfo(args.bsdtar, path)
                done[name] = (file, ver)
                for prov in info.get("provides", []):
                    provides.setdefault(dep_name(prov), name)
                for dep in info.get("depend", []):
                    d = dep_name(dep)
                    if d.startswith(PREFIX) and d not in done and d not in provides:
                        todo.add(d)
            print(f"  {len(done)} packages so far", file=sys.stderr)
    missing = {m for m in missing if m not in provides}
    if missing:
        print("Not found on or before " + args.date + ": " + ", ".join(sorted(missing)), file=sys.stderr)
        return 1
    with open(args.lock, "w", encoding="ascii", newline="\n") as f:
        f.write(f"# MSYS2 MINGW64 packages as of {args.date} (newest file on {REPO} published that day or before)\n")
        for name in sorted(done):
            file, ver = done[name]
            with open(os.path.join(args.cache, file), "rb") as pkg:
                digest = hashlib.sha256(pkg.read()).hexdigest()
            f.write(f"{name} {ver} {digest} {file}\n")
    print(f"{len(done)} packages, list in {args.lock}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
