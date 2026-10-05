# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""EdgeExtend for Natron: one of the layer's gizmos, a Group of Natron's own nodes (see natron_layer/gizmos.py).

Push a premultiplied image's colour out past its alpha, to fix fringes.
"""


def getPluginID():
    return "layer.gizmo.EdgeExtend"


def getLabel():
    return "EdgeExtend"


def getVersion():
    return 1


def getGrouping():
    return "Nuke/Filter"


def getPluginDescription():
    return "Push a premultiplied image's colour out past its alpha, to fix fringes. One of this Natron's gizmos: Natron's own nodes inside, so a comp holding it renders on the farm and opens as a plain Group where the layer isn't installed."


def createInstance(app, group):
    import natron_layer.gizmos

    natron_layer.gizmos.build("EdgeExtend", app, group)
