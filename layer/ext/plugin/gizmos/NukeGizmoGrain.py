# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Grain for Natron: one of the layer's gizmos, a Group of Natron's own nodes (see natron_layer/gizmos.py).

Film grain per channel, sized in pixels, following the image's brightness.
"""


def getPluginID():
    return "layer.gizmo.Grain"


def getLabel():
    return "Grain"


def getVersion():
    return 1


def getGrouping():
    return "Nuke/Draw"


def getPluginDescription():
    return "Film grain per channel, sized in pixels, following the image's brightness. One of this Natron's gizmos: Natron's own nodes inside, so a comp holding it renders on the farm and opens as a plain Group where the layer isn't installed."


def createInstance(app, group):
    import natron_layer.gizmos

    natron_layer.gizmos.build("Grain", app, group)
