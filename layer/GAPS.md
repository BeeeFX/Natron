# What Natron still lacks compared with Nuke

Ranked by how much compositors use each thing (our estimate), from the gap analysis made for this fork on
27 September 2026 (Singerie's `docs/dev/research/parity-layers.md`, section 2.3). Each row says which way it can be
closed and where it stands.

**Routes.** **E**: through Natron's own ways in (startup scripts, PyPlugs, OpenFX plug-ins built apart, the
stylesheet, preferences), nothing of Natron's changed: costs nothing when a release comes. **P**: Python (PySide)
acting on Natron's live interface from the startup scripts (Qt's picture cache, fonts, widgets), nothing of Natron's
changed: a release that renames a picture or widget leaves that one thing as Natron draws it. **C**: a core patch,
Natron's own code changed: costly at every release, so few (see `patches/README.md`).

**Status.** *done* (in the layer), *partly*, *planned* (in the roadmap below), *open*, *not planned*.

## Used all day

| # | Nuke | Natron today | Route | Status |
|---|---|---|---|---|
| 1 | Tab node search | Has it, ranked by use; no favourites | E: Nuke names as aliases and gizmos. C: favourites and a menu-path column (about 150–300 lines) | **E done** (13 aliases, `Copy [Nuke]`, and 6 gizmos); C planned (item 9) |
| 2 | Node graph behaviour and keys | Mostly (Dot, Backdrop, Ctrl+G, D, Ctrl+F, snap, Merge to A, colours per class) | E: Nuke's keys it lacks, preferences, select similar. Bookmarks: E panel plus C "centre on node" | **E done** for keys (K, I, `\`, Shift+Y, Alt+B, Alt+F), preferences and Select similar class / colour; bookmarks planned (item 12) |
| 3 | Viewer | Good, with the fork's OCIO display and view | E: flipbook through RV, ImageStatistics. C: input process | **flipbook done** (Alt+F: NatronRenderer in the background, then RV or a movie); input process not planned (unless Niik-l wants it) |
| 4 | Properties bin | Partly (max panels, floating panels) | E: max panels. C: several and pinned bins | **E done** (10 panels); C not planned |
| 5 | Merge | Same as Nuke | E: key M (Natron's own), operator cycling | same key; **cycling done** (Nuke › Merge › Next / Previous operation) |
| 6 | Grade, ColorCorrect, HueCorrect, OCIO | Same | E | same keys (G, C) |
| 7 | Transform, Reformat, Crop, CornerPin, filters, STMap | Same; LensWarp in the fork | E | **done** (CornerPin2D, AdjustBBox, FilterErode, Glow, Denoise aliases; STMapIdentity gizmo) |
| 8 | Roto, RotoPaint | Mostly; no planar tracker inside Roto | E: roto and tracker link scripts | same keys (O, P); **link done** (Nuke › Roto › Link roto to track: a Transform after the Roto follows a track; Natron takes no expression on a shape itself) |
| 9 | Tracker, CornerPin export | Has it, with linked or baked CornerPin and Transform export | E: bake export, keys | **done** (Nuke › Edit › Bake expressions to keyframes, for the roto link and anything else) |
| 10 | Keying (Keylight, IBK, Primatte) | PIK (IBK-like), ChromaKeyer, Keyer, Despill | E: PIK presets named after Nuke's; a Keylight-class OpenFX keyer later | **partly** (Keylight and IBKGizmo aliases on PIK; Natron's Despill covers a despill gizmo's controls); OFX keyer planned (item 14) |
| 11 | Channels and layers | Multi-plane, Shuffle | E: Copy, ShuffleCopy, ChannelMerge, an extract-layers script; a Nuke channel system would be C, large | **E done** (aliases; Nuke › Channel › Extract layers into Shuffles); channel system not planned |
| 12 | Curve editor, dope sheet, script editor | Has them | E | same |
| 13 | Expressions | Python expressions, no TCL | E: a snippet menu | **done** (Nuke › Expressions: 18 Nuke-style recipes) |
| 14 | Playback, caches, render queue | Has them | E | same |

## Used often

| # | Nuke | Natron today | Route | Status |
|---|---|---|---|---|
| 15 | Gizmos and ToolSets | PyPlugs; no ToolSets menu | E | **done**: 6 gizmos (Grain, ZDefocus, EdgeExtend, ChromaticAberration, Vignette, STMapIdentity); ToolSets (studio, the artist's, a project's through `NATRON_LAYER_TOOLSETS`; Singerie's tool library to come) |
| 16 | Cryptomatte | A community GLSL keyer | E: an OpenFX plug-in | planned (item 10) |
| 17 | 3D: Axis, TransformGeo, WriteGeo, Normals | Missing in the fork | C in the fork's 3D code, offered to Niik-l only | open |
| 18 | ZDefocus, Bokeh | Community PyPlugs (licences not stated); DeepDefocus | E | **ZDefocus done** (our gizmo: six depth slices, CImg's filters); bladed or disc bokeh would be an OpenFX plug-in, open |
| 19 | Motion vectors, Kronos | The fork's own **VectorBlur** (from motion vectors); no optical flow | E: offline flow plus PyPlugs, or OpenFX | VectorBlur **in the fork**; optical flow open |
| 20 | Text, slates, burn-ins | **Arena's Text is in the 2026.10.02 release and renders headless** (checked, below); 2026.09.20 lacks it | E: a slate and burn-in ToolSet or gizmo on Arena's Text | **Text there** (2026.10.02 on); the slate and burn-in tool planned (item 11) |
| 21 | Denoise | DenoiseSharpen | E | **done** (Denoise alias) |
| 22 | Retime | Retime, FrameBlend, FrameHold, TimeOffset | E | **done** for TimeClip (alias) |
| 23 | BlinkScript | Shadertoy, SeExpr | E | open |
| 24 | Farm | NatronRenderer, Singerie's farm | E | done in Singerie |

**Item 20, what changed upstream** (Niik-l's commits `04dc3195` and `5a04e697` of 1 October 2026 and his
`DEV_3D_SYSTEM_CHANGELOG.md`): his Windows and Linux builds now build and ship openfx-arena (`Arena.ofx`), from his
2026.10.02 release on. **Checked on that release's portable build (5 October 2026)**: 24 plug-ins more than
2026.09.20 and none fewer: Arena's 19 (`net.fxarena.openfx.*`: **Text**, ReadSVG, ReadPSD, Arc, Charcoal, Edges,
Implode, Modulate, Morphology, Oilpaint, Polar, Polaroid, Reflection, Roll, Sketch, Swirl, Texture, Tile, Wave) and
five readers that come with it (`fr.inria.openfx.ReadKrita`, `ReadCDR`, `ReadPDF`, `ReadMisc`, `OpenRaster`).
**Text renders in NatronRenderer** (the smoke test draws "SNG 1001" on black and finds the letters): it finds the
PC's fonts (its font menu lists the Windows ones; NatronRenderer prints that the release's own fontconfig folder
is missing, harmless here), with size, colour, alignment, wrapping, stroke, letter spacing and a subtitle file
input. So building Arena ourselves (roadmap item 11's first plan) isn't needed. Still to do: a slate and burn-in
tool on it (the frame number by expression, the shot name), a look on a farm PC (fonts there), and Niik-l's own
caveat: Arena carries an older copy of openfx-io's colour handling, so its readers (SVG, PSD) may show the old
default colourspace under ACES.

## Specialist

| # | Nuke | Natron today | Route | Status |
|---|---|---|---|---|
| 25 | Deep | 17 nodes in the fork | C in the fork | open |
| 26 | CameraTracker, PointCloudGenerator | In the fork, early | check on a real shot | open |
| 27 | LiveGroups | Precomp, Groups | E | open |
| 28 | Opening .nk scripts | Nothing | E: a translator for common nodes | open |

## Nuke's look and habits (done in this layer)

The Nuke look by default (`ext/presets/nuke_look.toml`, `ext/qss/nuke.qss`), the skin (`natron_layer/skin.py`,
route P: our own icons, the font, the session stylesheet, the properties pane's share), Nuke's keys
(`ext/presets/nuke_hotkeys.toml`: 50 compared, 38 already the same in Natron, 6 added, 3 missing, 3 different), the
Nuke group of aliases and gizmos, the workflow scripts, ToolSets and expressions, and "Import my Nuke preferences".
Not reachable without a core patch: changing Natron's own default keys (they're compiled in; an artist's own keys
can only be stored in Natron's settings). The node graph's drawing (node size and shading, link width and arrows,
selection tint, the disabled cross, Dots, postage stamps on Read nodes) is **core patch 0001** since `.sng3`
(preferences defaulting to Natron's drawing, the look setting Nuke's; `README.md`, "The node graph's drawing"). The
font, once thought out of
reach (Natron reads it before any script runs), is reached through Qt: the skin registers its own and substitutes it
for Natron's.

Done in `.sng3`: the second wave of icons (the Merge operations' pictures, the roto, paint and tracker tools, the
curve editor's interpolation buttons, the text style buttons, the File menu's icons through an icon theme), the
properties panels' header buttons flat (core patch 0002 names the header), Tab's search box in Nuke's style.

Still Natron's (next): the knobs' own check boxes and Natron's custom drop-downs and sliders (drawn by Natron
itself), the viewer's two toolbars' order and the info bar's layout (moving Natron's widgets is fragile; a core patch
if Baptiste wants it), the curve editor's and dope sheet's own drawing beyond their colours, the node indicators'
glossy round badges ("E", "V", "P"), the few icons no one has drawn yet (the combo box arrows, the cursors, the
application and viewer icons).

## Roadmap (research section 2.7), and where this layer is

1. Layer folder, adapter and smoke test — **done**.
2. Nuke look — **done**; the skin (icons, font, flat stylesheet, palette, layout share) — **first wave done**
   (`.sng2`), **second wave done** (`.sng3`: the rest of the icons, the menus', the panel headers, Tab's box); the node
   graph drawn like Nuke's — **done** (`.sng3`, core patch 0001, this fork's first source build).
3. Nuke keys — **done** for what Natron lacks; Natron's own keys clashing with an artist's imported ones are listed
   at import.
4. Nuke menu of aliases — **done** (13).
5. Curated gizmo pack — **done** (6, our own: natron-plugins' licences aren't stated per plug-in, see `../FORK.md`).
6. Workflow scripts — **done** (extract layers, postage stamp, roto and tracker link and bake, select similar, merge
   cycling, collect files, flipbook).
7. ToolSets and an expression snippet menu — **done** (two studio ToolSets; sharing per project through Singerie's
   tool library is the Singerie side, to build).
8. Shortcut import and export in Natron's shortcut editor (C, about 150–300 lines, offered to Niik-l and
   NatronGitHub).
9. Tab search favourites and a menu-path column (C).
10. Cryptomatte OpenFX plug-in.
11. Text and burn-ins: Arena's Text ships with Niik-l's 2026.10.02 release and renders headless (checked, above);
    next, a slate and burn-in ToolSet or gizmo on it.
12. Centre the node graph on a node (C, small) and a bookmarks panel.
13. Missing 3D nodes, contributed to Niik-l's fork.
14. A Keylight-class keyer as an OpenFX plug-in.
15. Viewer input process (only if Niik-l wants it).
