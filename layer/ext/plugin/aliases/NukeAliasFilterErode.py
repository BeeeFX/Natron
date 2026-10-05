# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Nuke's FilterErode for Natron: a toolset that makes Natron's own node (see natron_layer/aliases.py).

Natron's Erode (CImg): a negative size dilates.
"""


def getPluginID():
    return "layer.nuke.FilterErode"


def getLabel():
    return "FilterErode"


def getVersion():
    return 1


def getGrouping():
    return "Nuke/Filter"


def getPluginDescription():
    return "Nuke's FilterErode, made with Natron's Erode. Natron's Erode (CImg): a negative size dilates."


def getIsToolset():
    # Natron reads getIsToolset (this spelling) to know a PyPlug makes nodes instead of a Group
    # (Engine/AppManager.cpp, getGroupInfos).
    return True


def createInstance(app, group):
    import natron_layer.aliases

    natron_layer.aliases.make("FilterErode", app, None if isinstance(group, str) else group)
