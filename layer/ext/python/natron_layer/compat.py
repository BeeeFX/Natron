# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The layer's adapter, ``layer/compat/natron_compat.py``, under the package's name.

The adapter lives in ``layer/compat`` (the repository's shape: one place for every call into Natron and Qt); this
module only imports it, so the rest of the package writes ``from . import compat``.
"""

from __future__ import annotations

import sys

from . import paths

_folder = str(paths.layer_root() / "compat")
if _folder not in sys.path:
    sys.path.insert(0, _folder)

from natron_compat import *  # noqa: E402,F403
from natron_compat import (  # noqa: E402,F401  (the names the package uses, listed for readers and linters)
    SettingsWriter,
    StoredSettings,
    active_app,
    add_menu_command,
    application,
    connect,
    create_node,
    gui_app,
    gui_natron,
    has_plugin,
    refresh_setting,
    information,
    is_background,
    natron,
    param_value,
    plugin_ids,
    qt_modules,
    say,
    select_only,
    selected_nodes,
    set_node_value,
    set_param_value,
    setting,
    setting_value,
    stored_keys,
    unique_name,
    unsaved,
    version,
    warning,
    write_to_script_editor,
)
