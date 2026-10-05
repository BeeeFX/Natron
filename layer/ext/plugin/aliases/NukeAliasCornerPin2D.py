# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Nuke's CornerPin2D for Natron: a toolset that makes Natron's own node (see natron_layer/aliases.py).

Natron's CornerPin.
"""


def getPluginID():
    return "layer.nuke.CornerPin2D"


def getLabel():
    return "CornerPin2D"


def getVersion():
    return 1


def getGrouping():
    return "Nuke/Transform"


def getPluginDescription():
    return "Nuke's CornerPin2D, made with Natron's CornerPin. Natron's CornerPin."


def getIsToolset():
    # Natron reads getIsToolset (this spelling) to know a PyPlug makes nodes instead of a Group
    # (Engine/AppManager.cpp, getGroupInfos).
    return True


def createInstance(app, group):
    import natron_layer.aliases

    natron_layer.aliases.make("CornerPin2D", app, None if isinstance(group, str) else group)
