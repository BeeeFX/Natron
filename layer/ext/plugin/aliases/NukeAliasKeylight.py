# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Nuke's Keylight for Natron: a toolset that makes Natron's own node (see natron_layer/aliases.py).

Natron's PIK keyer with the screen colour picked by hand, Keylight's way of working. PIK is IBK-like, not Keylight's algorithm, so mattes differ.
"""


def getPluginID():
    return "layer.nuke.Keylight"


def getLabel():
    return "Keylight"


def getVersion():
    return 1


def getGrouping():
    return "Nuke/Keyer"


def getPluginDescription():
    return "Nuke's Keylight, made with Natron's PIK. Natron's PIK keyer with the screen colour picked by hand, Keylight's way of working. PIK is IBK-like, not Keylight's algorithm, so mattes differ."


def getIsToolset():
    # Natron reads getIsToolset (this spelling) to know a PyPlug makes nodes instead of a Group
    # (Engine/AppManager.cpp, getGroupInfos).
    return True


def createInstance(app, group):
    import natron_layer.aliases

    natron_layer.aliases.make("Keylight", app, None if isinstance(group, str) else group)
