# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The layer's interface in Natron: the menu bar's Nuke menu, the Nuke keys Natron lacks, the artist's imported
Nuke shortcuts, and the first-launch question about their Nuke preferences.

Natron runs initGui.py after init.py, in sessions with an interface only, in its main namespace (natron_layer is
there, set by init.py). Natron takes menu entries only from here. This file stays plain ASCII.
"""

if globals().get("natron_layer") is not None:
    natron_layer.start_gui()  # noqa: F821  (set by init.py, in the same namespace)
