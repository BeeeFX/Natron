# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""ChromaticAberration for Natron: one of the layer's gizmos, a Group of Natron's own nodes (see natron_layer/gizmos.py).

Split the colours towards the edges, as a lens does.
"""


def getPluginID():
    return "layer.gizmo.ChromaticAberration"


def getLabel():
    return "ChromaticAberration"


def getVersion():
    return 1


def getGrouping():
    return "Nuke/Filter"


def getPluginDescription():
    return "Split the colours towards the edges, as a lens does. One of this Natron's gizmos: Natron's own nodes inside, so a comp holding it renders on the farm and opens as a plain Group where the layer isn't installed."


def createInstance(app, group):
    import natron_layer.gizmos

    natron_layer.gizmos.build("ChromaticAberration", app, group)
