# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Made-up Cryptomatte renders whose every coverage is known (standard library only), and the truth: the matte a
list of IDs must give, summed straight from the file's ranks.

- ``objects.exr``: a picture in RGBA, ``CryptoObject00..02`` (6 ranks) and ``CryptoMaterial00..01`` (4 ranks), both
  manifests in the header. Pixels hold 0 to 6 objects with random coverages, an ID of 0 with coverage (an empty
  rank must never count), an object only at the last rank, names with a comma and with paths.
- ``assets_lower.exr``: Blender's way, ``ViewLayer.CryptoAsset00..02`` with lower-case ``r g b a``, its manifest in
  a sidecar file named by ``manif_file``.
- ``no_manifest.exr``: the objects without any manifest (what the farm's split of a Blender 5 frame gives), and
  ``objects_names.json``, a sidecar manifest for it.
- ``crowd.exr``: 2,000 names at Karma's 480 x 270, for the speed of a long list.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import random
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "ext" / "python"))

import exr_io  # noqa: E402
from natron_layer import cryptomatte_data as data  # noqa: E402  (the hash only, checked against real manifests)

OBJECTS = ["/root/chars/hero", "/root/chars/hero_cape", "/root/set/tree_01", "/root/set/tree_02", "/root/set/tree_10",
           "/root/set/rock", "/root/set/ground", "/root/fx/dust", "car, red", "lamp", "sky"]
MATERIALS = ["mat_metal", "mat_wood", "mat_glass", "mat_skin", "mat_leaf"]
ASSETS = ["hero_asset", "tree_asset", "rock_asset", "ground_asset"]


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def bits(name: str) -> int:
    return data.name_bits(name)


def as_float(b: int) -> float:
    return struct.unpack("<f", struct.pack("<I", b))[0]


def _pixel(rng: random.Random, names: list[str], ranks: int, x: int, y: int) -> list[tuple[float, float]]:
    """``ranks`` (ID, coverage) pairs, highest coverage first, padded with (0, 0)."""
    if y == 0:  # an empty rank with coverage: ID 0 must never match
        found = [(0.0, f32(0.25 + 0.5 * rng.random()))]
    elif x == 0 and len(names) >= ranks:  # the first name only at the last rank
        others = [n for n in names[1:]][: ranks - 1]
        found = [(as_float(bits(n)), f32(0.3 - 0.04 * i)) for i, n in enumerate(others)]
        found.append((as_float(bits(names[0])), f32(0.01)))
    else:
        count = rng.choice([0, 1, 1, 1, 2, 2, 3, 4, 5, 6, 8])  # 8: more objects than ranks (the rest is lost)
        chosen = rng.sample(names, min(count, len(names)))
        weights = [rng.random() + 0.05 for _ in chosen]
        total = sum(weights) / (0.4 + 0.6 * rng.random())
        found = sorted(((as_float(bits(n)), f32(w / total)) for n, w in zip(chosen, weights)), key=lambda p: -p[1])
    found = found[:ranks]
    return found + [(0.0, 0.0)] * (ranks - len(found))


def _layers(base: str, width: int, height: int, names: list[str], ranks: int, seed: int,
            lower: bool = False) -> dict[str, list[float]]:
    rng = random.Random(seed)
    letters = "rgba" if lower else "RGBA"
    channels = {f"{base}{k:02d}.{c}": [0.0] * (width * height) for k in range(ranks // 2) for c in letters}
    for y in range(height):
        for x in range(width):
            i = y * width + x
            for rank, (ident, cover) in enumerate(_pixel(rng, names, ranks, x, y)):
                layer = f"{base}{rank // 2:02d}"
                channels[f"{layer}.{letters[0 if rank % 2 == 0 else 2]}"][i] = ident
                channels[f"{layer}.{letters[1 if rank % 2 == 0 else 3]}"][i] = cover
    return channels


def _picture(width: int, height: int, other: bool = False) -> dict[str, list[float]]:
    """A gradient in RGBA (``other``: another one, to tell an Image input from the Source)."""
    across = [f32((i % width) / width) for i in range(width * height)]
    down = [f32((i // width) / height) for i in range(width * height)]
    return {"R": down if other else across, "G": across if other else down,
            "B": [0.25 if other else 0.5] * (width * height), "A": [1.0] * (width * height)}


def _manifest_attributes(name: str, names: list[str], sidecar: str | None = None) -> dict[str, str]:
    key = hashlib.md5(name.encode()).hexdigest()[:7]
    attributes = {f"cryptomatte/{key}/name": name, f"cryptomatte/{key}/hash": "MurmurHash3_32",
                  f"cryptomatte/{key}/conversion": "uint32_to_float32"}
    if sidecar:
        attributes[f"cryptomatte/{key}/manif_file"] = sidecar
    else:
        attributes[f"cryptomatte/{key}/manifest"] = json.dumps({n: f"{bits(n):08x}" for n in names})
    return attributes


def make(folder: Path) -> dict[str, str]:
    folder.mkdir(parents=True, exist_ok=True)
    w, h = 64, 32
    made = {}
    channels = {**_picture(w, h), **_layers("CryptoObject", w, h, OBJECTS, 6, 1),
                **_layers("CryptoMaterial", w, h, MATERIALS, 4, 2)}
    strings = {**_manifest_attributes("CryptoObject", OBJECTS), **_manifest_attributes("CryptoMaterial", MATERIALS)}
    made["objects"] = str(folder / "objects.exr")
    exr_io.write(made["objects"], w, h, channels, strings)
    made["no_manifest"] = str(folder / "no_manifest.exr")
    exr_io.write(made["no_manifest"], w, h, channels)
    made["names_json"] = str(folder / "objects_names.json")
    Path(made["names_json"]).write_text(json.dumps({n: f"{bits(n):08x}" for n in OBJECTS}), encoding="utf-8")
    lower = {**_picture(w, h, other=True),
             **_layers("ViewLayer.CryptoAsset", w, h, ASSETS, 6, 3, lower=True)}
    made["assets_lower"] = str(folder / "assets_lower.exr")
    exr_io.write(made["assets_lower"], w, h, lower, _manifest_attributes("ViewLayer.CryptoAsset", ASSETS,
                                                                         "assets_lower.json"))
    (folder / "assets_lower.json").write_text(json.dumps({n: f"{bits(n):08x}" for n in ASSETS}), encoding="utf-8")
    crowd = [f"/root/crowd/agent_{i:04d}" for i in range(2000)]
    cw, ch = 480, 270
    made["crowd"] = str(folder / "crowd.exr")
    exr_io.write(made["crowd"], cw, ch, {**_picture(cw, ch), **_layers("CryptoObject", cw, ch, crowd, 6, 4)},
                 _manifest_attributes("CryptoObject", crowd))
    return made


# --- The truth ---


def _json_manifest(path: str) -> dict[str, int]:
    return {k: int(v, 16) for k, v in json.loads(Path(path).read_text(encoding="utf-8")).items()}


def manifest_of(image: exr_io.Image, layer: str, sidecar: str | None = None, folder: str = "") -> dict[str, int]:
    """The names of ``layer``: from ``sidecar`` (a .json, or another EXR) when given, else the header (inline, or
    the ``manif_file`` in ``folder``)."""
    if sidecar:
        if not sidecar.lower().endswith(".exr"):
            return _json_manifest(sidecar)
        image, folder = exr_io.read(sidecar), os.path.dirname(sidecar)
    strings = image.strings()
    for key, value in strings.items():
        if key.endswith("/name") and value == layer:
            base = key.rsplit("/", 1)[0]
            if base + "/manifest" in strings:
                return {k: int(v, 16) for k, v in json.loads(strings[base + "/manifest"]).items()}
            if base + "/manif_file" in strings:
                return _json_manifest(os.path.join(folder, strings[base + "/manif_file"]))
    return {}


def expected_ids(entries: list[str], manifest: dict[str, int]) -> set[int]:
    """The test's own reading of a matte list (names, wildcards, -leave out, <raw ID>)."""
    keep: set[int] = set()
    drop: set[int] = set()
    for entry in entries:
        target = drop if entry.startswith("-") else keep
        body = entry[1:] if entry.startswith("-") else entry
        if body.startswith("<") and body.endswith(">"):
            target.add(struct.unpack("<I", struct.pack("<f", float(body[1:-1])))[0])
        elif any(c in body for c in "*?["):
            target.update(b for n, b in manifest.items() if fnmatch.fnmatchcase(n, body))
        else:
            target.add(manifest.get(body, bits(body)))
    return {b for b in keep - drop if b & 0x7FFFFFFF}


def rank_layers(image: exr_io.Image, layer: str) -> list[tuple[list[float], list[float], list[float], list[float]]]:
    found = []
    k = 0
    while True:
        names = [f"{layer}{k:02d}.{c}" for c in "RGBA"]
        lower = [f"{layer}{k:02d}.{c}" for c in "rgba"]
        values = [image.get(a, b) for a, b in zip(names, lower)]
        if any(v is None for v in values):
            return found
        found.append(tuple(values))  # type: ignore[arg-type]
        k += 1


def truth(image: exr_io.Image, layer: str, ids: set[int]) -> list[float]:
    """The matte: every rank's coverage where its ID is listed, summed (double precision)."""
    floats = {as_float(b) for b in ids}
    out = [0.0] * (image.width * image.height)
    for r, g, b, a in rank_layers(image, layer):
        for i in range(len(out)):
            if r[i] in floats:
                out[i] += g[i]
            if b[i] in floats:
                out[i] += a[i]
    return out


def first_rank_pixel(image: exr_io.Image, layer: str, ident: int) -> tuple[int, int] | None:
    """A pixel (x, file row) whose first rank is ``ident`` with its four neighbours the same (a pick inside it)."""
    r = rank_layers(image, layer)[0][0]
    want = as_float(ident)
    w, h = image.width, image.height
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if all(r[(y + dy) * w + x + dx] == want for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))):
                return x, y
    for i, v in enumerate(r):
        if v == want:
            return i % w, i // w
    return None


if __name__ == "__main__":
    print(make(Path(sys.argv[1])))
