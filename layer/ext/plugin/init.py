# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The layer's start in Natron, in every session (with or without the interface).

Natron runs every init.py it finds in its PyPlugs folders and on NATRON_PLUGIN_PATH, as code in its main namespace
(there is no __file__). This one finds the layer's files (the folder holding upstream.toml) from the folder it sits
in, which carries the file layer_plugin.txt: in the repository that's layer/ext/plugin (the layer is two folders up),
in a packaged build Plugins/PyPlugs/layer (the layer is Resources/layer). It imports natron_layer into Natron's main
namespace (the menu commands name their functions natron_layer.<module>.<function>) and applies the Nuke look for
this session. Nothing is written to Natron's preferences. This file stays plain ASCII.
"""


def _layer_start():
    import importlib
    import os
    import sys

    import NatronEngine

    candidates = []
    explicit = os.environ.get("NATRON_LAYER_ROOT", "").strip()
    if explicit:
        candidates.append(explicit)
    for folder in [*NatronEngine.natron.getNatronPath(), *sys.path]:
        if os.path.isfile(os.path.join(str(folder), "layer_plugin.txt")):
            here = os.path.normpath(str(folder))
            candidates.append(os.path.join(here, "..", ".."))
            candidates.append(os.path.join(here, "..", "..", "..", "Resources", "layer"))
    for candidate in candidates:
        root = os.path.normpath(candidate)
        package = os.path.join(root, "ext", "python")
        if os.path.isfile(os.path.join(root, "upstream.toml")) and os.path.isdir(os.path.join(package, "natron_layer")):
            if package not in sys.path:
                sys.path.insert(0, package)
            layer = importlib.import_module("natron_layer")
            layer.start()
            return layer
    print("Natron layer: its files weren't found next to init.py, so Natron starts without its Nuke look.")
    return None


natron_layer = _layer_start()
del _layer_start
