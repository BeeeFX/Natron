# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Nuke's Glow for Natron: a toolset that makes Natron's own node (see natron_layer/aliases.py).

Natron's Bloom: a stack of growing blurs added together, close to Glow without its tolerance controls.
"""


def getPluginID():
    return "layer.nuke.Glow"


def getLabel():
    return "Glow"


def getVersion():
    return 1


def getGrouping():
    return "Nuke/Filter"


def getPluginDescription():
    return "Nuke's Glow, made with Natron's Bloom. Natron's Bloom: a stack of growing blurs added together, close to Glow without its tolerance controls."


def getIsToolset():
    # Natron reads getIsToolset (this spelling) to know a PyPlug makes nodes instead of a Group
    # (Engine/AppManager.cpp, getGroupInfos).
    return True


def createInstance(app, group):
    import natron_layer.aliases

    natron_layer.aliases.make("Glow", app, None if isinstance(group, str) else group)
