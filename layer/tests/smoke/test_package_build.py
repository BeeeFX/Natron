# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The build's licence texts (layer/tools/package_build.py), on a made-up MSYS2 folder: no Natron, no build.

    python layer/tests/smoke/test_package_build.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
sys.dont_write_bytecode = True
import package_build  # noqa: E402

PREFIX = "mingw-w64-x86_64-"


def package(msys2: Path, name: str, version: str, files: dict[str, str], licence: str = "spdx:MIT") -> None:
    """A package as pacman leaves it: its files on disk and its local database entry (desc, files)."""
    entry = msys2 / "var" / "lib" / "pacman" / "local" / f"{PREFIX}{name}-{version}"
    entry.mkdir(parents=True)
    (entry / "desc").write_text(f"%NAME%\n{PREFIX}{name}\n\n%LICENSE%\n{licence}\n\n%URL%\nhttps://example.org/{name}\n",
                                encoding="utf-8")
    (entry / "files").write_text("%FILES%\n" + "\n".join(files) + "\n", encoding="utf-8")
    for path, text in files.items():
        (msys2 / path).parent.mkdir(parents=True, exist_ok=True)
        (msys2 / path).write_text(text, encoding="utf-8")


class Licences(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = Path(tempfile.mkdtemp(prefix="natron_layer_licences_"))
        self.root = self.folder / "natron-build"
        msys2 = self.root / "msys64"
        package(msys2, "zlib", "1.3-1", {"mingw64/bin/zlib1.dll": "dll", "mingw64/share/licenses/zlib/LICENSE": "zlib"})
        package(msys2, "gmp", "6.3-1", {"mingw64/bin/libgmp-10.dll": "dll",
                                        "mingw64/share/doc/gmp/COPYING.LESSERv3": "LGPL"}, "spdx:LGPL-3.0-or-later")
        package(msys2, "x265", "4.1-1", {"mingw64/bin/libx265.dll": "dll"}, "spdx:GPL-2.0-or-later")
        package(msys2, "cmake", "4.4-1", {"mingw64/bin/cmake.exe": "exe"})
        self.lock = self.root / "mingw64-2026-10-02.lock"
        self.lock.write_text("# lock\n" + "".join(f"{PREFIX}{n} {v} 0 {PREFIX}{n}-{v}-any.pkg.tar.zst\n" for n, v in (
            ("zlib", "1.3-1"), ("gmp", "6.3-1"), ("x265", "4.1-1"), ("cmake", "4.4-1"))), encoding="utf-8")
        (self.root / "cycles").mkdir()
        (self.root / "cycles" / "LICENSE").write_text("Apache-2.0", encoding="utf-8")
        self.build = self.folder / "build"
        (self.build / "Resources").mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.folder, ignore_errors=True)

    def test_every_text_is_copied_and_the_missing_ones_named(self) -> None:
        without = package_build.copy_licences(self.build, self.root, self.lock)
        licences = self.build / "Resources" / "licenses"
        self.assertTrue((self.build / "LICENSE.txt").is_file())
        self.assertTrue((self.build / "LICENSE-layer.txt").is_file())
        self.assertEqual((licences / "zlib" / "LICENSE").read_text(encoding="utf-8"), "zlib")
        self.assertTrue((licences / "gmp" / "COPYING.LESSERv3").is_file(), "a text kept with the documents")
        self.assertTrue((licences / "cycles" / "LICENSE").is_file())
        self.assertEqual(without, [f"{PREFIX}x265"], "a DLL with no licence text is named; a tool without DLL isn't")
        listed = (licences / "PACKAGES.txt").read_text(encoding="utf-8")
        self.assertIn("x265 4.1-1: spdx:GPL-2.0-or-later https://example.org/x265  (no text)", listed)

    def test_a_release_build_gets_the_two_licences_only(self) -> None:
        self.assertEqual(package_build.copy_licences(self.build, None, None), [])
        self.assertTrue((self.build / "LICENSE.txt").is_file())
        self.assertFalse((self.build / "Resources" / "licenses").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
