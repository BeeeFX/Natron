# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""STMapIdentity for Natron: one of the layer's gizmos, a Group of Natron's own nodes (see natron_layer/gizmos.py).

An ST map of the input's format: R = (x + 0.5) / width, G = (y + 0.5) / height, for STMap and lens distortion maps.
"""


def getPluginID():
    return "layer.gizmo.STMapIdentity"


def getLabel():
    return "STMapIdentity"


def getVersion():
    return 1


def getGrouping():
    return "Nuke/Transform"


def getPluginDescription():
    return "An ST map of the input's format: R = (x + 0.5) / width, G = (y + 0.5) / height, for STMap and lens distortion maps. One of this Natron's gizmos: Natron's own nodes inside, so a comp holding it renders on the farm and opens as a plain Group where the layer isn't installed."


def createInstance(app, group):
    import natron_layer.gizmos

    natron_layer.gizmos.build("STMapIdentity", app, group)
