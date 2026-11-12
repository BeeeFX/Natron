# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Just enough OpenEXR for the Cryptomatte test, in the standard library only (no OpenEXR or numpy needed).

- ``write``: a single-part scanline EXR, uncompressed, 32-bit float channels, with string attributes (a
  Cryptomatte's manifest) in its header;
- ``read``: every channel of a scanline EXR, single- or multi-part, uncompressed, ZIPS or ZIP (what Karma, Blender
  and Natron's own Write make by default), half or float, as ``{channel: [row0 values…, row1…]}`` flattened, with each
  part's header attributes.

Written from the OpenEXR file layout document; independent of the node's own manifest reader, so the test's truth
doesn't come from the code it checks.
"""

from __future__ import annotations

import struct
import zlib
from collections.abc import Mapping, Sequence

MAGIC = 20000630
NO_COMPRESSION, ZIPS, ZIP = 0, 2, 3
LINES = {NO_COMPRESSION: 1, ZIPS: 1, ZIP: 16}
HALF, FLOAT = 1, 2


class Image:
    def __init__(self, width: int, height: int, channels: dict[str, list[float]], headers: list[dict]) -> None:
        self.width = width
        self.height = height
        self.channels = channels  # name -> width * height values, top row first
        self.headers = headers

    def get(self, *names: str) -> list[float] | None:
        for name in names:
            if name in self.channels:
                return self.channels[name]
        return None

    def strings(self) -> dict[str, str]:
        found: dict[str, str] = {}
        for header in self.headers:
            for key, (kind, value) in header.items():
                if kind == "string":
                    found[key] = value.decode("utf-8", "replace")
        return found


# --- Writing ---


def _attribute(name: str, kind: str, data: bytes) -> bytes:
    return name.encode() + b"\0" + kind.encode() + b"\0" + struct.pack("<i", len(data)) + data


def write(path: str, width: int, height: int, channels: Mapping[str, Sequence[float]],
          strings: Mapping[str, str] | None = None) -> None:
    """``channels``: name -> width * height floats, top row first."""
    names = sorted(channels)
    chlist = b"".join(n.encode() + b"\0" + struct.pack("<iB3xii", FLOAT, 0, 1, 1) for n in names) + b"\0"
    box = struct.pack("<iiii", 0, 0, width - 1, height - 1)
    header = b"".join([
        _attribute("channels", "chlist", chlist),
        _attribute("compression", "compression", bytes([NO_COMPRESSION])),
        _attribute("dataWindow", "box2i", box),
        _attribute("displayWindow", "box2i", box),
        _attribute("lineOrder", "lineOrder", b"\0"),
        _attribute("pixelAspectRatio", "float", struct.pack("<f", 1.0)),
        _attribute("screenWindowCenter", "v2f", struct.pack("<ff", 0.0, 0.0)),
        _attribute("screenWindowWidth", "float", struct.pack("<f", 1.0)),
        *(_attribute(k, "string", v.encode("utf-8")) for k, v in (strings or {}).items()),
    ]) + b"\0"
    long_names = any(len(n) > 31 for n in [*names, *(strings or {})])
    start = struct.pack("<ii", MAGIC, 2 | (0x400 if long_names else 0)) + header
    line_size = 4 * width * len(names)
    first_chunk = len(start) + 8 * height
    table = b"".join(struct.pack("<Q", first_chunk + y * (8 + line_size)) for y in range(height))
    with open(path, "wb") as file:
        file.write(start + table)
        for y in range(height):
            data = b"".join(struct.pack(f"<{width}f", *channels[n][y * width:(y + 1) * width]) for n in names)
            file.write(struct.pack("<ii", y, len(data)) + data)


# --- Reading ---


def _read_header(data: bytes, at: int) -> tuple[dict, int]:
    header = {}
    while data[at] != 0:
        end = data.index(b"\0", at)
        name = data[at:end].decode()
        at = end + 1
        end = data.index(b"\0", at)
        kind = data[at:end].decode()
        at = end + 1
        (size,) = struct.unpack_from("<i", data, at)
        at += 4
        header[name] = (kind, data[at:at + size])
        at += size
    return header, at + 1


def _channels(raw: bytes) -> list[tuple[str, int]]:
    found, at = [], 0
    while raw[at] != 0:
        end = raw.index(b"\0", at)
        name = raw[at:end].decode()
        (kind,) = struct.unpack_from("<i", raw, end + 1)
        found.append((name, kind))
        at = end + 1 + 16
    return found


def _unzip(block: bytes, expected: int) -> bytes:
    t = bytearray(zlib.decompress(block))
    for i in range(1, len(t)):
        t[i] = (t[i - 1] + t[i] - 128) & 0xFF
    half = (len(t) + 1) // 2
    out = bytearray(len(t))
    out[0::2] = t[:half]
    out[1::2] = t[half:]
    if len(out) != expected:
        raise ValueError(f"a ZIP block unpacked to {len(out)} bytes, not {expected}")
    return bytes(out)


def read(path: str) -> Image:
    with open(path, "rb") as file:
        data = file.read()
    magic, version = struct.unpack_from("<ii", data, 0)
    if magic != MAGIC:
        raise ValueError(f"{path} isn't an OpenEXR file")
    if version & 0x200 or version & 0x800:
        raise ValueError(f"{path}: tiled or deep files aren't read here")
    multipart = bool(version & 0x1000)
    at = 8
    headers = []
    while True:
        header, at = _read_header(data, at)
        headers.append(header)
        if not multipart or data[at] == 0:
            break
    if multipart:
        at += 1
    channels: dict[str, list[float]] = {}
    width = height = 0
    for header in headers:
        x0, y0, x1, y1 = struct.unpack("<iiii", header["dataWindow"][1])
        width, height = x1 - x0 + 1, y1 - y0 + 1
        compression = header["compression"][1][0]
        if compression not in LINES:
            raise ValueError(f"{path}: compression {compression} isn't read here")
        lines = LINES[compression]
        if multipart:
            (chunks,) = struct.unpack("<i", header["chunkCount"][1])
        else:
            chunks = (height + lines - 1) // lines
        offsets = struct.unpack_from(f"<{chunks}Q", data, at)
        at += 8 * chunks
        layout = _channels(header["channels"][1])
        for name, _ in layout:
            channels[name] = [0.0] * (width * height)
        for offset in offsets:
            pos = offset + (4 if multipart else 0)
            y, size = struct.unpack_from("<ii", data, pos)
            block = data[pos + 8:pos + 8 + size]
            rows = min(lines, y1 + 1 - y)
            expected = sum(width * (2 if kind == HALF else 4) for _, kind in layout) * rows
            pixels = block if size == expected else _unzip(block, expected)
            p = 0
            for row in range(rows):
                base = (y - y0 + row) * width
                for name, kind in layout:
                    fmt, step = ("e", 2) if kind == HALF else ("f", 4)
                    values = struct.unpack_from(f"<{width}{fmt}", pixels, p)
                    p += step * width
                    channels[name][base:base + width] = values
    return Image(width, height, channels, headers)
