# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""What a ToolSet's paste does to the artist's clipboard (layer/compat/natron_compat.py), with stand-ins for Qt's
clipboard: every format put back, an empty clipboard left empty, a full one never cleared. No Natron needed; the
window probe checks it with Qt's own clipboard.

    python layer/tests/smoke/test_clipboard.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "compat"))
sys.dont_write_bytecode = True
import natron_compat  # noqa: E402


class MimeData:
    def __init__(self, formats: dict[str, bytes] | None = None) -> None:
        self.held = dict(formats or {})

    def formats(self) -> list[str]:
        return list(self.held)

    def data(self, name: str) -> bytes:
        return self.held[name]

    def setData(self, name: str, value: bytes) -> None:  # noqa: N802  (Qt's name)
        self.held[name] = bytes(value)


class Board:
    def __init__(self, formats: dict[str, bytes]) -> None:
        self.content = MimeData(formats)
        self.cleared = 0

    def mimeData(self) -> MimeData:  # noqa: N802
        return self.content

    def setMimeData(self, data: MimeData) -> None:  # noqa: N802
        self.content = data

    def setText(self, text: str) -> None:  # noqa: N802
        self.content = MimeData({"text/plain": text.encode()})

    def clear(self) -> None:
        self.content = MimeData()
        self.cleared += 1


class Qt:
    class QtCore:
        QMimeData = MimeData

        @staticmethod
        def QByteArray(value: bytes) -> bytes:  # noqa: N802
            return bytes(value)


FILES = {"text/uri-list": b"file:///D:/plates/a.exr\r\nfile:///D:/plates/b.exr\r\n",
         "application/x-qt-windows-mime;value=\"FileName\"": b"A.EXR\x00", "text/plain": b"D:/plates/a.exr"}


class KeptClipboard(unittest.TestCase):
    def paste_with(self, board: Board) -> Board:
        with mock.patch.object(natron_compat, "_board", return_value=board), \
                mock.patch.object(natron_compat, "qt_modules", return_value=Qt), \
                mock.patch.object(natron_compat, "flush_clipboard"):
            with natron_compat.kept_clipboard():
                board.setText("<boost_serialization><Clipboard/></boost_serialization>")  # the ToolSet
        return board

    def test_copied_files_come_back_every_format(self) -> None:
        board = self.paste_with(Board(FILES))
        self.assertEqual(board.content.held, FILES)
        self.assertEqual(board.cleared, 0, "a clipboard that held something is never cleared")

    def test_an_empty_clipboard_stays_empty(self) -> None:
        board = self.paste_with(Board({}))
        self.assertEqual(board.content.held, {})

    def test_the_restored_data_is_kept_alive(self) -> None:
        board = self.paste_with(Board({"image/png": b"\x89PNG"}))
        self.assertIs(natron_compat._restored[0], board.content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
