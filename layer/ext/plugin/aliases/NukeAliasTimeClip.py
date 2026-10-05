# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Nuke's TimeClip for Natron: a toolset that makes Natron's own node (see natron_layer/aliases.py).

Natron's FrameRange: frames outside the range held, black or looped.
"""


def getPluginID():
    return "layer.nuke.TimeClip"


def getLabel():
    return "TimeClip"


def getVersion():
    return 1


def getGrouping():
    return "Nuke/Time"


def getPluginDescription():
    return "Nuke's TimeClip, made with Natron's FrameRange. Natron's FrameRange: frames outside the range held, black or looped."


def getIsToolset():
    # Natron reads getIsToolset (this spelling) to know a PyPlug makes nodes instead of a Group
    # (Engine/AppManager.cpp, getGroupInfos).
    return True


def createInstance(app, group):
    import natron_layer.aliases

    natron_layer.aliases.make("TimeClip", app, None if isinstance(group, str) else group)
