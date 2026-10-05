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
(`.github/README.md`), and one small workflow (`.github/workflows/upstream-watch.yml`, which doesn't run since
GitHub Actions are off, see below). **No file of Niik-l's is changed.**

## What the layer does (all in `layer/`)

- **The Nuke look, by default.** Nuke's greys and orange highlight, flat tabs, Nuke-like node colours per class
  (blue Merge, orange filters, purple transforms…), no icons on nodes, a new Merge taking the selected node in A,
  mask inputs hidden, ten properties panels at most, no file browser when a Write is made. It's this build's default:
  a preference the artist changes in Natron's Preferences window is theirs and wins. Nothing is written to the
  artist's Natron settings by the layer.
- **Nuke's keys.** Natron already has most of Nuke's default keys (B, C, D, G, M, O, P, R, T, W…). The layer adds
  the ones it lacks: K (Copy), I (node info), `\` (snap to grid), Shift+Y (connect), Alt+B (duplicate and branch),
  Alt+F (flipbook), in the menu bar's **Nuke** menu, changeable in Natron's shortcut editor. They act in the node
  graph; elsewhere the key does what Natron does with it (K still stops playback in the viewer).
- **Nuke's node names.** A **Nuke** group in the toolbar and in Tab search: Copy, ShuffleCopy, ChannelMerge,
  Keylight, IBKGizmo, Glow, Denoise, FilterErode, CornerPin2D, AdjustBBox, CurveTool, TimeClip, PostageStamp. Each
  makes Natron's own node set up the Nuke way, so comps hold only plain Natron nodes and open anywhere.
- **A gizmo pack.** Grain, ZDefocus, EdgeExtend, ChromaticAberration, Vignette and STMapIdentity, our own Groups of
  Natron's nodes (in the toolbar's Nuke group and Tab search). A comp holding one carries its nodes: it renders on
  the farm and opens on a Natron without the layer.
- **Workflow scripts** in the Nuke menu: extract an EXR's layers into Shuffles, link a roto to a track and bake
  expressions to keyframes, select similar nodes, cycle a Merge's operation, collect a comp's files, and a flipbook
  (Alt+F) rendered in the background and played in RV, or as a movie when RV isn't there.
- **ToolSets and expressions.** Saved node setups pasted with Natron's own paste (two studio ones: a CG beauty
  rebuild from Cycles' passes, a grain and lens stack; the artist's own; a project's, later from Singerie's tool
  library), and an expression menu of 18 Nuke-style recipes in Natron's Python expressions.
- **"Import my Nuke preferences".** At first launch, when the artist has Nuke preferences (`~/.nuke`), a question
  offers to bring them in; the same is in the Nuke menu. It reads their `preferences*.nk` and `menu.py` (never runs
  them, never changes them) and uses what maps: some preferences, and their node shortcuts. Not yet tried on a real
  Nuke preferences file.
- **A smoke test** against Niik-l's portable releases (`layer/tests/smoke/`: 235 checks, pixels compared, the saved
  comps rendered again without the layer), and **an upstream watch** that says when he publishes something new.
  **Tested on his 2026.09.20 and 2026.10.02 releases** (5 October 2026): every check passes on both, with the same
  pixel values, and on a build of each; Singerie's own Natron pipeline suite passes on both too. 2026.10.02 adds
  openfx-arena (Text, SVG and PSD readers, ImageMagick filters), whose Text node renders headless.

**GitHub Actions are switched off on this repository** (since 5 October 2026), Niik-l's workflows and ours alike.
The upstream watch therefore runs on a PC: `python layer/tools/sync_upstream.py --watch` (it exits with 3 when
something is new, so a weekly scheduled task can run it; `layer/README.md` has the command). The workflow file is
kept for the day Actions come back.

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
- **The gizmo pack is our own** (`layer/ext/python/natron_layer/gizmos.py`), built from Natron's own nodes; nothing
  is derived from natron-plugins, the community PyPlugs the fork bundles. Checked on 5 October 2026 in the copy the
  2026.09.20 release ships (natron-plugins at its tip): its `Licenses/` folder holds only a GPL-2.0 and a CC-BY-2.0
  text, with no list of which plug-in is under which, and the candidates' own folders state no licence. Some say where
  they come from: **Defocus** is from a Shadertoy shader under CC BY-NC-SA 3.0 (non-commercial: not compatible with
  the GPL); **PM_VectorBlur** is based on a tutorial and a Shadertoy conversion (Shadertoy's default licence is the
  same CC BY-NC-SA 3.0); **Grain_Advanced** ports a studio's Nuke gizmo and **DespillMadness** another author's Nuke
  gizmo, under licences the copies don't state; Copy_N, Shuffle_N, ChannelMerge and zDefocus state none. Hence none
  is used.
- **The workflow scripts, ToolSets and expression recipes are our own** too: natron-python-scripting (MPL-2.0) only
  inspired the list of tools; none of its files or code is used, so no MPL notice is needed.
- The studio ToolSets (`layer/ext/toolsets/*.xml`) are Natron's own copy format of nodes made by our recipes
  (`toolset_recipes.py`).
- Nuke is a trademark of The Foundry Visionmongers Ltd. This fork isn't affiliated with The Foundry; it uses Nuke's
  node and menu names only so that people who know Nuke find their way.
