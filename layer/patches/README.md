# Core patches

Changes to Natron's own files (its C++ code, its build), carried on top of Niik-l's releases. **There are none
yet**: everything the layer does goes through Natron's own ways in (startup scripts, PyPlugs, the stylesheet,
preferences), which cost nothing when a new release comes.

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

When a patch exists, sng/main also carries it as commits, the build is made from source (the fork's
`tools/win-build` scripts), and `upstream.toml`'s `[patches] count` says how many. The candidates, in order, are in
`../GAPS.md` (shortcut import and export in Natron's shortcut editor, Tab search favourites, centre the node graph on
a node).
