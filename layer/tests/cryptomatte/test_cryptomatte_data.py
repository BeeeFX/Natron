# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The Cryptomatte node's arithmetic, without Natron: ``python -m unittest`` in this folder (run_cryptomatte.py runs
it first)."""

from __future__ import annotations

import os
import random
import struct
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "ext" / "python"))

import exr_io  # noqa: E402
from natron_layer import cryptomatte_data as data  # noqa: E402

# IDs as the renderers wrote them in their manifests (a Blender 5.1 Cycles frame and a Houdini 21 Karma one).
KNOWN = {"cube": 0xD9682F08, "ball": 0x645D3BC4, "ground": 0xC5B51EDE, "Sun": 0xEE8D1AE3,
         "/root/banana_model/asset/banana/banana": 0xC8220DAD,
         "/assets/monkey_model/monkey_model/monkey_0/monkey": 0x5EDECD4F}


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


class Ids(unittest.TestCase):
    def test_names_hash_as_the_renderers_do(self) -> None:
        for name, bits in KNOWN.items():
            self.assertEqual(data.name_bits(name), bits, name)

    def test_murmur3_reference_values(self) -> None:
        # MurmurHash3_x86_32's commonly published check values.
        self.assertEqual(data.murmur3_32(b""), 0)
        self.assertEqual(data.murmur3_32(b"", 1), 0x514E28B7)
        self.assertEqual(data.murmur3_32(b"", 0xFFFFFFFF), 0x81F16F39)
        self.assertEqual(data.murmur3_32(b"\0\0\0\0"), 0x2362F9DE)
        self.assertEqual(data.murmur3_32(b"aaaa", 0x9747B28C), 0x5A97808A)
        self.assertEqual(data.murmur3_32(b"Hello, world!", 0x9747B28C), 0x24884CBA)

    def test_ids_are_never_denormal_infinite_or_nan(self) -> None:
        rng = random.Random(5)
        for _ in range(5000):
            name = "".join(rng.choice("abcxyz/_0123") for _ in range(rng.randint(1, 20)))
            exponent = (data.name_bits(name) >> 23) & 0xFF
            self.assertNotIn(exponent, (0, 0xFF))


class Lists(unittest.TestCase):
    manifest = {"cube": 1, "ball": 2, "ground": 3, "/set/tree_01": 0x40000000, "/set/tree_02": 0x40000001,
                "car, red": 0x40000002}

    def test_parse_and_format(self) -> None:
        text = 'cube, "car, red"\n\n  -ground  \n<1.5>, /set/*'
        entries = data.parse_list(text)
        self.assertEqual(entries, ["cube", "car, red", "-ground", "<1.5>", "/set/*"])
        self.assertEqual(data.parse_list(data.format_list(entries)), entries)

    def test_select(self) -> None:
        chosen = data.select(["*", "-ground"], self.manifest)
        self.assertEqual(chosen.ids, frozenset({1, 2, 0x40000000, 0x40000001, 0x40000002}))
        self.assertEqual(data.select(["/set/tree_0?"], self.manifest).ids, frozenset({0x40000000, 0x40000001}))
        self.assertEqual(data.select(["<1.5>"], {}).ids, frozenset({data.float_to_bits(1.5)}))
        self.assertEqual(data.select(["cube"], {}).ids, frozenset({KNOWN["cube"]}))  # hashed without a manifest
        missing = data.select(["nothing*", "<abc>"], self.manifest)
        self.assertEqual((missing.ids, missing.unmatched), (frozenset(), ("nothing*", "<abc>")))
        self.assertEqual(data.select(["<0.0>", "<-0.0>"], {}).ids, frozenset())  # an empty rank never counts

    def test_membership_expression_shape(self) -> None:
        ids = list(range(0x40000000, 0x40000000 + 100))
        text = data.membership(ids)
        self.assertTrue(text.startswith("m(x)=(x<") and text.endswith(";"))
        for bits in ids:
            self.assertIn(repr(data.bits_to_float(bits)), text)
        self.assertEqual(data.rank_pair_expression([]), "0")
        self.assertIn("(-", data.membership([0xC0000000]))  # negative IDs in brackets

    def test_membership_tree_finds_exactly_the_listed_ids(self) -> None:
        # The tree evaluated here the way CImg reads it (``?:`` and ``||``), on listed and unlisted IDs.
        ids = {data.name_bits(f"agent_{i}") for i in range(300)}
        python = _ternaries(data.membership(ids)[len("m(x)="):-1].replace("||", " or "))
        for bits in list(ids)[:100] + [data.name_bits(f"other_{i}") for i in range(100)]:
            x = data.bits_to_float(bits)
            self.assertEqual(bool(eval(python, {"x": x})), bits in ids)  # noqa: S307  (our own text)


def _ternaries(text: str) -> str:
    """``(c?a:b)`` -> ``((a) if (c) else (b))``, innermost first (the tree's conditions hold no ``?``)."""
    while "?" in text:
        q = text.rindex("?")
        start = text.rindex("(x<", 0, q)
        depth, i = 0, q + 1
        while not (text[i] == ":" and depth == 0):
            depth += {"(": 1, ")": -1}.get(text[i], 0)
            i += 1
        colon = i
        depth, i = 0, colon + 1
        while not (text[i] == ")" and depth == 0):
            depth += {"(": 1, ")": -1}.get(text[i], 0)
            i += 1
        condition, then, other = text[start + 1:q], text[q + 1:colon], text[colon + 1:i]
        text = text[:start] + f"(({then}) if ({condition}) else ({other}))" + text[i + 1:]
    return text


class Preview(unittest.TestCase):
    def test_colours_hold_the_id_exactly(self) -> None:
        rng = random.Random(3)
        for _ in range(20000):
            bits = data.name_bits(str(rng.random()))
            for listed in (True, False):
                colour = data.preview_colour(bits, listed)
                self.assertEqual(tuple(f32(c) for c in colour), colour)
                self.assertEqual(data.decode_preview(*colour), bits)

    def test_blends_and_backgrounds_give_nothing(self) -> None:
        rng = random.Random(4)
        passed = 0
        for _ in range(20000):  # two objects averaged (an edge seen zoomed out), or four
            ids = [data.name_bits(str(rng.random())) for _ in range(4)]
            colours = [data.preview_colour(i, rng.random() < 0.5) for i in ids]
            two = tuple(f32((a + b) / 2) for a, b in zip(colours[0], colours[1]))
            four = tuple(f32(sum(c[k] for c in colours) / 4) for k in range(3))
            passed += data.decode_preview(*two) is not None
            passed += data.decode_preview(*four) is not None
        self.assertEqual(passed, 0)
        self.assertIsNone(data.decode_preview(0.0, 0.0, 0.0))
        self.assertIsNone(data.decode_preview(0.18, 0.18, 0.18))


class Header(unittest.TestCase):
    def test_manifest_inline_and_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            inline = os.path.join(folder, "a.exr")
            exr_io.write(inline, 2, 1, {"CryptoObject00.R": [0.0, 0.0]},
                         {"cryptomatte/abc1234/name": "CryptoObject",
                          "cryptomatte/abc1234/manifest": '{"cube":"d9682f08"}', "unrelated": "x" * 70000})
            found = data.cryptomattes_in(inline)
            self.assertEqual([(c.name, c.manifest) for c in found], [("CryptoObject", {"cube": KNOWN["cube"]})])
            sidecar = os.path.join(folder, "b.exr")
            exr_io.write(sidecar, 2, 1, {"R": [0.0, 0.0]}, {"cryptomatte/def5678/name": "ViewLayer.CryptoAsset",
                                                             "cryptomatte/def5678/manif_file": "b.json"})
            Path(folder, "b.json").write_text('{"hero": "0000abcd"}', encoding="utf-8")
            self.assertEqual(data.cryptomattes_in(sidecar)[0].manifest, {"hero": 0xABCD})
            self.assertEqual(data.read_manifest_file(os.path.join(folder, "b.json")), {"hero": 0xABCD})

    def test_frame_files(self) -> None:
        self.assertEqual(data.frame_file("c_####.exr", 1001), "c_1001.exr")
        self.assertEqual(data.frame_file("c_%04d.exr", 7), "c_0007.exr")
        with tempfile.TemporaryDirectory() as folder:
            for frame in (1001, 1005):
                Path(folder, f"c_{frame}.exr").write_bytes(b"")
            pattern = os.path.join(folder, "c_####.exr")
            self.assertEqual(os.path.basename(data.nearest_frame_file(pattern, 1004) or ""), "c_1005.exr")
            self.assertEqual(os.path.basename(data.nearest_frame_file(pattern, 1) or ""), "c_1001.exr")


if __name__ == "__main__":
    unittest.main()
