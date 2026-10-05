# The layer

Everything this fork adds to Niik-l's Natron lives in this folder (see `../FORK.md` for the short version). It makes
Natron look and behave like Nuke **by default** with **no change to Natron's own code**, so every one of Niik-l's
releases can be taken as it comes. GPL-3.0-or-later (`LICENSE`).

## What's where

| Path | What |
|---|---|
| `upstream.toml` | Niik-l's release this branch carries, the release the smoke test last passed on, the patch count |
| `compat/natron_compat.py` | **The adapter**: the one module that calls Natron's Python API and Qt (through qtpy, which the fork bundles). Everything else calls it |
| `ext/plugin/` | What Natron loads: `init.py` (every session), `initGui.py` (with a window), `aliases/` (the Nuke-named toolsets), `gizmos/` (the gizmo pack's PyPlugs), `layer_plugin.txt` (how init.py finds the rest) |
| `ext/python/natron_layer/` | The layer's code: `look.py` (the Nuke look), `hotkeys.py` (keys), `aliases.py` (Nuke names), `gizmo_kit.py` and `gizmos.py` (the gizmo pack), `workflow.py` and `flipbook_job.py` (the workflow scripts), `toolsets.py` and `toolset_recipes.py` (ToolSets), `expressions.py` (the expression menu), `nuke_prefs.py` (reading Nuke preferences), `gui.py` (the Nuke menu, the first-launch question), `user_config.py` (the artist's answers) |
| `ext/presets/` | `nuke_look.toml` (the look's values), `nuke_hotkeys.toml` (Nuke's keys next to Natron's), `nuke_expressions.toml` (the expression recipes) |
| `ext/toolsets/` | The studio ToolSets: Natron's own copied nodes, made by `tools/make_toolsets.py` |
| `ext/qss/nuke.qss` | The stylesheet: Natron's own, unchanged, then a Nuke section |
| `patches/` | Core patches (none) and the budget |
| `tests/smoke/` | The smoke test (`run_smoke.py`; inside Natron `smoke_checks.py` and `tool_checks.py`, without the layer `project_checks.py`), its window probe and the hand-written Nuke fixtures |
| `tools/` | `package_build.py` (a build from a release), `sync_upstream.py` (the upstream watch, and bringing Niik-l's commits in), `make_toolsets.py` (the studio ToolSets' files, with its window probe `toolset_maker/`) |
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

`ext/presets/nuke_hotkeys.toml` lists 50 of Nuke's default keys (from Foundry's published lists) next to what Natron
does with each (read in its source): 38 already do the same in Natron (B, C, D, F, G, M, N, O, P, R, T, W, the dot,
Tab, Alt+C, Alt+K, Ctrl+G, Shift+X, the viewer's R G B A Y, J K L…), **6 are added by the layer**, 3 have no
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
| Alt+F | Render › Flipbook selected (see Workflow scripts) | none (Natron's menus have no Alt letters) |

The workflow scripts, ToolSets and expressions below have no default key, as in Nuke; the artist can give them one
in the shortcut editor.

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

`aliases.py` and `ext/plugin/aliases/`: thirteen **toolsets** (Natron's PyPlug kind that makes nodes instead of a
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
| PostageStamp | NoOp with its node preview on (the picture of its input on the node) |

Names Natron already uses (Blur, Grade, Merge, Transform…) aren't aliased, so Tab search doesn't list them twice.
Comps hold only plain Natron nodes: they open and render anywhere, the farm included, with or without the layer.

## The gizmo pack

`gizmos.py` (built with `gizmo_kit.py`) and `ext/plugin/gizmos/`: six **Group PyPlugs** written for this layer from
Natron's own nodes, in the toolbar's Nuke group and Tab search under Nuke's names, each coloured like Nuke's nodes of
its menu. **Nothing is derived from natron-plugins** (the community PyPlugs the fork bundles): their per-plug-in
licences aren't stated (see `../FORK.md`, Licences), so these are our own.

| Gizmo (Nuke menu) | What it does | Built from |
|---|---|---|
| Grain (Draw) | Film grain: size and intensity per channel (Intensity ≈ the grain's spread), Response (0: the same grain everywhere, 1: in proportion to the image's value, none in the blacks), seed, Animated, Mix | Noise, three CImg blurs (one per channel), a Grade, Merges |
| ZDefocus (Filter) | Defocus by depth: Depth channel (alpha by default; depth.Z is picked when the input has one), Focal point, Depth of field, Size (blur per unit of depth), Maximum, Filter, Output result or focal plane setup (the blur as grey) | the blur amount from the depth, six slices weighted by Keyer tents, each blurred by CImg Blur, added and divided by the added weights |
| EdgeExtend (Filter) | Pushes a premultiplied image's colour out past its alpha (fringes after keying): Size, Erode, Premultiply (off: the extended colour, unpremultiplied, with the input's alpha) | six growing blurs of the premultiplied image, unpremultiplied and laid over each other |
| ChromaticAberration (Filter) | Splits the colours towards the edges: Amount, Red/Green/Blue shares | one LensDistortion per channel (centred on the format by Natron) |
| Vignette (Draw) | Darkens the edges: Amount, Softness, Scale | a Radial fitted to the input's format, multiplied |
| STMapIdentity (Transform) | An ST map of the input's format: R = (x + 0.5) / width, G = (y + 0.5) / height (Pixel centres off: x / width) | two Ramps |

Natron already has, under Nuke's own names: **VectorBlur** (the fork's own node, from motion vectors), **Exposure**
(the fork's), **Despill** (spill map mix, expand, respill colour, brightness), Shuffle and ShuffleCopy; Copy and
ChannelMerge are aliases. So those aren't redone.

How a gizmo travels: Natron saves a Group PyPlug's inner nodes with the comp and, with its default preferences, opens
it from the comp (checked in `Engine/NodeGroupSerialization.cpp`): where the layer is installed the Group takes the
gizmo's name and ID, elsewhere (the farm without our build, a plain Natron) it's a plain Group. Either way it renders
the same pixels (the smoke test renders a comp of every gizmo in a NatronRenderer without the layer). The other side:
**a later fix to a gizmo reaches new nodes, not the ones already in comps**. The rules that make this work are in
`gizmo_kit.py`: only Natron's nodes inside, expressions using Natron's names only (`thisGroup.size.get()`), each
expression reading one of the group's controls, fixed inner names, no NatronGui.

Found on the fork while building them:

- Natron reports a **Group's format as the project's** (`getOutputFormat`), while it computes its region of
  definition through it: Vignette and STMapIdentity read the format of the node feeding them, or the region of
  definition when that node is a Group (another gizmo).
- An expression inside a Group is compiled with the Group's name in it, and **recompiled on a rename only when it
  reads one of the Group's parameters**: hence every gizmo expression reads a control.
- Natron's alias of a parameter (`setAsAlias`) gives the inner parameter the new control's value: the kit starts each
  control at the inner value first.
- Blurring Natron's Noise lowers its spread about as 1 / size (measured): Grain scales its strength back up by size.
- Natron's **Shuffle says "unpremultiplied" unless told**, and a Write then multiplies by the alpha again: the
  shuffles that carry a CG render's layers are marked premultiplied.

## Workflow scripts

`workflow.py`, in the menu bar's Nuke menu. Our own code (natron-python-scripting's list of tools inspired the
choice; none of its MPL-2.0 files is used):

| Menu entry | What it does |
|---|---|
| Channel › Extract layers into Shuffles | One Shuffle per layer of the selected node's stream (an EXR's AOVs), named after the layer: its first three channels in R, G, B (one channel goes to all three), its alpha or the stream's own; marked premultiplied |
| Other › PostageStamp (and Tab) | The alias above |
| Roto › Link roto to track | With a Roto (or RotoPaint) and a Tracker selected: a Transform is inserted after the Roto (what it fed is fed by the Transform), its translate an expression giving the track's move since the current frame, its centre the track's position then. Natron takes no expression on a shape's own parameters (checked), hence the Transform, as a Nuke artist would do |
| Edit › Bake expressions to keyframes | Every expression of the selected nodes becomes a keyframe on each frame of the project's range |
| Edit › Select similar class, colour | The top-level nodes of the same plug-in, or of the same node colour (colours exist in the window only) |
| Merge › Next / Previous operation | The selected Merges through Nuke's common operations (over, under, plus, screen, multiply, minus, from, max, min, difference, stencil, mask, in, out, atop, divide, average, copy) |
| File › Collect files… | Every file the comp reads copied into a chosen folder (`footage/<node>/`, sequences frame by frame) and a copy of the comp written there reading them as `[Project]/footage/…` (Natron's `[Project]` is the folder a comp opens from). The open comp isn't changed |
| Render › Flipbook selected (Alt+F) | The selected node rendered over the project's frame range by NatronRenderer, in the background, from a copy of the comp (`saveTempProject`; `flipbook_job.py` puts `[Project]` back on the comp's own folder), then played: in **RV** when it's on this PC (`NATRON_RV_PATH`, the fork's own setting for its "Open in RV" buttons, then `RV_PATH`, `RV_HOME`, the PATH, the usual install folders), else as an MP4 (H.264) in the system's player. Natron's window stays free while it renders |

Each script's work is a function taking its nodes, which the smoke test runs headless; the menu functions only read
the selection and say what happened. Within Singerie, publishing and the archive collect a shot's files; Collect
files is for a comp handed on outside it.

## ToolSets

`toolsets.py`, menu bar › Nuke › ToolSets, as in Nuke. A ToolSet is a file of **Natron's own copied nodes**
(`<name>.xml`: the text Natron's Copy puts on the clipboard, which its Paste reads), so pasting one is Natron's
paste: the file's text goes on the clipboard, `pasteNodes`, and whatever the clipboard held (its text or picture) is
put back. Pasting needs Natron's window. Three places, each its own submenu:

- **Studio**: the layer's, in `ext/toolsets/`. Two today: **CG beauty rebuild (Cycles passes)** (Blender Cycles'
  light passes added back up: (Dir + Ind) × Col for diffuse, glossy and transmission, plus volume, emission and the
  environment, the beauty's alpha, and a Check that's black when the passes add up) and **Grain and lens** (a
  LensDistortion to set to the plate's lens, ChromaticAberration, Vignette, Grain).
- **Mine**: the artist's, saved with **Save selection as ToolSet…** (Natron's Copy of the selection, kept in
  `%APPDATA%\natron-layer\toolsets`).
- **Project**: every folder listed in `NATRON_LAYER_TOOLSETS` (separated as on PATH). **This is the way in for
  Singerie's tool library**, not built yet: a ToolSet published as a project tool, pinned per project, and laid out
  by the desktop helper in the project's tools folder, whose path the helper puts in `NATRON_LAYER_TOOLSETS` when it
  launches Natron (as it sets `SINGERIE_PERSONAL_TOOLS` today).

After a paste, a Dot labelled `ToolSetIn` is connected to the node that was selected, and each Shuffle labelled
`AOV_<pass>` takes that pass from its input when there is one (`ViewLayer.DiffDir` or `DiffDir` for `AOV_DiffDir`),
else black; the summary says which. Labels, because Natron renames pasted nodes whose names are taken. **Paste a
ToolSet…** lists every ToolSet there is now (one saved a minute ago included); the per-ToolSet entries are made when
Natron starts.

The studio files are made from `toolset_recipes.py` by `python layer/tools/make_toolsets.py --renderer <…>`, which
opens Natron's window for a few seconds (the recipes built, selected, copied, saved; paths of the PC cut from the
gizmos' PyPlug names; the clipboard put back; Natron's settings compared). Run it again when a recipe or a gizmo
changes (a pasted gizmo carries its inner nodes), or when a Natron release changes its copy format: the smoke test
pastes every file in the window and renders the result without the layer.

Found on the fork: Windows lets one program at a time open the clipboard and programs watching it open it right
after each change, so a set can fail; the layer tries again until the text reads back, and never calls Natron's
paste on a clipboard that doesn't hold the ToolSet. A paste before Natron's node graph exists ended Natron.

## Expressions

`expressions.py`, menu bar › Nuke › Expressions: 18 Nuke-style recipes written as Natron's Python expressions
(`ext/presets/nuke_expressions.toml`, each with how Nuke writes it): frame number (plus an offset), hold, offset in
time, loop and ping-pong the animation (`curve(t, dimension)`, the parameter's own keys, as Nuke's `curve`), wiggle
(`NatronEngine.ExprUtils.noise`, from about -1 to 1), random per frame (Natron's `random`, fixed per frame), sine,
ramp between two frames, on from a frame, same as or opposite of another node's parameter, another node's parameter
at a frame, the input's width and height, the project's first and last frame. Picking one opens a small window: the
selected node's parameter, the recipe's fields, the expression (editable), **Apply** (every dimension) or **Copy**
(for Natron's own expression editor). The smoke test checks each recipe's value on known frames.

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
(the stylesheet still holds Natron's own unchanged, the patch series, ASCII files for Natron, one PyPlug per alias
and gizmo, one file per studio ToolSet, every expression recipe valid Python), then `NatronRenderer -t
smoke_checks.py` in a clean session: Natron's disk cache, home folder, TEMP and the layer's config in a temporary
folder, only the layer on `NATRON_PLUGIN_PATH`. Inside: the layer loads; the adapter's view of Natron (2.6, Python
3.14, qtpy on PySide6, the 3D workspace); the look applied, the artist's own values left, the imported ones over the
look, a value set with saving on not written; every alias registered and making its node; **a comp of alias nodes
rendered and its pixels compared** (Copy, ChannelMerge, TimeClip, AdjustBBox: values worked out by hand) and seven
aliases rendering the same pixels as Natron's node set up by hand; the keys' table and the commands' work; the import
and the first-launch question on the fixtures (the `.nuke` folder fingerprinted unchanged); the look's reset into a
settings file standing in for Natron's. Then **the tools** (`tool_checks.py`): each gizmo made by its ID and
rendering known pixels (Grain's average and spread per channel, deterministic per frame; ZDefocus sharp at the focal
point, Natron's 8 px blur far from it, half and half between two slices, depth.Z picked; EdgeExtend's colour pushed
out with the alpha kept; ChromaticAberration as Natron's LensDistortion per channel; Vignette's centre and corners on
square and 640 × 480 inputs and behind another gizmo; STMapIdentity's values and an identity STMap), every gizmo
renamed after creation (their expressions follow), a comp of every gizmo saved; the workflow scripts on test comps
(layers of a multi-layer EXR extracted, similar class, Merge cycling, a roto following a track then baked, a
sequence collected, a flipbook rendered by a second NatronRenderer as frames and as an MP4, no player opened); the 18
expression recipes' values on known frames; the CG beauty rebuild adding up to a render's beauty and the grain and
lens stack rendering. `--gui` also opens Natron's window for about 25 seconds with a probe (`gui_probe/`): the
question, the Nuke menu and its keys (every tool's entry), the stylesheet in use, where keys act, a command through
its menu entry, each gizmo by its ID and coloured, Select similar colour, both studio ToolSets pasted with Natron's
paste onto a render and a checker (passes matched, the clipboard put back), Save selection as ToolSet and its paste,
an expression's window, and a picture of the window; it ends Natron at once so nothing is written at exit. Last,
**a NatronRenderer without the layer** (`project_checks.py`) opens the comps saved by the checks and renders them:
the gizmos (from the Groups saved in the comp, the same pixels to the last bit), the comp written by Collect files,
and the pasted ToolSets (the rebuild's beauty; the stack's pixels identical to its recipe's).

**Natron's settings are compared before and after** (every registry value under `HKCU\Software\INRIA`, Natron's
folders in `%LOCALAPPDATA%` and the home folder, the release folder): unchanged. The fork has no option to keep its
settings elsewhere, so the test never writes one; Natron itself records four switches for every PyPlug it registers
(the aliases `layer.nuke.*` and the gizmos `layer.gizmo.*`: 76 values), and the test takes out the ones added during
the run, as Singerie's Natron suite does. The window's checks use the system clipboard (pasting goes through it) and
put back what it held.

On a packaged build (`tools/package_build.py`), point `--renderer` at the build: the test then uses the build's own
copy of the layer with nothing on `NATRON_PLUGIN_PATH` (its last step then runs with the build's layer; the comps'
gizmos still open from the comps).

Things to know when writing a check run by `NatronRenderer -t`: never assign the name `app` in Natron's main
namespace (Natron calls a Group PyPlug's `createInstance(app1, app1.<node>)` and declares nodes on that same object);
a deleted node keeps its name for a while and Natron later removes that Python name, so the checks give their nodes
names never used twice; node colours exist only in the window; Writes store half floats unless told otherwise.

Last results: see `upstream.toml` `[tested]`.

## Bringing Niik-l's releases in

1. `python layer/tools/sync_upstream.py --watch` says what's new; `--push` fast-forwards `RB-2.6` and pushes his new
   tags. **Fast-forward only**: if his history was ever rewritten, nothing is pushed and a person looks.
2. Merge his release tag into `sng/main` (`git merge --no-ff natron-2.6-<date>`). His files and ours never overlap,
   so the merge is clean as long as there are no core patches.
3. Download that release's portable build and run the smoke test on it (with `--gui`).
4. When it passes, update `upstream.toml` (`[upstream]` and `[tested]`), push `sng/main`, make the build
   (`tools/package_build.py`) and publish it on Singerie (an admin's step).

**The upstream watch runs on a PC.** GitHub Actions are switched off for the whole BeeeFX/Natron repository (Baptiste,
5 October 2026), Niik-l's workflows and ours alike, so `.github/workflows/upstream-watch.yml` doesn't run on GitHub;
it's kept for the day Actions come back. Its job is `sync_upstream.py --watch`: it fetches Niik-l's `RB-2.6` and
release tags, compares them with our copy of his branch (BeeeFX/Natron when the PC can read it, else the local
branch) and with the release `sng/main` carries and was tested on (`upstream.toml`), prints what's new and the steps,
writes the same text to `--report <file>` when asked, and exits with 3 when something is new (0 when not). It builds
nothing, runs no Natron and pushes nothing. A weekly scheduled task on a PC with the working copy can run it, for
instance (Windows; not set up by the layer):

```
schtasks /Create /SC WEEKLY /D MON /ST 09:00 /TN "Natron upstream watch" /TR "python \"%USERPROFILE%\.singerie\tools\natron-fork\layer\tools\sync_upstream.py\" --watch --report \"%USERPROFILE%\natron-upstream.txt\""
```

The smoke test needs Windows and the release's portable build (no graphics card needed); it runs on a PC, and later
can run on a farm PC.

Niik-l's own workflows are in his files (`.github/workflows/`): "Build Installer" ran on every push of any branch and
"Tests" on pushes to `RB-2.6`, using Actions minutes for nothing this fork needs; with Actions off they no longer run.

## Making a build

```
python layer/tools/package_build.py --release "<Niik-l's portable release>" --tag natron-2.6-2026.09.20 [--number 1]
```

copies the release (only read), adds the layer (`Plugins/PyPlugs/layer`: startup files, aliases, gizmos;
`Resources/layer`: the rest, the studio ToolSets included), writes `Resources/layer/BUILD.toml` and `SOURCE.txt` (where the
corresponding source is, as the GPL asks), and zips it: `layer/dist/Natron-2.6.0-2026.09.20.sng1-win64.zip`, one
folder inside. Its version is **`2.6.0+2026.09.20.sng1`** (`2.6.0+<release date>.sng<n>`): Singerie's software
manager reads fork builds as `2.6.0+<build>`, so `2.6.x`, `2.6.0` and the exact build match it, `.sng2` sorts after
`.sng1`, and both after Niik-l's plain `2.6.0+2026.09.20`. The archive's name has `-` for `+` (Singerie's build list
takes no `+` in file names). Nothing is uploaded.

## Writing code here

- Natron and Qt only through `compat` (the adapter): one place to fix when the fork's API moves.
- Features are checked with `getPluginIDs()`, not versions.
- Startup files, PyPlugs and everything Natron runs as a script stay plain ASCII (Natron doesn't read them as UTF-8).
- Nothing writes Natron's settings without the artist's yes; nothing changes an artist's comps or files by itself
  (the tools change a comp only when the artist runs them on it; Collect files and the flipbook work on copies).
- Gizmos follow `gizmo_kit.py`'s rules (Natron's nodes, expressions reading a control, fixed inner names, no
  NatronGui), so a comp holding one renders anywhere.
- Each file starts with `SPDX-License-Identifier: GPL-3.0-or-later`.
- Code written here is our own. Something taken from an open-source project keeps its licence notice, is
  compatible with GPL-3.0-or-later, and is recorded in `../FORK.md` (Licences).
