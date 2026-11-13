# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The Cryptomatte node's arithmetic and file reading, in plain Python (no Natron needed, so it's tested alone).

Written from the Cryptomatte specification (Psyop, version 1.2.0, BSD-licensed document; nothing of its reference
code is used here):

- an object's **ID** is the MurmurHash3 (x86, 32-bit, seed 0) of its name's UTF-8 bytes, its bits read as a 32-bit
  float, with bit 23 flipped when the exponent would be 0 or 255 (so an ID is never a denormal, an infinity or NaN);
- a Cryptomatte called ``<name>`` is stored as layers ``<name>00``, ``<name>01``…, each holding two **ranks**: an ID
  in R with its coverage in G, the next ID in B with its coverage in A; ranks are sorted by coverage, highest first;
- its **manifest** (name -> the ID's eight hex digits) is in the EXR header as ``cryptomatte/<key>/manifest`` (JSON),
  or in a file next to the frames named by ``cryptomatte/<key>/manif_file``; ``cryptomatte/<key>/name`` is ``<name>``.

The matte of a set of IDs is the sum, over every rank, of the coverage where the rank's ID is in the set: exact at
edges and through motion blur, nothing where an ID isn't listed (an empty rank, ID 0, never matches).
"""

from __future__ import annotations

import csv
import fnmatch
import json
import os
import re
import struct
from collections.abc import Iterable
from typing import NamedTuple

# --- IDs ---


def murmur3_32(data: bytes, seed: int = 0) -> int:
    """MurmurHash3_x86_32 (Austin Appleby's public-domain algorithm)."""
    c1, c2, mask = 0xCC9E2D51, 0x1B873593, 0xFFFFFFFF
    h = seed & mask
    length = len(data)
    whole = length - length % 4
    for i in range(0, whole, 4):
        k = int.from_bytes(data[i:i + 4], "little")
        k = (k * c1) & mask
        k = ((k << 15) | (k >> 17)) & mask
        k = (k * c2) & mask
        h ^= k
        h = ((h << 13) | (h >> 19)) & mask
        h = (h * 5 + 0xE6546B64) & mask
    tail = data[whole:]
    k = 0
    for i in reversed(range(len(tail))):
        k = (k << 8) | tail[i]
    if tail:
        k = (k * c1) & mask
        k = ((k << 15) | (k >> 17)) & mask
        k = (k * c2) & mask
        h ^= k
    h ^= length
    h ^= h >> 16
    h = (h * 0x85EBCA6B) & mask
    h ^= h >> 13
    h = (h * 0xC2B2AE35) & mask
    h ^= h >> 16
    return h


def name_bits(name: str) -> int:
    """The ID of ``name`` as its 32 bits (the manifest's hex value)."""
    bits = murmur3_32(name.encode("utf-8"))
    exponent = (bits >> 23) & 0xFF
    if exponent in (0, 0xFF):
        bits ^= 1 << 23
    return bits


def bits_to_float(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", bits & 0xFFFFFFFF))[0]


def float_to_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def name_id(name: str) -> float:
    return bits_to_float(name_bits(name))


# --- The EXR header ---


class Cryptomatte(NamedTuple):
    name: str  # the layers' base name: CryptoObject, ViewLayer.CryptoMaterial, CryptoPrimitives…
    key: str  # the header's key (cryptomatte/<key>/…)
    manifest: dict[str, int]  # object name -> its ID's bits
    source: str  # where the manifest came from (the EXR, a sidecar file), "" when there's none


class HeaderError(ValueError):
    pass


def _header_strings(path: str, prefix: str) -> list[dict[str, str]]:
    """Every part's string attributes starting with ``prefix``, read from the header only (no pixels)."""
    with open(path, "rb") as file:
        start = file.read(8)
        if len(start) < 8 or struct.unpack("<i", start[:4])[0] != 20000630:
            raise HeaderError(f"{path} isn't an OpenEXR file")
        multipart = bool(struct.unpack("<i", start[4:])[0] & 0x1000)
        data = bytearray()
        at = 0

        def need(count: int) -> None:
            while len(data) < at + count:
                more = file.read(max(65536, count))
                if not more:
                    raise HeaderError(f"{path}: the header ends early")
                data.extend(more)

        parts: list[dict[str, str]] = []
        while True:
            found: dict[str, str] = {}
            need(1)
            if multipart and parts and data[at] == 0:
                break
            while True:
                need(1)
                if data[at] == 0:
                    at += 1
                    break
                fields = []
                for _ in range(2):
                    while True:
                        need(1)
                        end = data.find(b"\0", at)
                        if end >= 0:
                            break
                        need(len(data) - at + 1)
                    fields.append(bytes(data[at:end]).decode("utf-8", "replace"))
                    at = end + 1
                need(4)
                (size,) = struct.unpack_from("<i", data, at)
                at += 4
                need(size)
                name, kind = fields
                if kind == "string" and name.startswith(prefix):
                    found[name] = bytes(data[at:at + size]).decode("utf-8", "replace")
                at += size
            parts.append(found)
            if not multipart:
                break
    return parts


def _parse_manifest(text: str) -> dict[str, int]:
    found = json.loads(text) if text.strip() else {}
    manifest = {}
    for name, value in found.items():
        try:
            manifest[str(name)] = int(str(value), 16) & 0xFFFFFFFF
        except ValueError:
            continue
    return manifest


def read_manifest_file(path: str) -> dict[str, int]:
    """A sidecar manifest (a JSON object of name -> hex ID), or the manifests of an EXR's Cryptomattes merged."""
    if path.lower().endswith(".exr"):
        merged: dict[str, int] = {}
        for each in cryptomattes_in(path):
            merged.update(each.manifest)
        return merged
    with open(path, encoding="utf-8") as file:
        return _parse_manifest(file.read())


def cryptomattes_in(path: str) -> list[Cryptomatte]:
    """The Cryptomattes an EXR's header names, with their manifests (a ``manif_file`` read from the EXR's folder)."""
    by_key: dict[str, dict[str, str]] = {}
    for part in _header_strings(path, "cryptomatte/"):
        for attribute, value in part.items():
            pieces = attribute.split("/")
            if len(pieces) == 3:
                by_key.setdefault(pieces[1], {}).setdefault(pieces[2], value)
    found = []
    for key, fields in by_key.items():
        name = fields.get("name", "").strip()
        if not name:
            continue
        manifest: dict[str, int] = {}
        source = ""
        if "manifest" in fields:
            manifest, source = _parse_manifest(fields["manifest"]), path
        elif fields.get("manif_file"):
            sidecar = os.path.join(os.path.dirname(path), fields["manif_file"])
            if os.path.isfile(sidecar):
                manifest, source = read_manifest_file(sidecar), sidecar
        found.append(Cryptomatte(name, key, manifest, source))
    return found


# --- Frames on disk ---

_HASHES = re.compile(r"#+")
_PRINTF = re.compile(r"%0?(\d*)d")


def frame_file(pattern: str, frame: int) -> str:
    """``shot_####.exr`` or ``shot_%04d.exr`` at ``frame``; a plain file name as it is."""
    found = _HASHES.sub(lambda m: f"{frame:0{len(m.group())}d}", pattern)
    return _PRINTF.sub(lambda m: f"{frame:0{int(m.group(1) or 0)}d}", found)


def nearest_frame_file(pattern: str, frame: int) -> str | None:
    """The frame's file when it exists, else the sequence's file nearest to ``frame`` (a manifest seldom changes
    within a shot), else None."""
    exact = frame_file(pattern, frame)
    if os.path.isfile(exact):
        return exact
    if not (_HASHES.search(pattern) or _PRINTF.search(pattern)):
        return None
    folder, name = os.path.split(pattern)
    head = re.escape(_PRINTF.sub("#", _HASHES.sub("#", name)))
    shape = re.compile("^" + head.replace(r"\#", r"(-?\d+)").replace("#", r"(-?\d+)") + "$", re.I)
    best = None
    try:
        listed = os.listdir(folder or ".")
    except OSError:
        return None
    for entry in listed:
        match = shape.match(entry)
        if match:
            distance = abs(int(match.group(1)) - frame)
            if best is None or distance < best[0]:
                best = (distance, os.path.join(folder, entry))
    return best[1] if best else None


# --- The matte list ---

RAW = re.compile(r"^<\s*([^<>]+?)\s*>$")


def parse_list(text: str) -> list[str]:
    """The artist's matte list: names or patterns separated by commas or new lines; a name holding a comma in
    double quotes; ``-pattern`` leaves out what ``pattern`` matches; ``<1.5e-12>`` is an ID by its value (Nuke's way
    of writing an ID without a name)."""
    entries = []
    for line in text.splitlines():
        for row in csv.reader([line], skipinitialspace=True):
            for cell in row:
                cell = cell.strip()
                if cell:
                    entries.append(cell)
    return entries


def format_list(entries: Iterable[str]) -> str:
    """One entry a line (quoted when it holds a comma or a quote)."""
    lines = []
    for entry in entries:
        if any(c in entry for c in ',"') or entry != entry.strip():
            entry = '"' + entry.replace('"', '""') + '"'
        lines.append(entry)
    return "\n".join(lines)


def raw_entry(bits: int) -> str:
    return f"<{bits_to_float(bits)!r}>"


def is_pattern(entry: str) -> bool:
    return any(c in entry for c in "*?[")


class Selection(NamedTuple):
    ids: frozenset[int]  # the IDs' bits
    names: tuple[str, ...]  # the names they stand for (manifest names, hashed names, raw IDs)
    unmatched: tuple[str, ...]  # patterns that matched nothing, raw entries that aren't numbers


def select(entries: Iterable[str], manifest: dict[str, int]) -> Selection:
    """The IDs the matte list stands for. A plain name not in the manifest is hashed (so a list keeps working on
    frames written without a manifest); a pattern needs the manifest."""
    chosen: dict[int, str] = {}
    unmatched = []
    excluded: set[int] = set()
    for entry in entries:
        leave_out = entry.startswith("-") and len(entry) > 1
        body = entry[1:].strip() if leave_out else entry
        found: dict[int, str] = {}
        raw = RAW.match(body)
        if raw:
            try:
                value = float(raw.group(1))
                found[float_to_bits(value)] = body
            except (ValueError, OverflowError):
                pass
        elif is_pattern(body):
            for name, bits in manifest.items():
                if fnmatch.fnmatchcase(name, body):
                    found[bits] = name
        elif body in manifest:
            found[manifest[body]] = body
        else:
            found[name_bits(body)] = body
        if not found:
            unmatched.append(entry)
        if leave_out:
            excluded.update(found)
        else:
            for bits, name in found.items():
                chosen.setdefault(bits, name)
    ids = {b for b in chosen if b not in excluded and (b & 0x7FFFFFFF) != 0}  # ID 0 (an empty rank) never counts
    return Selection(frozenset(ids), tuple(chosen[b] for b in sorted(ids)), tuple(unmatched))


# --- The expressions (CImg's math, evaluated in double precision by Natron's CImgExpression) ---


def _literal(value: float) -> str:
    text = repr(value)  # the shortest decimal that reads back to the same double, so the same float32
    return f"({text})" if text.startswith("-") else text


def membership(ids: Iterable[int]) -> str:
    """A CImg macro ``m(x)``: 1 when ``x`` is one of ``ids``, else 0. Sorted IDs searched as a tree of ``?:`` (CImg
    evaluates one branch only), so a pixel costs about log2(n) comparisons however long the list."""
    values = sorted({bits_to_float(b) for b in ids})

    def tree(part: list[float]) -> str:
        if len(part) <= 4:
            return "(" + "||".join(f"x=={_literal(v)}" for v in part) + ")"
        middle = len(part) // 2
        return f"(x<{_literal(part[middle])}?{tree(part[:middle])}:{tree(part[middle:])})"

    return "m(x)=" + (tree(values) if values else "0") + ";"


def rank_pair_expression(ids: Iterable[int]) -> str:
    """For one ``<name>NN`` layer in RGBA: the coverage of both its ranks whose ID is listed."""
    ids = list(ids)
    if not ids:
        return "0"
    return membership(ids) + "m(R)*G+m(B)*A"


# The preview: each pixel's first-rank ID drawn as a colour that holds the ID exactly, so a colour picked in the viewer
# gives the ID back. The ID's 23 mantissa bits go in red (the low 11) and green (the high 12), its sign and exponent
# (9 bits, ``code``) in blue, each with 12 check bits worked out from the others, so a blend of two colours (an
# edge averaged by a zoomed-out viewer, a box pick) is told from a real one. The checks aren't linear (an average of
# two right colours would pass linear ones about once in 300):
#   red   = (low * 4096 + (high * high * 3 + code * (high + 7) + 11) % 4096) / 2**23
#   green = (high * 4096 + (low * low * 5 + code * code * 3 + low * 13 + 29) % 4096) / 2**24
#   blue  = 0.5 + (code * 4096 + (low * high + low * 3 + high * 11 + 7) % 4096) / 2**22
# (every product stays far below 2**53, so CImg's doubles compute them exactly).
# Every such value is exact in a 32-bit float. Unlisted objects are drawn at a quarter of that (exact too: a power of
# two), listed ones at full strength; ID 0 (no object) is black.
PREVIEW_DIM = 0.25


def preview_expression(ids: Iterable[int]) -> str:
    # Macros only, no variables: an assignment (``a=R;a``) crashes the CImgExpression of Natron 2026.10.02 (checked);
    # a macro is written out where it's used, so it costs only a longer expression. Macro names have two letters
    # or more: CImg keeps most single letters (e, w, h, s, i...) for itself.
    ids = list(ids)
    listed = membership(ids) if ids else "m(x)=0;"
    return (listed + "e0(v)=floor(log2(abs(v)));ex(v)=e0(v)+(abs(v)/2^e0(v)>=2)-(abs(v)/2^e0(v)<1);"
            "mt(v)=round((abs(v)/2^ex(v)-1)*8388608);lo(v)=mt(v)%2048;hi(v)=floor(mt(v)/2048);"
            "cd(v)=ex(v)+127+(v<0)*256;"
            "cr(v)=(lo(v)*4096+(hi(v)*hi(v)*3+cd(v)*(hi(v)+7)+11)%4096)/8388608;"
            "cg(v)=(hi(v)*4096+(lo(v)*lo(v)*5+cd(v)*cd(v)*3+lo(v)*13+29)%4096)/16777216;"
            "cb(v)=0.5+(cd(v)*4096+(lo(v)*hi(v)+lo(v)*3+hi(v)*11+7)%4096)/4194304;"
            "co(v)=c==0?cr(v):(c==1?cg(v):(c==2?cb(v):1));"
            f"R==0?0:(m(R)?co(R):co(R)*{PREVIEW_DIM!r})")


def _checks(low: int, high: int, code: int) -> tuple[int, int, int]:
    return ((high * high * 3 + code * (high + 7) + 11) % 4096,
            (low * low * 5 + code * code * 3 + low * 13 + 29) % 4096, (low * high + low * 3 + high * 11 + 7) % 4096)


def preview_colour(bits: int, listed: bool = True) -> tuple[float, float, float]:
    """The colour the preview draws for an ID (what the expression above computes), as 32-bit floats."""
    if bits & 0x7FFFFFFF == 0:
        return (0.0, 0.0, 0.0)
    mantissa = bits & 0x7FFFFF
    low, high = mantissa % 2048, mantissa // 2048
    code = ((bits >> 23) & 0xFF) + (256 if bits >> 31 else 0)
    c1, c2, c3 = _checks(low, high, code)
    colour = ((low * 4096 + c1) / 2**23, (high * 4096 + c2) / 2**24, 0.5 + (code * 4096 + c3) / 2**22)
    scale = 1.0 if listed else PREVIEW_DIM
    return (colour[0] * scale, colour[1] * scale, colour[2] * scale)


def decode_preview(r: float, g: float, b: float) -> int | None:
    """The ID's bits under a colour picked from the preview, or None (a blend of several objects at an edge, a
    zoomed-out viewer averaging pixels, the picture not being the preview, the background)."""
    for scale in (1.0, 1.0 / PREVIEW_DIM):
        red, green, blue = r * scale * 2**23, g * scale * 2**24, (b * scale - 0.5) * 2**22
        if not all(v == int(v) and v >= 0 for v in (red, green, blue)):
            continue
        red, green, blue = int(red), int(green), int(blue)
        low, high, code = red >> 12, green >> 12, blue >> 12
        if low >= 2048 or high >= 4096 or code >= 512 or (code & 0xFF) in (0, 0xFF):
            continue
        if _checks(low, high, code) != (red & 4095, green & 4095, blue & 4095):
            continue
        return ((code >> 8) << 31) | ((code & 0xFF) << 23) | (high << 11) | low
    return None
