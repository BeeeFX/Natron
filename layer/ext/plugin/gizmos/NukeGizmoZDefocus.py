# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""ZDefocus for Natron: one of the layer's gizmos, a Group of Natron's own nodes (see natron_layer/gizmos.py).

Defocus by depth: sharp at the focal point, blurred away from it.
"""


def getPluginID():
    return "layer.gizmo.ZDefocus"


def getLabel():
    return "ZDefocus"


def getVersion():
    return 1


def getGrouping():
    return "Nuke/Filter"


def getPluginDescription():
    return "Defocus by depth: sharp at the focal point, blurred away from it. One of this Natron's gizmos: Natron's own nodes inside, so a comp holding it renders on the farm and opens as a plain Group where the layer isn't installed."


def createInstance(app, group):
    import natron_layer.gizmos

    natron_layer.gizmos.build("ZDefocus", app, group)
