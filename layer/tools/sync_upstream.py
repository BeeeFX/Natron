# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Watch Niik-l's repository and bring his new commits and releases into this repository's RB-2.6 (any Python
3.11+, git on the path):

    python layer/tools/sync_upstream.py --watch [--report <file>]   # the weekly watch, from a PC
    python layer/tools/sync_upstream.py                              # says what's new, changes nothing
    python layer/tools/sync_upstream.py --push                       # fast-forwards RB-2.6, pushes his new tags

``--watch`` does the job of ``.github/workflows/upstream-watch.yml``, which can't run since GitHub Actions were
switched off on BeeeFX/Natron (5 October 2026): it fetches Niik-l's RB-2.6 and release tags, compares them with our
copy of his branch and with the release sng/main carries and was tested on (``upstream.toml``), and prints what's
new with the steps to take; ``--report`` also writes that text to a file. It exits with 3 when something is new and
0 when not, so a weekly scheduled task on a PC can run it (layer/README.md, "Bringing Niik-l's releases in", has the
Windows command). It changes nothing in the repository's branches and pushes nothing; our copy on GitHub is read when
this PC can (it's private), else the local RB-2.6 stands in for it.

RB-2.6 stays an exact copy of his branch: ``--push`` only ever **fast-forwards** it (moves it to his newer commit).
When his history was rewritten so that it can't be, nothing is pushed and the script says so: that needs a person.
Merging a release into sng/main is the next step, by hand, with the smoke test (the script prints the commands).
"""

from __future__ import annotations

import argparse
import datetime
import subprocess
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LAYER = REPO / "layer"
UPSTREAM = "https://github.com/Niik-l/Natron.git"
BRANCH = "RB-2.6"
SOMETHING_NEW = 3


def git(*args: str, check: bool = True) -> str:
    done = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, check=False)
    if check and done.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout.strip()


def git_ok(*args: str) -> bool:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, check=False).returncode == 0


def remote_tags(remote: str) -> set[str]:
    listed = git("ls-remote", "--tags", remote, "natron-*", check=False)
    return {line.split("refs/tags/", 1)[1].removesuffix("^{}") for line in listed.splitlines() if "refs/tags/" in line}


def watch(report: str | None) -> int:
    """What's new at Niik-l's since our copy and since the release sng/main carries; 3 when something is."""
    if "upstream" not in git("remote").split():
        git("remote", "add", "upstream", UPSTREAM)
    git("fetch", "--quiet", "upstream", BRANCH, "--tags")
    reached_ours = git_ok("fetch", "--quiet", "origin", BRANCH)
    ours = f"origin/{BRANCH}" if reached_ours else BRANCH
    theirs = f"upstream/{BRANCH}"
    upstream = tomllib.loads((LAYER / "upstream.toml").read_text(encoding="utf-8"))
    carried, tested = upstream["upstream"]["tag"], upstream["tested"]["release"]
    his_tags = remote_tags("upstream")
    our_tags = remote_tags("origin") if reached_ours else set(git("tag", "--list", "natron-*").split())
    where = "BeeeFX/Natron" if reached_ours else "the local branch: BeeeFX/Natron could not be read from this PC"
    lines = [f"Niik-l's Natron, watched {datetime.date.today().isoformat()} ({UPSTREAM})",
             f"Our copy of his {BRANCH}: {git('rev-parse', '--short', ours)} ({where}); "
             f"his: {git('rev-parse', '--short', theirs)}."]
    new_commits = git("log", "--format=  %h %ad %s", "--date=short", f"{ours}..{theirs}") if git_ok(
        "merge-base", "--is-ancestor", ours, theirs) else None
    if new_commits is None:
        lines.append(f"His {BRANCH} can't be fast-forwarded from ours: his history was rewritten. A person looks.")
    elif new_commits:
        lines += [f"New on his {BRANCH}:", new_commits]
    else:
        lines.append(f"Nothing new on his {BRANCH}.")
    new_tags = sorted(his_tags - our_tags)
    newer = sorted(t for t in his_tags if t > carried)
    lines.append("His release tags not yet in our copy: " + (", ".join(new_tags) or "none") + ".")
    lines.append(f"sng/main carries {carried}; the layer was last tested on {tested}."
                 + (" Releases after it: " + ", ".join(newer) + "." if newer else ""))
    if carried != tested:
        lines.append(f"{carried} isn't tested yet: download its portable build and run the smoke test.")
    something = bool(new_commits) or bool(new_tags) or bool(newer) or new_commits is None
    if something:
        newest = newer[-1] if newer else carried
        lines += ["", "Steps (layer/README.md, \"Bringing Niik-l's releases in\"):",
                  "  python layer/tools/sync_upstream.py --push      (RB-2.6 fast-forwarded, his tags pushed)",
                  f"  git checkout sng/main && git merge --no-ff {newest}",
                  '  python layer/tests/smoke/run_smoke.py --renderer "<that release>/bin/NatronRenderer.exe" --gui',
                  "  then layer/upstream.toml ([upstream], and [tested] once it passed), and push sng/main."]
    text = "\n".join(lines)
    print(text)
    if report:
        Path(report).write_text(text + "\n", encoding="utf-8")
    return SOMETHING_NEW if something else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--watch", action="store_true", help="the weekly watch: what's new, exit 3 when something is")
    parser.add_argument("--report", help="with --watch: also write what it found to this file")
    parser.add_argument("--push", action="store_true", help="fast-forward RB-2.6 on origin and push the new tags")
    args = parser.parse_args()
    if args.watch:
        return watch(args.report)
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
