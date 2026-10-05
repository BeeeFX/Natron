# What Natron still lacks compared with Nuke

Ranked by how much compositors use each thing (our estimate), from the gap analysis made for this fork on
27 September 2026 (Singerie's `docs/dev/research/parity-layers.md`, section 2.3). Each row says which way it can be
closed and where it stands.

**Routes.** **E**: through Natron's own ways in (startup scripts, PyPlugs, OpenFX plug-ins built apart, the
stylesheet, preferences), nothing of Natron's changed: costs nothing when a release comes. **C**: a core patch,
Natron's own code changed: costly at every release, so few (see `patches/README.md`).

**Status.** *done* (in the layer), *partly*, *planned* (in the roadmap below), *open*, *not planned*.

## Used all day

| # | Nuke | Natron today | Route | Status |
|---|---|---|---|---|
| 1 | Tab node search | Has it, ranked by use; no favourites | E: Nuke names as aliases. C: favourites and a menu-path column (about 150–300 lines) | **E done** (12 aliases, `Copy [Nuke]`); C planned (item 9) |
| 2 | Node graph behaviour and keys | Mostly (Dot, Backdrop, Ctrl+G, D, Ctrl+F, snap, Merge to A, colours per class) | E: Nuke's keys it lacks, preferences. Bookmarks: E panel plus C "centre on node" | **E done** for keys (K, I, `\`, Shift+Y, Alt+B) and preferences; bookmarks planned (item 12) |
| 3 | Viewer | Good, with the fork's OCIO display and view | E: flipbook through RV, ImageStatistics. C: input process | open (flipbook), not planned (input process, unless Niik-l wants it) |
| 4 | Properties bin | Partly (max panels, floating panels) | E: max panels. C: several and pinned bins | **E done** (10 panels); C not planned |
| 5 | Merge | Same as Nuke | E: key M (Natron's own), operator cycling | same key; cycling planned (item 6) |
| 6 | Grade, ColorCorrect, HueCorrect, OCIO | Same | E | same keys (G, C) |
| 7 | Transform, Reformat, Crop, CornerPin, filters, STMap | Same; LensWarp in the fork | E | **done** (CornerPin2D, AdjustBBox, FilterErode, Glow, Denoise aliases) |
| 8 | Roto, RotoPaint | Mostly; no planar tracker inside Roto | E: roto and tracker link scripts | same keys (O, P); scripts planned (item 6) |
| 9 | Tracker, CornerPin export | Has it | E: bake export, keys | open |
| 10 | Keying (Keylight, IBK, Primatte) | PIK (IBK-like), ChromaKeyer, Keyer | E: PIK presets named after Nuke's; a Keylight-class OpenFX keyer later | **partly** (Keylight and IBKGizmo aliases on PIK); OFX keyer planned (item 14) |
| 11 | Channels and layers | Multi-plane, Shuffle | E: Copy, ShuffleCopy, ChannelMerge; a Nuke channel system would be C, large | **E done** (aliases); channel system not planned |
| 12 | Curve editor, dope sheet, script editor | Has them | E | same |
| 13 | Expressions | Python expressions, no TCL | E: a snippet menu | planned (item 7) |
| 14 | Playback, caches, render queue | Has them | E | same |

## Used often

| # | Nuke | Natron today | Route | Status |
|---|---|---|---|---|
| 15 | Gizmos and ToolSets | PyPlugs; no ToolSets menu | E | planned (items 5 and 7) |
| 16 | Cryptomatte | A community GLSL keyer | E: an OpenFX plug-in | planned (item 10) |
| 17 | 3D: Axis, TransformGeo, WriteGeo, Normals | Missing in the fork | C in the fork's 3D code, offered to Niik-l only | open |
| 18 | ZDefocus, Bokeh | Community PyPlugs; DeepDefocus | E | open |
| 19 | Motion vectors, Kronos | No optical flow | E: offline flow plus PyPlugs, or OpenFX | open |
| 20 | Text, slates, burn-ins | **Arena (Text, ReadSVG, ReadPSD, Magick) is bundled from the 2026.10.02 release on** (checked in its source; the 2026.09.20 build tested here lacks it) | E | to check on the 2026.10.02 build |
| 21 | Denoise | DenoiseSharpen | E | **done** (Denoise alias) |
| 22 | Retime | Retime, FrameBlend, FrameHold, TimeOffset | E | **done** for TimeClip (alias) |
| 23 | BlinkScript | Shadertoy, SeExpr | E | open |
| 24 | Farm | NatronRenderer, Singerie's farm | E | done in Singerie |

## Specialist

| # | Nuke | Natron today | Route | Status |
|---|---|---|---|---|
| 25 | Deep | 17 nodes in the fork | C in the fork | open |
| 26 | CameraTracker, PointCloudGenerator | In the fork, early | check on a real shot | open |
| 27 | LiveGroups | Precomp, Groups | E | open |
| 28 | Opening .nk scripts | Nothing | E: a translator for common nodes | open |

## Nuke's look and habits (done in this layer)

The Nuke look by default (`ext/presets/nuke_look.toml`, `ext/qss/nuke.qss`), Nuke's keys
(`ext/presets/nuke_hotkeys.toml`: 49 compared, 38 already the same in Natron, 5 added, 3 missing, 3 different), the
Nuke group of aliases,
and "Import my Nuke preferences". Not reachable without a core patch: changing Natron's own default keys (they're
compiled in; an artist's own keys can only be stored in Natron's settings) and the font (Natron reads it before any
script runs).

## Roadmap (research section 2.7), and where this layer is

1. Layer folder, adapter and smoke test — **done**.
2. Nuke look — **done**.
3. Nuke keys — **done** for what Natron lacks; Natron's own keys clashing with an artist's imported ones are listed
   at import.
4. Nuke menu of aliases — **done** (12).
5. Curated gizmo pack from natron-plugins (each licence checked, Python 3.14 checked).
6. Workflow scripts (extract EXR layers, postage stamps, roto and tracker link, select similar, merge cycling,
   collect files, flipbook).
7. ToolSets and an expression snippet menu.
8. Shortcut import and export in Natron's shortcut editor (C, about 150–300 lines, offered to Niik-l and
   NatronGitHub).
9. Tab search favourites and a menu-path column (C).
10. Cryptomatte OpenFX plug-in.
11. Text and burn-ins (Arena: bundled since 2026.10.02, to check).
12. Centre the node graph on a node (C, small) and a bookmarks panel.
13. Missing 3D nodes, contributed to Niik-l's fork.
14. A Keylight-class keyer as an OpenFX plug-in.
15. Viewer input process (only if Niik-l wants it).
