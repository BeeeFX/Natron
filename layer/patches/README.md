# Core patches

Changes to Natron's own files (its C++ code, its build), carried on top of Niik-l's releases. **Eight**: three since
`.sng3` (31 October 2026), two more since `.sng4`, one more since `.sng5`, two more since `.sng6` (1 November 2026);
about 1,190 changed lines in all, all written so Niik-l can take them as they are: new preferences whose
defaults are Natron's own behaviour (nothing changes for anyone who doesn't set them), and a name for the stylesheet.
The layer sets the Nuke-like values for the session, like its other preferences.

| Patch | What | Files, lines | Upstream |
|---|---|---|---|
| `0001-Node-graph-drawing-preferences.patch` | The node graph's drawing as preferences (Appearance > Node Graph > Node and link drawing): node width and height, corner radius, shading strength, outline colour, selected colour and tint (instead of the halo), Dot diameter, link width and colours, arrow head length and opening, the disabled cross's colour and width, whether new Read nodes show a postage stamp, and whether a node grows to fit a longer label. GAPS.md, "Nuke's look". | `Engine/Settings.{h,cpp}`, `Engine/Node.cpp`, `Gui/NodeGui.{h,cpp}`, `Gui/Edge.cpp`, `Gui/DotGui.cpp`, `Gui/NodeGraphRectItem.{h,cpp}`; see the patch's header | to offer |
| `0002-Properties-panel-header-name.patch` | The properties panels' header gets an object name (`DockablePanelHeader`) so a stylesheet can draw its buttons apart from the knobs' own (flat, as Nuke's). | `Gui/DockablePanel.cpp`, 2 lines | to offer |
| `0003-Node-graph-errors-and-selection.patch` (on top of 0001) | A node in error drawn in an error colour with an outline and frame of it, its message on hover (preferences `nodeErrorTint`, `nodeErrorColor`; 0 keeps Natron's frame and large ERROR); a selected node keeps its own colour, brightened, with an outline in the selection colour; with postage stamps off, a Read says "File not found" as soon as its file is named (nothing else renders an unconnected Read); a node shows a message it got before its drawing existed. | `Engine/Settings.cpp`, `Engine/ReadNode.cpp`, `Gui/NodeGui.{h,cpp}`; 166 lines added, 7 removed | to offer |

| `0004-Properties-panel-rows.patch` | The properties rows as Nuke's, as preferences (Appearance > Main Window): `sliderHandleBar`, `knobDimensionButtonLast`, `knobAnimationButton`, `pageTabNodeName`; a drop-down whose `flat` property is set drawn without its box. | `Engine/Settings.cpp`, `Gui/KnobGui.cpp`, `Gui/KnobGuiValue.cpp`, `Gui/ScaleSliderQWidget.cpp`, `Gui/DockablePanel.cpp`, `Gui/ComboBox.cpp`; 104 lines added, 10 removed | not offered (kept private for now, Baptiste) |
| `0005-Node-graph-viewer-labels-backdrops.patch` (on top of 0001 and 0003) | `linkLabelNearInput`, `viewerNodePointed`, `backdropLabelOnly`, `nodeBadgesFlat`, `nodeNameKeepsSize` (Appearance > Node Graph > Node and link drawing). | `Engine/Settings.cpp`, `Gui/Edge.cpp`, `Gui/NodeGraphRectItem.{h,cpp}`, `Gui/NodeGui.cpp`, `Gui/BackdropGui.cpp`; 139 lines added, 9 removed | not offered (kept private for now, Baptiste) |

| `0006-Timeline-ruler-and-knob-widgets.patch` (on top of 0004) | `timelineRulerNuke` (the timeline's frame ruler as Nuke's: no axis line, short ticks and taller numbered ones on one baseline, the cached line under them, the in and out points as upright lines, regular-weight numbers), `knobWidgetsShaded` (check boxes with a small cross in a darker square, drop-downs shaded light to dark), and `sliderHandleBar` drawing the scale as Nuke's (a dark groove, dark ticks and numbers). | `Engine/Settings.cpp`, `Gui/TimeLineGui.cpp`, `Gui/ScaleSliderQWidget.cpp`, `Gui/AnimatedCheckBox.cpp`, `Gui/ComboBox.cpp`; 137 lines added, 41 removed (since `.sng7` the current frame's number beside its marker and the in and out points' beside their lines, for a ruler as compact as Nuke's) | not offered (kept private for now, Baptiste) |

| `0007-Viewer-info-bar-curves-and-dope-sheet.patch` | `viewerInfoNuke` (the viewer's info bar as Nuke's: "bbox:", "channels: rgba" after it, the values in Nuke's brighter red, green and blue with a white alpha, "H: 51 S:0.05 V:0.86  L: 0.84822"), `animationEditorsNuke` (the r, g, b and a curves red, green, blue and white; the dope sheet's keys as narrow grey bars). | `Engine/Settings.cpp`, `Gui/InfoViewerWidget.cpp`, `Gui/CurveEditor.cpp`, `Gui/DopeSheetView.cpp`; 112 lines added, 18 removed | not offered (kept private for now, Baptiste) |
| `0008-Selected-node-fill-and-Tab-favourites.patch` (on top of 0001, 0003 and 0005) | `nodeSelectedFill` (a selected node filled flat with the selection colour inside a rim of its own colour, as Nuke's), `tabSearchNuke` and `tabFavourites` (the Tab search with favourites first and a star on each row, a green dot for the nodes made most often, the typed letters bold). | `Engine/Settings.cpp`, `Gui/NodeGraphRectItem.{h,cpp}`, `Gui/NodeGui.cpp`, `Gui/NodeCreationDialog.cpp`; 178 lines added, 12 removed | not offered (kept private for now, Baptiste) |
| `0009-Viewer-B-input-freeze.patch` (a fix, since `.sng7`) | **Shift+1 in the viewer froze Natron** (the B side): `InspectorNode::refreshActiveInputs` turned the compare operation on (Wipe) while holding the viewer's active-inputs lock; that shows the B info bar, Qt 6 repaints the viewer at once, and its drawing waited for the same lock forever. The operation is now changed once the lock is released. Reproduced on Niik-l's own 2026.10.02 release, without the layer: a bug of his, not ours. No preference (a fix, not a look). | `Engine/NodeInputs.cpp`; 12 lines added, 10 removed | not offered yet (the first to offer when Baptiste says so) |

**The budget is full again** (8 of 8 patches for the look, about 1,210 lines for about 1,200: a little over since `.sng7`'s compact ruler; the fix 0009 counts apart). It grew for `.sng6` by two patches and
300 lines (1 November 2026, round 5): the viewer's info bar, the curve editor's colours, the dope sheet's keys, the
node graph's selected node and the Tab search's list are all painted by Natron's C++ code, four places a stylesheet
or the Python layer can't reach (the info bar's labels get their text from C++ with no signal Python could follow).
Two patches rather than one keeps each under 300 lines. A next core change replaces or grows one of these.

**Fixes of Niik-l's own bugs count apart** (since `.sng7`, 1 November 2026; `upstream.toml`'s `fixes`): a freeze
or a crash in his code can't wait for a free place in the look's budget. Each is as small as it can be, has no
preference, and is the first thing to offer him when Baptiste says so. Today one: 0009. Patch 0006 also grew by 19
lines for `.sng7` (the ruler's labels beside their marks, for the compact timeline), within the look's budget.

`fixes/` holds something else: **build fixes for the plug-ins' and Cycles' sources** (not Natron's), needed when the MSYS2
packages of a release's day are newer than Niik-l's PC had, applied by `../tools/source_build.sh` after his own
plug-in patches. Today two: `openfx-io-ffmpeg8.patch` (openfx-io's FFmpeg writer read `AVCodec::pix_fmts`, which
FFmpeg 8 removed; it now asks `avcodec_get_supported_config`, and still reads the field on older FFmpeg), to offer
to NatronGitHub/openfx-io; `cycles-node-define-init-order.patch` (Cycles' `NODE_DEFINE` locked a static mutex that
another file's static values reach before it is made; with GCC 16's MinGW `std::mutex` the program stopped at start;
the mutex is now made on first use), to offer to Niik-l's Cycles. They don't count against the budget below.

A core patch has to be redone or rebased every time Niik-l publishes a release (every one to three weeks), so each
one is costly. The budget:

- **At most 8 core patches**, and **about 1,200 changed lines in Natron's files in total**, none over 300 lines (6 and
  900 until `.sng6`, 5 and 800 until `.sng5`).
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
(shortcut import and export in Natron's shortcut editor, the Tab search's menu-path column, centre the node graph on a node).
