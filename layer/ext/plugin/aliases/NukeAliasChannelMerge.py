# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Nuke's ChannelMerge for Natron: a toolset that makes Natron's own node (see natron_layer/aliases.py).

A Merge working on alpha only, with screen (a + b - ab, ChannelMerge's union); B's colour passes.
"""


def getPluginID():
    return "layer.nuke.ChannelMerge"


def getLabel():
    return "ChannelMerge"


def getVersion():
    return 1


def getGrouping():
    return "Nuke/Channel"


def getPluginDescription():
    return "Nuke's ChannelMerge, made with Natron's Merge. A Merge working on alpha only, with screen (a + b - ab, ChannelMerge's union); B's colour passes."


def getIsToolset():
    # Natron reads getIsToolset (this spelling) to know a PyPlug makes nodes instead of a Group
    # (Engine/AppManager.cpp, getGroupInfos).
    return True


def createInstance(app, group):
    import natron_layer.aliases

    natron_layer.aliases.make("ChannelMerge", app, None if isinstance(group, str) else group)
