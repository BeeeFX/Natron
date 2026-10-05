# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Nuke's ShuffleCopy for Natron: a toolset that makes Natron's own node (see natron_layer/aliases.py).

Natron's Shuffle has both inputs (B and A) and every channel of each, which is what ShuffleCopy does.
"""


def getPluginID():
    return "layer.nuke.ShuffleCopy"


def getLabel():
    return "ShuffleCopy"


def getVersion():
    return 1


def getGrouping():
    return "Nuke/Channel"


def getPluginDescription():
    return "Nuke's ShuffleCopy, made with Natron's Shuffle. Natron's Shuffle has both inputs (B and A) and every channel of each, which is what ShuffleCopy does."


def getIsToolset():
    # Natron reads getIsToolset (this spelling) to know a PyPlug makes nodes instead of a Group
    # (Engine/AppManager.cpp, getGroupInfos).
    return True


def createInstance(app, group):
    import natron_layer.aliases

    natron_layer.aliases.make("ShuffleCopy", app, None if isinstance(group, str) else group)
