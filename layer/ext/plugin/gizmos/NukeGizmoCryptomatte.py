# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Cryptomatte for Natron: one of the layer's gizmos, a Group of Natron's own nodes (see natron_layer/cryptomatte.py).

A matte of the objects named in a list, from a render's Cryptomatte layers.
"""


def getPluginID():
    return "layer.gizmo.Cryptomatte"


def getLabel():
    return "Cryptomatte"


def getVersion():
    return 1


def getGrouping():
    return "Nuke/Keyer"


def getPluginDescription():
    return "A matte of the objects named in a list, from a render's Cryptomatte layers (Blender's CryptoObject, CryptoMaterial, CryptoAsset, Karma's CryptoPrimitives...): every rank summed exactly, names with wildcards, Ctrl+click in the viewer to add or remove an object, rendered on the CPU. One of this Natron's gizmos: Natron's own nodes inside, so a comp holding it renders on the farm and opens as a plain Group where the layer isn't installed."


def createInstance(app, group):
    import natron_layer.gizmos

    natron_layer.gizmos.build("Cryptomatte", app, group)
