# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Nuke's Copy for Natron: a toolset that makes Natron's own node (see natron_layer/aliases.py).

A Shuffle that keeps B's colour and takes A's alpha, like Copy's default (alpha to alpha). Pick other channels in its R, G, B, A menus.
"""


def getPluginID():
    return "layer.nuke.Copy"


def getLabel():
    return "Copy"


def getVersion():
    return 1


def getGrouping():
    return "Nuke/Channel"


def getPluginDescription():
    return "Nuke's Copy, made with Natron's Shuffle. A Shuffle that keeps B's colour and takes A's alpha, like Copy's default (alpha to alpha). Pick other channels in its R, G, B, A menus."


def getIsToolset():
    # Natron reads getIsToolset (this spelling) to know a PyPlug makes nodes instead of a Group
    # (Engine/AppManager.cpp, getGroupInfos).
    return True


def createInstance(app, group):
    import natron_layer.aliases

    natron_layer.aliases.make("Copy", app, None if isinstance(group, str) else group)
