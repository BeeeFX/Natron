# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Vignette for Natron: one of the layer's gizmos, a Group of Natron's own nodes (see natron_layer/gizmos.py).

Darken the edges with an ellipse fitted to the input's format.
"""


def getPluginID():
    return "layer.gizmo.Vignette"


def getLabel():
    return "Vignette"


def getVersion():
    return 1


def getGrouping():
    return "Nuke/Draw"


def getPluginDescription():
    return "Darken the edges with an ellipse fitted to the input's format. One of this Natron's gizmos: Natron's own nodes inside, so a comp holding it renders on the farm and opens as a plain Group where the layer isn't installed."


def createInstance(app, group):
    import natron_layer.gizmos

    natron_layer.gizmos.build("Vignette", app, group)
