# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Nuke's PostageStamp for Natron: a toolset that makes Natron's own node (see natron_layer/aliases.py).

A NoOp showing its input's picture on the node in the graph (Natron's node preview, on for this one).
"""


def getPluginID():
    return "layer.nuke.PostageStamp"


def getLabel():
    return "PostageStamp"


def getVersion():
    return 1


def getGrouping():
    return "Nuke/Other"


def getPluginDescription():
    return "Nuke's PostageStamp, made with Natron's NoOp. A NoOp showing its input's picture on the node in the graph (Natron's node preview, on for this one)."


def getIsToolset():
    # Natron reads getIsToolset (this spelling) to know a PyPlug makes nodes instead of a Group
    # (Engine/AppManager.cpp, getGroupInfos).
    return True


def createInstance(app, group):
    import natron_layer.aliases

    natron_layer.aliases.make("PostageStamp", app, None if isinstance(group, str) else group)
