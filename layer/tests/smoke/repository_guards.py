# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Guards run_smoke.py runs on the repository itself, with no Natron (any Python 3.11+, standard library only):

- the patch files are the code: taking the series off this branch's tree, last to first, gives Niik-l's commit
  exactly (upstream.toml), and the look's patches stay within the budget's lines (the fixes count apart);
- FORK.md, the page a visitor reads first, names every patch of the series;
- a packaged build (``--renderer`` inside one) carries Natron's licence, the layer's and the libraries' notices.

Nothing here writes to the repository: the patches are taken off on a temporary index (GIT_INDEX_FILE).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAYER = HERE.parents[1]
REPO = LAYER.parent

# The repository's own files that aren't Natron's code: the layer, the fork's page and GitHub's folder. Everything
# else that differs from Niik-l's commit is a core change, so it must be in a patch file.
NOT_CORE = ("layer", "FORK.md", ".github")

Say = Callable[[object, str], bool]


def patch_lines(text: str) -> int:
    """The lines a patch file adds and removes (its diff's ``+`` and ``-`` lines, not the file names nor the
    signature line ``-- `` git format-patch ends with)."""
    count = 0
    in_diff = False
    for line in text.splitlines():
        if line.startswith("diff --git "):
            in_diff = True
            continue
        if not in_diff or line.startswith(("+++ ", "--- ")) or line == "-- ":
            continue
        if line[:1] in ("+", "-"):
            count += 1
    return count


def _git(env: dict[str, str] | None = None) -> Callable[..., subprocess.CompletedProcess]:
    git = shutil.which("git") or "git"

    def run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run([git, *args], cwd=REPO, env=env, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", check=False)  # fmt: skip

    return run


def series_off_tree(series: list[str], base: str) -> tuple[list[str], list[str]]:
    """Take the series off this tree (HEAD plus the working tree's uncommitted core changes) on a temporary index.
    Returns (patches refused, core files still differing from ``base``)."""
    excluded = [f":!{p}" for p in NOT_CORE]
    with tempfile.TemporaryDirectory(prefix="natron_layer_index_") as folder:
        env = dict(os.environ, GIT_INDEX_FILE=os.path.join(folder, "index"))
        git = _git(env)
        git("read-tree", "HEAD")
        changed = [p for p in git("diff", "--name-only", "HEAD", "--", ".", *excluded).stdout.splitlines() if p]
        changed += [p for p in git("ls-files", "--others", "--exclude-standard", "--", ".", *excluded).stdout.splitlines()
                    if p]  # a new core file not added yet
        if changed:
            git("add", "--", *changed)
        for name in reversed(series):
            done = git("apply", "--cached", "--reverse", "--whitespace=nowarn", str(LAYER / "patches" / name))
            if done.returncode != 0:
                first = (done.stderr.strip().splitlines() or ["?"])[0]
                return [f"{name}: {first}"], []
        left = git("diff", "--cached", "--name-only", base, "--", ".", *excluded).stdout.splitlines()
    return [], [p for p in left if p]


def patch_checks(say: Say, series: list[str], upstream: dict) -> None:
    """A core change made without its patch file, or a patch file edited without the code, fails here."""
    base = upstream["upstream"]["commit"]
    if shutil.which("git") is None or not (REPO / ".git").exists():
        say(False, "git and the repository's history are here to compare the patch files with the code")
        return
    if _git()("cat-file", "-e", base + "^{commit}").returncode != 0:
        say(False, f"Niik-l's commit {base[:10]} is in this clone (fetch it to compare the patch files with the code)")
        return
    refused, left = series_off_tree(series, base)
    say(not refused and not left, "the patch files are the code: taking the series off this tree, last to first, "
        f"gives Niik-l's {base[:10]} exactly" + (f" (refused: {refused[0]})" if refused else "")
        + (f" (left over in {left[:5]}: regenerate those patches)" if left else ""))
    fixes = set(upstream["patches"].get("fix_files", []))
    sizes = {name: patch_lines((LAYER / "patches" / name).read_text(encoding="utf-8")) for name in series}
    look = sum(size for name, size in sizes.items() if name not in fixes)
    budget = upstream["patches"]["budget_lines"]
    say(fixes <= set(series) and look <= budget, f"the look's patches change {look} lines of Natron's code, within "
        f"the budget of {budget} (the {len(fixes)} fixes, named in upstream.toml, count apart)")
    biggest = upstream["patches"].get("patch_lines", 300)
    over = [f"{name} ({size})" for name, size in sizes.items() if size > biggest]
    say(not over, f"no patch changes more than {biggest} lines" + (f": {over}" if over else ""))


def fork_page_checks(say: Say, series: list[str]) -> None:
    page = (REPO / "FORK.md").read_text(encoding="utf-8")
    missing = [name for name in series if name not in page]
    say(not missing, f"FORK.md names every patch of the series ({len(series)})" + (f": not {missing}" if missing
                                                                                    else ""))


def licence_checks(say: Say, build: Path) -> None:
    """A packaged build carries Natron's own licence at its root, the layer's beside it and the bundled libraries'
    licence texts in Resources/licenses (tools/package_build.py)."""
    licences = build / "Resources" / "licenses"
    folders = [p for p in licences.iterdir() if p.is_dir() and any(p.iterdir())] if licences.is_dir() else []
    say((build / "LICENSE.txt").is_file() and (build / "LICENSE-layer.txt").is_file() and folders,
        f"the build carries Natron's LICENSE.txt, the layer's LICENSE-layer.txt and the libraries' licence texts "
        f"(Resources/licenses: {len(folders)} folders)")


def unit_tests(say: Say) -> None:
    """The layer's tests that need no Natron, beside test_nuke_prefs.py: the build's licences, the clipboard."""
    import sys  # noqa: PLC0415

    for name in ("test_package_build.py", "test_clipboard.py"):
        done = subprocess.run([sys.executable, str(HERE / name)], capture_output=True, text=True, check=False)
        output = done.stdout + done.stderr
        passed = done.returncode == 0 and "\nOK" in output
        say(passed, f"{name} passed" + ("" if passed else ":\n" + output[-1500:]))


def run(say: Say, series: list[str], upstream: dict) -> None:
    unit_tests(say)
    patch_checks(say, series, upstream)
    fork_page_checks(say, series)
