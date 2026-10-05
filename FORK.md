# What this fork adds

This repository is a copy of **Niik-l's Natron 2.6** ([github.com/Niik-l/Natron](https://github.com/Niik-l/Natron),
branch `RB-2.6`), the fork of Natron with a 3D workspace, Python 3.14 and Qt 6. On top of it we add a **layer**
that makes Natron look and behave like Nuke **by default**, so compositors coming from Nuke feel at home at once,
without changing Natron's own code.

## The two branches

| Branch | What it is |
|---|---|
| `RB-2.6` | **An exact copy of Niik-l's branch**, never changed by us. It only moves forward when he publishes. |
| `sng/main` | **Ours**: his code plus everything we add. His new releases come in as merges into it. |

## See everything we added, in one click

**https://github.com/BeeeFX/Natron/compare/RB-2.6...sng/main**

That page compares his branch with ours and shows only our changes: the list of our commits at the top, then every
file we added or changed, line by line (green for what we added). Today every change is a new file: the `layer/`
folder, this page, a short introduction GitHub shows on the repository's front page when it opens on `sng/main`
(`.github/README.md`), and one small workflow (`.github/workflows/upstream-watch.yml`). **No file of Niik-l's is
changed.**

## What the layer does (all in `layer/`)

- **The Nuke look, by default.** Nuke's greys and orange highlight, flat tabs, Nuke-like node colours per class
  (blue Merge, orange filters, purple transforms…), no icons on nodes, a new Merge taking the selected node in A,
  mask inputs hidden, ten properties panels at most, no file browser when a Write is made. It's this build's default:
  a preference the artist changes in Natron's Preferences window is theirs and wins. Nothing is written to the
  artist's Natron settings by the layer.
- **Nuke's keys.** Natron already has most of Nuke's default keys (B, C, D, G, M, O, P, R, T, W…). The layer adds
  the ones it lacks: K (Copy), I (node info), `\` (snap to grid), Shift+Y (connect), Alt+B (duplicate and branch),
  in the menu bar's **Nuke** menu, changeable in Natron's shortcut editor. They act in the node graph; elsewhere the
  key does what Natron does with it (K still stops playback in the viewer).
- **Nuke's node names.** A **Nuke** group in the toolbar and in Tab search: Copy, ShuffleCopy, ChannelMerge,
  Keylight, IBKGizmo, Glow, Denoise, FilterErode, CornerPin2D, AdjustBBox, CurveTool, TimeClip. Each makes
  Natron's own node set up the Nuke way, so comps hold only plain Natron nodes and open anywhere.
- **"Import my Nuke preferences".** At first launch, when the artist has Nuke preferences (`~/.nuke`), a question
  offers to bring them in; the same is in the Nuke menu. It reads their `preferences*.nk` and `menu.py` (never runs
  them, never changes them) and uses what maps: some preferences, and their node shortcuts. Not yet tried on a real
  Nuke preferences file.
- **A smoke test** against Niik-l's portable releases (`layer/tests/smoke/`), and **a weekly watch** that opens an
  issue when he publishes something new.

The details, the reasons and how to work on it: [`layer/README.md`](layer/README.md). What's still missing compared
with Nuke, ranked: [`layer/GAPS.md`](layer/GAPS.md).

## Core patches

None. Changing Natron's own code makes every one of Niik-l's releases (every one to three weeks) harder to take,
so the budget is at most 5 small patches (about 800 lines), each offered to him first: [`layer/patches/`](layer/patches/README.md).

## Licences

- Natron and Niik-l's fork: GPL-2.0-or-later (see `LICENSE.txt`), with their bundled parts' own licences.
- The layer: **GPL-3.0-or-later** (`layer/LICENSE`), each file says so in its first lines.
- `layer/ext/qss/nuke.qss` contains Natron's own stylesheet (GPL-2.0-or-later) unchanged, with our Nuke section
  after it. It isn't derived from natron-python-scripting's `mainstyle_NUKE` (MPL-2.0): no MPL file is used.
- Nuke is a trademark of The Foundry Visionmongers Ltd. This fork isn't affiliated with The Foundry; it uses Nuke's
  node and menu names only so that people who know Nuke find their way.
