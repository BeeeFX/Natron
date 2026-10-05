# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Nuke's CurveTool for Natron: a toolset that makes Natron's own node (see natron_layer/aliases.py).

Natron's ImageStatistics: min, max, mean and more over a rectangle, per frame or a sequence.
"""


def getPluginID():
    return "layer.nuke.CurveTool"


def getLabel():
    return "CurveTool"


def getVersion():
    return 1


def getGrouping():
    return "Nuke/Image"


def getPluginDescription():
    return "Nuke's CurveTool, made with Natron's ImageStatistics. Natron's ImageStatistics: min, max, mean and more over a rectangle, per frame or a sequence."


def getIsToolset():
    # Natron reads getIsToolset (this spelling) to know a PyPlug makes nodes instead of a Group
    # (Engine/AppManager.cpp, getGroupInfos).
    return True


def createInstance(app, group):
    import natron_layer.aliases

    natron_layer.aliases.make("CurveTool", app, None if isinstance(group, str) else group)
