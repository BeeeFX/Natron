# Core patches

Changes to Natron's own files (its C++ code, its build), carried on top of Niik-l's releases. **Three since `.sng3`**
(31 October 2026, about 440 changed lines), all written so Niik-l can take them as they are: new preferences whose
defaults are Natron's own behaviour (nothing changes for anyone who doesn't set them), and a name for the stylesheet.
The layer sets the Nuke-like values for the session, like its other preferences.

| Patch | What | Files, lines | Upstream |
|---|---|---|---|
| `0001-Node-graph-drawing-preferences.patch` | The node graph's drawing as preferences (Appearance > Node Graph > Node and link drawing): node width and height, corner radius, shading strength, outline colour, selected colour and tint (instead of the halo), Dot diameter, link width and colours, arrow head length and opening, the disabled cross's colour and width, whether new Read nodes show a postage stamp, and whether a node grows to fit a longer label. GAPS.md, "Nuke's look". | `Engine/Settings.{h,cpp}`, `Engine/Node.cpp`, `Gui/NodeGui.{h,cpp}`, `Gui/Edge.cpp`, `Gui/DotGui.cpp`, `Gui/NodeGraphRectItem.{h,cpp}`; see the patch's header | to offer |
| `0002-Properties-panel-header-name.patch` | The properties panels' header gets an object name (`DockablePanelHeader`) so a stylesheet can draw its buttons apart from the knobs' own (flat, as Nuke's). | `Gui/DockablePanel.cpp`, 2 lines | to offer |
| `0003-Node-graph-errors-and-selection.patch` (on top of 0001) | A node in error drawn in an error colour with an outline and frame of it, its message on hover (preferences `nodeErrorTint`, `nodeErrorColor`; 0 keeps Natron's frame and large ERROR); a selected node keeps its own colour, brightened, with an outline in the selection colour; with postage stamps off, a Read says "File not found" as soon as its file is named (nothing else renders an unconnected Read); a node shows a message it got before its drawing existed. | `Engine/Settings.cpp`, `Engine/ReadNode.cpp`, `Gui/NodeGui.{h,cpp}`; 166 lines added, 7 removed | to offer |

`fixes/` holds something else: **build fixes for the plug-ins' and Cycles' sources** (not Natron's), needed when the MSYS2
packages of a release's day are newer than Niik-l's PC had, applied by `../tools/source_build.sh` after his own
plug-in patches. Today two: `openfx-io-ffmpeg8.patch` (openfx-io's FFmpeg writer read `AVCodec::pix_fmts`, which
FFmpeg 8 removed; it now asks `avcodec_get_supported_config`, and still reads the field on older FFmpeg), to offer
to NatronGitHub/openfx-io; `cycles-node-define-init-order.patch` (Cycles' `NODE_DEFINE` locked a static mutex that
another file's static values reach before it is made; with GCC 16's MinGW `std::mutex` the program stopped at start;
the mutex is now made on first use), to offer to Niik-l's Cycles. They don't count against the budget below.

A core patch has to be redone or rebased every time Niik-l publishes a release (every one to three weeks), so each
one is costly. The budget:

- **At most 5 core patches**, and **about 800 changed lines in Natron's files in total**, none over 300 lines.
- **None in the files the fork is busy rewriting** (the viewer's colour path, the 3D workspace, the properties panels
  of 3D nodes) unless Niik-l takes it.
- When the budget is full, a new patch replaces an old one or waits.

Each patch is a `git format-patch` file in this folder, listed in `series`, whose header says:

- what it does and which gap of `../GAPS.md` it serves;
- its size (files and lines changed);
- `upstream: offered <link>` (offered to Niik-l, and to NatronGitHub when it isn't tied to the fork's 3D work) or
  `local: <why it isn't offered>`. Every fix is offered upstream within two weeks of being written.

`sng/main` also carries the patches as commits, so a build from `sng/main` has them; the files here are the same
changes, kept for offering them and for re-applying them on a new release (`git am layer/patches/000*.patch` on his
tag, when a merge conflicts). Since there are patches, the build is made from source (`../README.md`, "Building from
source"), and `upstream.toml`'s `[patches] count` says how many. The next candidates, in order, are in `../GAPS.md`
(shortcut import and export in Natron's shortcut editor, Tab search favourites, centre the node graph on a node).
