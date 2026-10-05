# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Nuke's AdjustBBox for Natron: a toolset that makes Natron's own node (see natron_layer/aliases.py).

Natron's AdjustRoD (Add Pixels).
"""


def getPluginID():
    return "layer.nuke.AdjustBBox"


def getLabel():
    return "AdjustBBox"


def getVersion():
    return 1


def getGrouping():
    return "Nuke/Transform"


def getPluginDescription():
    return "Nuke's AdjustBBox, made with Natron's AdjustRoD. Natron's AdjustRoD (Add Pixels)."


def getIsToolset():
    # Natron reads getIsToolset (this spelling) to know a PyPlug makes nodes instead of a Group
    # (Engine/AppManager.cpp, getGroupInfos).
    return True


def createInstance(app, group):
    import natron_layer.aliases

    natron_layer.aliases.make("AdjustBBox", app, None if isinstance(group, str) else group)
