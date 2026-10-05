# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Bring Niik-l's new commits and releases into this repository's RB-2.6 (any Python 3.10+, git on the path):

    python layer/tools/sync_upstream.py            # says what's new, changes nothing
    python layer/tools/sync_upstream.py --push     # fast-forwards RB-2.6 and pushes it with his new tags

RB-2.6 stays an exact copy of his branch: it's only ever **fast-forwarded** (moved to his newer commit). When his
history was rewritten so that it can't be, nothing is pushed and the script says so: that needs a person (see
layer/README.md, "Bringing Niik-l's releases in"). Merging a release into sng/main is the next step, by hand, with
the smoke test (the script prints the commands).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
UPSTREAM = "https://github.com/Niik-l/Natron.git"
BRANCH = "RB-2.6"


def git(*args: str, check: bool = True) -> str:
    done = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, check=False)
    if check and done.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--push", action="store_true", help="fast-forward RB-2.6 on origin and push the new tags")
    args = parser.parse_args()
    if "upstream" not in git("remote").split():
        git("remote", "add", "upstream", UPSTREAM)
    git("fetch", "upstream", "--tags")
    git("fetch", "origin", "--tags")
    ours, theirs = f"origin/{BRANCH}", f"upstream/{BRANCH}"
    if git("rev-parse", ours) == git("rev-parse", theirs):
        print(f"{BRANCH} is up to date with Niik-l's ({git('rev-parse', '--short', theirs)}).")
    elif subprocess.run(["git", "-C", str(REPO), "merge-base", "--is-ancestor", ours, theirs]).returncode != 0:
        print(f"Niik-l's {BRANCH} can't be fast-forwarded from ours: his history was rewritten. Nothing pushed.")
        print(f"Ours: {git('log', '-1', '--format=%h %ad %s', '--date=short', ours)}")
        print(f"His:  {git('log', '-1', '--format=%h %ad %s', '--date=short', theirs)}")
        return 1
    else:
        print(f"New on Niik-l's {BRANCH}:")
        print(git("log", "--format=  %h %ad %s", "--date=short", f"{ours}..{theirs}"))
    local_tags = set(git("ls-remote", "--tags", "origin").split())
    new_tags = [t for t in git("tag", "--list", "natron-*").split() if f"refs/tags/{t}" not in local_tags]
    print("New release tags: " + (", ".join(new_tags) if new_tags else "none"))
    if args.push:
        refs = [f"refs/remotes/upstream/{BRANCH}:refs/heads/{BRANCH}"] + [f"refs/tags/{t}:refs/tags/{t}" for t in new_tags]
        print(git("push", "origin", *refs))
        print("Pushed (a fast-forward only: git refuses anything else without --force, which this never uses).")
    if new_tags:
        newest = sorted(new_tags)[-1]
        print("\nNext, by hand: merge the release into sng/main and run the smoke test on its portable build:")
        print(f"  git checkout sng/main && git merge --no-ff {newest}")
        print('  python layer/tests/smoke/run_smoke.py --renderer "<that release>/bin/NatronRenderer.exe" --gui')
        print("  then update layer/upstream.toml ([upstream] tag and commit, [tested] when it passed) and push sng/main.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
