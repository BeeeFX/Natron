# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Nuke's IBKGizmo for Natron: a toolset that makes Natron's own node (see natron_layer/aliases.py).

PIK is Natron's IBK-inspired keyer; set Screen Type to blue for a blue screen. Feed a clean plate to its C input as IBKGizmo's c input.
"""


def getPluginID():
    return "layer.nuke.IBKGizmo"


def getLabel():
    return "IBKGizmo"


def getVersion():
    return 1


def getGrouping():
    return "Nuke/Keyer"


def getPluginDescription():
    return "Nuke's IBKGizmo, made with Natron's PIK. PIK is Natron's IBK-inspired keyer; set Screen Type to blue for a blue screen. Feed a clean plate to its C input as IBKGizmo's c input."


def getIsToolset():
    # Natron reads getIsToolset (this spelling) to know a PyPlug makes nodes instead of a Group
    # (Engine/AppManager.cpp, getGroupInfos).
    return True


def createInstance(app, group):
    import natron_layer.aliases

    natron_layer.aliases.make("IBKGizmo", app, None if isinstance(group, str) else group)
