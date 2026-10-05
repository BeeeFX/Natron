# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Nuke's Denoise for Natron: a toolset that makes Natron's own node (see natron_layer/aliases.py).

Natron's DenoiseSharpen (wavelets). Analyse the noise first, as with Denoise.
"""


def getPluginID():
    return "layer.nuke.Denoise"


def getLabel():
    return "Denoise"


def getVersion():
    return 1


def getGrouping():
    return "Nuke/Filter"


def getPluginDescription():
    return "Nuke's Denoise, made with Natron's DenoiseSharpen. Natron's DenoiseSharpen (wavelets). Analyse the noise first, as with Denoise."


def getIsToolset():
    # Natron reads getIsToolset (this spelling) to know a PyPlug makes nodes instead of a Group
    # (Engine/AppManager.cpp, getGroupInfos).
    return True


def createInstance(app, group):
    import natron_layer.aliases

    natron_layer.aliases.make("Denoise", app, None if isinstance(group, str) else group)
