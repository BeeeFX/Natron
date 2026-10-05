# The layer

Everything this fork adds to Niik-l's Natron lives in this folder (see `../FORK.md` for the short version). It makes
Natron look and behave like Nuke **by default** with **no change to Natron's own code**, so every one of Niik-l's
releases can be taken as it comes. GPL-3.0-or-later (`LICENSE`).

## What's where

| Path | What |
|---|---|
| `upstream.toml` | Niik-l's release this branch carries, the release the smoke test last passed on, the patch count |
| `compat/natron_compat.py` | **The adapter**: the one module that calls Natron's Python API and Qt (through qtpy, which the fork bundles). Everything else calls it |
| `ext/plugin/` | What Natron loads: `init.py` (every session), `initGui.py` (with a window), `aliases/` (the Nuke-named toolsets), `layer_plugin.txt` (how init.py finds the rest) |
| `ext/python/natron_layer/` | The layer's code: `look.py` (the Nuke look), `hotkeys.py` (keys), `aliases.py` (Nuke names), `nuke_prefs.py` (reading Nuke preferences), `gui.py` (the Nuke menu, the first-launch question), `user_config.py` (the artist's answers) |
| `ext/presets/` | `nuke_look.toml` (the look's values), `nuke_hotkeys.toml` (Nuke's keys next to Natron's) |
| `ext/qss/nuke.qss` | The stylesheet: Natron's own, unchanged, then a Nuke section |
| `patches/` | Core patches (none) and the budget |
| `tests/smoke/` | The smoke test, its window probe and the hand-written Nuke fixtures |
| `tools/` | `package_build.py` (a build from a release), `sync_upstream.py` (bring Niik-l's commits in) |
| `GAPS.md` | What's still missing compared with Nuke, ranked, with each item's route and status |

## How Natron loads it

- **From the repository** (development, tests): put `layer/ext/plugin` on `NATRON_PLUGIN_PATH` and start the fork's
  portable release. init.py finds the layer two folders up.
- **In a build** (`tools/package_build.py`): `ext/plugin` becomes `Plugins/PyPlugs/layer` and the rest
  `Resources/layer`. Natron reads its bundled PyPlugs folder at every start, so the build is Nuke-like whoever
  launches it, Singerie or not. The layer's Python stays out of `Plugins/PyPlugs` because Natron puts every folder
  under it on Python's path.
- Singerie's own pipeline plugin is separate (Singerie's repository, `plugins/natron`): piping an app isn't
  modifying it.

## The Nuke look

Set from `ext/presets/nuke_look.toml` at every start (`look.apply`), with one rule for whose value wins:

1. **The artist's own.** A preference the artist changed in Natron's Preferences window and saved is stored in
   Natron's settings (the registry on Windows); the layer leaves it alone. Natron stores a preference only when it's
   changed (checked: a long-used Natron holds a handful), so "stored" means "someone chose it".
2. **Their imported Nuke preferences**, after they said yes (see below).
3. **The build's Nuke look.**

Values from 2 and 3 are **for the session only**. Checked on the fork: setting a preference from Python doesn't
write it (Natron writes preferences from its Preferences window, only those changed while it's open, from
`AppSettings.saveSettings()`, and a few flags of its own); the layer also turns Natron's hidden "Save settings on
change" off while it sets them, as Natron's own `--setting` option does. The smoke test compares every registry
value before and after.

Limits found on the fork:

- **Natron loads its stylesheet before any startup script runs**, and reloads it only when the setting changes while
  its window exists, so the layer sets it again once the window is up (`gui.refresh_look`).
- **The font and its size are read before any script runs** (straight from the stored settings), so the look can't
  change them: Natron's 11 pt is Nuke's size anyway. The import says so for a Nuke font size.
- **Natron's "Restore Defaults" button** (Preferences) gives Natron's stock values and stores them, which then count
  as the artist's own. The Nuke menu's **Use this build's look again…** asks, then removes the artist's stored values
  for the look's preferences (the only time the layer writes Natron's settings, on the artist's yes).
- The node graph's background is the stylesheet's base colour; nodes take the per-class colours; the viewer and the
  curve editor draw themselves (the curve editor's background is a preference, set).

The colours are approximations of Nuke's default theme by eye (Nuke's values aren't published as a list).

## Nuke's keys

`ext/presets/nuke_hotkeys.toml` lists 49 of Nuke's default keys (from Foundry's published lists) next to what Natron
does with each (read in its source): 38 already do the same in Natron (B, C, D, F, G, M, N, O, P, R, T, W, the dot,
Tab, Alt+C, Alt+K, Ctrl+G, Shift+X, the viewer's R G B A Y, J K L…), **5 are added by the layer**, 3 have no
equivalent reachable without a core patch (Alt+U splay, Ctrl+Enter open a group, H fill the viewer) and 3 do
something else in Natron (P in the viewer pauses input A, Alt+P toggles postage stamps, S in the viewer opens the
project settings).

The added ones are menu commands (menu bar › **Nuke**) made with Natron's `addMenuCommand`, each with its Nuke key as
default; the artist can change them in Natron's shortcut editor (group Global):

| Key | Nuke menu entry | Natron's own use of the key |
|---|---|---|
| K | Insert Copy node | none in the node graph; the viewer's stop, the curve editor's and dope sheet's constant interpolation |
| I | Node info | none |
| `\` | Snap all nodes to grid (110 × 24, our understanding of Nuke's default) | none |
| Shift+Y | Connect second selected to first | none in the node graph; the viewer's luminance of input A |
| Alt+B | Duplicate and branch | none |

Natron gives such a command's key to its whole window, so **each command first looks where the keyboard is**: in a
node graph it acts; anywhere else it hands the key to that widget as if the layer weren't there (checked in the
window: K in the viewer makes no node). Natron's own default keys are compiled in and can't be changed from Python;
the layer never writes the ones an artist stores.

**Seeding Natron's own keys** (not done, documented for the core-patch decision): Natron stores an artist's keys
in its settings, one group per shortcut group (`Global`, `NodeGraph`, `Viewer`, `Nodes/<menu>`…), with
`<action>_nbShortcuts`, `<action>_Modifiers<n>` (Qt's modifier flags as a number) and `<action>_Symbol<n>` (Qt's key
code), and `NATRON_SHORTCUTS_DEFAULT_VERSION` (read in `Gui/GuiApplicationManager10.cpp`, `loadShortcuts`). Only ten
plug-ins can have a node key at all (Transform, Roto, RotoPaint, Merge, Grade, ColorCorrect, Blur, Dot, Read,
Write: the list is compiled in). So the import adds an artist's node shortcuts as the layer's own menu commands
(`Nuke › My Nuke shortcuts`) instead of writing Natron's keys; a supported import and export in Natron's shortcut
editor would be core patch item 8 of `GAPS.md`.

## Nuke's node names

`aliases.py` and `ext/plugin/aliases/`: twelve **toolsets** (Natron's PyPlug kind that makes nodes instead of a
Group; Natron reads `getIsToolset`, with that spelling) in the toolbar's **Nuke** group and in Tab search as
`Copy  [Nuke]`. Each makes Natron's own node, set up as the Nuke node behaves, named after it (`Copy1`) and fed by
the selected node:

| Nuke | Natron's node, set up as |
|---|---|
| Copy | Shuffle keeping B's colour and taking A's alpha |
| ShuffleCopy | Shuffle (both inputs, every channel) |
| ChannelMerge | Merge on alpha only, screen (a + b − ab, ChannelMerge's union); B's colour passes |
| Keylight | PIK, screen colour picked by hand |
| IBKGizmo | PIK, green screen (feed a clean plate to C) |
| Glow | Bloom |
| Denoise | DenoiseSharpen |
| FilterErode | Erode (CImg) |
| CornerPin2D | CornerPin |
| AdjustBBox | AdjustRoD |
| CurveTool | ImageStatistics |
| TimeClip | FrameRange |

Names Natron already uses (Blur, Grade, Merge, Transform…) aren't aliased, so Tab search doesn't list them twice.
Comps hold only plain Natron nodes: they open and render anywhere, the farm included, with or without the layer.

## Import my Nuke preferences

At first launch, when the artist has a `.nuke` folder with preferences or a `menu.py`, a question offers **Import**,
**Not now** (asks again next time) or **Don't ask again**; the menu bar's Nuke menu has **Import my Nuke
preferences…** and **Forget my imported Nuke preferences…** any time. It reads the newest
`~/.nuke/preferences<version>.nk` (Nuke's script format: the `Preferences` node's knobs) and `~/.nuke/menu.py`
(parsed with Python's `ast`, **never run**), shows what maps and only on a yes keeps it in the layer's own file
(`%APPDATA%\natron-layer\config.json`). **Nothing in `.nuke` is changed and Natron's settings aren't written.**

What maps today: most panels open, snap to node, autosave delay, undo steps, mask inputs hidden, postage stamps,
cache sizes; node shortcuts from `menu.py` for every Nuke node with a Natron equivalent (around 80 Nuke classes,
the aliases included). Each shortcut that takes the place of one of Natron's keys in the node graph is named at
import. Everything else is listed with why.

**It hasn't met a real Nuke preferences file yet**: Nuke isn't installed where it was written. The knob names come
from Nuke's documented Preferences and common use, the tests use hand-written files
(`tests/smoke/fixtures/nuke_home/.nuke`), and the import lists every knob it read but didn't use, so the first real
file shows what to add.

## The smoke test

```
python layer/tests/smoke/run_smoke.py --renderer "<release>/bin/NatronRenderer.exe" [--gui] [--keep]
```

With any Python 3.10+. It runs the Nuke reader's tests (`test_nuke_prefs.py`, no Natron), checks the layer's files
(the stylesheet still holds Natron's own unchanged, the patch series, ASCII startup files, one PyPlug per alias),
then `NatronRenderer -t smoke_checks.py` in a clean session: Natron's disk cache, home folder, TEMP and the layer's
config in a temporary folder, only the layer on `NATRON_PLUGIN_PATH`. Inside: the layer loads; the adapter's view of
Natron (2.6, Python 3.14, qtpy on PySide6, the 3D workspace); the look applied, the artist's own values left, the
imported ones over the look, a value set with saving on not written; every alias registered and making its node;
**a comp of alias nodes rendered and its pixels compared** (Copy, ChannelMerge, TimeClip, AdjustBBox: values worked
out by hand) and seven aliases rendering the same pixels as Natron's node set up by hand; the keys' table and the
commands' work; the import and the first-launch question on the fixtures (the `.nuke` folder fingerprinted
unchanged); the look's reset into a settings file standing in for Natron's. `--gui` also opens Natron's window for
about 20 seconds with a probe (`gui_probe/`): the question, the Nuke menu and its keys, the stylesheet in use, where
keys act, a command through its menu entry, and a picture of the window; it ends Natron at once so nothing is written
at exit.

**Natron's settings are compared before and after** (every registry value under `HKCU\Software\INRIA`, Natron's
folders in `%LOCALAPPDATA%` and the home folder, the release folder): unchanged. The fork has no option to keep its
settings elsewhere, so the test never writes one; Natron itself records four switches for every PyPlug it registers
(the aliases, `layer.nuke.*`), and the test takes out the ones added during the run, as Singerie's Natron suite does.

On a packaged build (`tools/package_build.py`), point `--renderer` at the build: the test then uses the build's own
copy of the layer with nothing on `NATRON_PLUGIN_PATH`.

Last results: see `upstream.toml` `[tested]`.

## Bringing Niik-l's releases in

1. `python layer/tools/sync_upstream.py` says what's new; `--push` fast-forwards `RB-2.6` and pushes his new tags.
   **Fast-forward only**: if his history was ever rewritten, nothing is pushed and a person looks.
2. Merge his release tag into `sng/main` (`git merge --no-ff natron-2.6-<date>`). His files and ours never overlap,
   so the merge is clean as long as there are no core patches.
3. Download that release's portable build and run the smoke test on it (with `--gui`).
4. When it passes, update `upstream.toml` (`[upstream]` and `[tested]`), push `sng/main`, make the build
   (`tools/package_build.py`) and publish it on Singerie (an admin's step).

**The upstream watch** (`.github/workflows/upstream-watch.yml`, weekly and by hand) only compares his `RB-2.6` and
tags with ours and opens or updates one issue (label `upstream`) with the new commits and these steps. It builds
nothing and runs no Natron: about a minute on Ubuntu. GitHub runs scheduled workflows only from a repository's
default branch, so it runs once `sng/main` is the default. The smoke test needs Windows and the release's portable
build (no graphics card needed); it runs on a PC, and later can run on a farm PC registered as a self-hosted runner
(so no hosted Windows minutes are spent).

Niik-l's own workflows are in his files (`.github/workflows/`): in this repository "Build Installer" runs on every
push of any branch and "Tests" on pushes to `RB-2.6`, using Actions minutes; they don't serve this fork.

## Making a build

```
python layer/tools/package_build.py --release "<Niik-l's portable release>" --tag natron-2.6-2026.09.20 [--number 1]
```

copies the release (only read), adds the layer, writes `Resources/layer/BUILD.toml` and `SOURCE.txt` (where the
corresponding source is, as the GPL asks), and zips it: `layer/dist/Natron-2.6.0-2026.09.20.sng1-win64.zip`, one
folder inside. Its version is **`2.6.0+2026.09.20.sng1`** (`2.6.0+<release date>.sng<n>`): Singerie's software
manager reads fork builds as `2.6.0+<build>`, so `2.6.x`, `2.6.0` and the exact build match it, `.sng2` sorts after
`.sng1`, and both after Niik-l's plain `2.6.0+2026.09.20`. The archive's name has `-` for `+` (Singerie's build list
takes no `+` in file names). Nothing is uploaded.

## Writing code here

- Natron and Qt only through `compat` (the adapter): one place to fix when the fork's API moves.
- Features are checked with `getPluginIDs()`, not versions.
- Startup files and PyPlugs stay plain ASCII (Natron doesn't read them as UTF-8).
- Nothing writes Natron's settings without the artist's yes; nothing changes an artist's comps or files by itself.
- Each file starts with `SPDX-License-Identifier: GPL-3.0-or-later`.
