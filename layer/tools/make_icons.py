# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""Draw the layer's own interface icons: flat, light grey line pictures in the spirit of Nuke's interface (our own
drawings, nothing traced or copied), written as PNG at 1x and 2x into ``ext/icons/`` with the table the skin reads
(``ext/icons/pixmaps.toml``):

    python layer/tools/make_icons.py [--sheet <png>]

Needs Python 3.10+ with Pillow (the build itself has no Qt SVG plug-in, so the icons are drawn here once and
committed as PNG). Each icon is drawn on a 16 x 16 grid, eight times larger than wanted, then reduced, so its lines
stay crisp at 11, 18 and 24 pixels. Each picture is named after the file Natron loads for it (``play_enabled.png``),
which ``natron_pixmaps.py`` reads from the fork's source with its number. ``--sheet`` also writes a contact sheet of
every icon, large, on the interface's grey, to look at them side by side.

The second wave (the Merge operations, roto, paint and tracker tools, the curve editor's interpolation, the File
menu as an icon theme) is in ``make_icons_wave2.py``.

Colours: grey for a button at rest, a dimmer grey for "off" or unavailable, Nuke-like orange for "on" (a toggled
viewer option, the playing direction). Two-state buttons get both pictures, so Natron's own switching keeps working.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

LAYER = Path(__file__).resolve().parents[1]
REPO = LAYER.parent
OUT = LAYER / "ext" / "icons"
FONT = LAYER / "ext" / "fonts" / "DejaVuSans.ttf"
SS = 8  # supersampling

FG = (208, 208, 208, 255)
DIM = (128, 128, 128, 255)
ACC = (247, 148, 32, 255)
RED = (214, 72, 64, 255)
GREEN = (96, 186, 96, 255)
BLUE = (88, 140, 220, 255)


class Pen:
    """Drawing on a 16-unit grid; ``w`` is the line width in output pixels at 1x."""

    def __init__(self, size: int, scale: int) -> None:
        self.px = size * scale * SS
        self.u = self.px / 16.0
        self.image = Image.new("RGBA", (self.px, self.px), (0, 0, 0, 0))
        self.draw = ImageDraw.Draw(self.image)
        self.w = max(1.0, size / 12.0) * scale * SS
        self.size = size
        self.scale = scale

    def p(self, x: float, y: float) -> tuple[float, float]:
        return (x * self.u, y * self.u)

    def width(self, factor: float = 1.0) -> float:
        return self.w * factor

    def _dot(self, x: float, y: float, r: float, colour: tuple) -> None:
        cx, cy = x, y
        self.draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=colour)

    def line(self, points: list[tuple[float, float]], colour: tuple = FG, factor: float = 1.0,
             closed: bool = False) -> None:
        pts = [self.p(*q) for q in points]
        if closed:
            pts.append(pts[0])
        w = self.width(factor)
        self.draw.line(pts, fill=colour, width=int(round(w)), joint="curve")
        for q in pts:
            self._dot(q[0], q[1], w / 2.0, colour)

    def poly(self, points: list[tuple[float, float]], colour: tuple = FG, outline: bool = False,
             factor: float = 1.0) -> None:
        pts = [self.p(*q) for q in points]
        if outline:
            self.line(points, colour, factor, closed=True)
        else:
            self.draw.polygon(pts, fill=colour)
            # soften the corners a little, as the line icons are
            self.draw.line(pts + [pts[0]], fill=colour, width=int(round(self.width(0.5))), joint="curve")

    def rect(self, x: float, y: float, w: float, h: float, colour: tuple = FG, fill: bool = False,
             factor: float = 1.0, radius: float = 0.0) -> None:
        box = (*self.p(x, y), *self.p(x + w, y + h))
        if fill:
            self.draw.rounded_rectangle(box, radius=radius * self.u, fill=colour)
        else:
            self.draw.rounded_rectangle(box, radius=radius * self.u, outline=colour,
                                        width=int(round(self.width(factor))))

    def circle(self, cx: float, cy: float, r: float, colour: tuple = FG, fill: bool = False,
               factor: float = 1.0) -> None:
        box = (*self.p(cx - r, cy - r), *self.p(cx + r, cy + r))
        if fill:
            self.draw.ellipse(box, fill=colour)
        else:
            self.draw.ellipse(box, outline=colour, width=int(round(self.width(factor))))

    def arc(self, cx: float, cy: float, r: float, start: float, end: float, colour: tuple = FG,
            factor: float = 1.0) -> None:
        """Degrees, clockwise from 3 o'clock (PIL's convention)."""
        box = (*self.p(cx - r, cy - r), *self.p(cx + r, cy + r))
        w = self.width(factor)
        self.draw.arc(box, start, end, fill=colour, width=int(round(w)))
        for angle in (start, end):
            a = math.radians(angle)
            self._dot(*self.p(cx + r * math.cos(a), cy + r * math.sin(a)), w / 2.0, colour)

    def arc_arrow(self, cx: float, cy: float, r: float, start: float, end: float, colour: tuple = FG,
                  head: float = 3.4, factor: float = 1.0) -> None:
        """An arc drawn from ``start`` to ``end`` (degrees, 0 = 3 o'clock, growing clockwise on screen; either
        direction) with a filled arrow head at ``end``, pointing the way the arc goes."""
        sign = 1 if end > start else -1
        trim = math.degrees(head * 0.6 / r) * sign
        stop = end - trim
        steps = max(8, int(abs(stop - start) / 6))
        points = []
        for k in range(steps + 1):
            a = math.radians(start + (stop - start) * k / steps)
            points.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        self.line(points, colour, factor)
        a = math.radians(end)
        tip = (cx + r * math.cos(a), cy + r * math.sin(a))
        self.head(tip[0], tip[1], end + 90 * sign, head, colour)

    def head(self, x: float, y: float, angle: float, length: float, colour: tuple = FG) -> None:
        """A filled arrow head with its tip at (x, y) pointing along ``angle`` (degrees, 0 = right, 90 = down)."""
        a = math.radians(angle)
        back = (x - length * math.cos(a), y - length * math.sin(a))
        n = (-math.sin(a), math.cos(a))
        half = length * 0.62
        self.poly([(x, y), (back[0] + n[0] * half, back[1] + n[1] * half),
                   (back[0] - n[0] * half, back[1] - n[1] * half)], colour)

    def pie(self, cx: float, cy: float, r: float, start: float, end: float, colour: tuple = FG) -> None:
        box = (*self.p(cx - r, cy - r), *self.p(cx + r, cy + r))
        self.draw.pieslice(box, start, end, fill=colour)

    def text(self, x: float, y: float, text: str, colour: tuple = FG, height: float = 10.0,
             bold: bool = False) -> None:
        """Text centred on (x, y), ``height`` in grid units."""
        font = ImageFont.truetype(str(FONT), int(height * self.u))
        box = self.draw.textbbox((0, 0), text, font=font, anchor="lt")
        tw, th = box[2] - box[0], box[3] - box[1]
        cx, cy = self.p(x, y)
        stroke = int(round(self.width(0.35))) if bold else 0
        self.draw.text((cx - tw / 2 - box[0], cy - th / 2 - box[1]), text, font=font, fill=colour,
                       stroke_width=stroke, stroke_fill=colour)

    def arrow_head(self, x: float, y: float, angle: float, length: float, colour: tuple = FG,
                   factor: float = 1.0) -> None:
        """An open arrow head (two strokes) pointing along ``angle`` (degrees, 0 = right, 90 = down)."""
        a = math.radians(angle)
        for side in (150, -150):
            b = a + math.radians(side)
            self.line([(x + length * math.cos(b), y + length * math.sin(b)), (x, y)], colour, factor)

    def done(self) -> Image.Image:
        return self.image.resize((self.size * self.scale, self.size * self.scale), Image.Resampling.LANCZOS)


Draw = Callable[[Pen, tuple], None]
ICONS: dict[str, tuple[int, Draw, tuple]] = {}  # file name -> (size, drawing, colour)


def icon(names: str | list[str], size: int = 18, colour: tuple = FG) -> Callable[[Draw], Draw]:
    def register(function: Draw) -> Draw:
        for name in [names] if isinstance(names, str) else names:
            ICONS[name] = (size, function, colour)
        return function

    return register


def pair(on: str, off: str, size: int = 18, on_colour: tuple = ACC, off_colour: tuple = FG) -> Callable[[Draw], Draw]:
    """A two-state button: the "on" picture in orange, the "off" one in grey."""

    def register(function: Draw) -> Draw:
        ICONS[on] = (size, function, on_colour)
        ICONS[off] = (size, function, off_colour)
        return function

    return register


# ---------------------------------------------------------------------------------------------------------------
# Playback bar
# ---------------------------------------------------------------------------------------------------------------

def tri_right(p: Pen, x: float, c: tuple, h: float = 9.0, w: float = 7.5) -> None:
    p.poly([(x, 8 - h / 2), (x + w, 8), (x, 8 + h / 2)], c)


def tri_left(p: Pen, x: float, c: tuple, h: float = 9.0, w: float = 7.5) -> None:
    p.poly([(x, 8 - h / 2), (x - w, 8), (x, 8 + h / 2)], c)


@icon("firstFrame.png")
def _first(p: Pen, c: tuple) -> None:
    p.line([(3, 3.5), (3, 12.5)], c)
    tri_left(p, 9, c, 8, 5.5)
    tri_left(p, 14, c, 8, 5.5)


@icon("lastFrame.png")
def _last(p: Pen, c: tuple) -> None:
    tri_right(p, 2, c, 8, 5.5)
    tri_right(p, 7, c, 8, 5.5)
    p.line([(13, 3.5), (13, 12.5)], c)


@icon("back1.png")
def _previous(p: Pen, c: tuple) -> None:
    tri_left(p, 10, c, 8, 6)
    p.line([(12, 4), (12, 12)], c)


@icon("forward1.png")
def _next(p: Pen, c: tuple) -> None:
    p.line([(4, 4), (4, 12)], c)
    tri_right(p, 6, c, 8, 6)


def chevrons(p: Pen, c: tuple, direction: int) -> None:
    for x in (6.5, 11):
        tip = x - 3 if direction < 0 else x + 3
        base = x if direction < 0 else x - 0
        if direction < 0:
            p.line([(x, 4), (x - 3.5, 8), (x, 12)], c)
        else:
            p.line([(x - 2, 4), (x + 1.5, 8), (x - 2, 12)], c)
        del tip, base


@icon("previousIncr.png")
def _prev_incr(p: Pen, c: tuple) -> None:
    chevrons(p, c, -1)


@icon("nextIncr.png")
def _next_incr(p: Pen, c: tuple) -> None:
    chevrons(p, c, 1)


def diamond(p: Pen, cx: float, cy: float, r: float, c: tuple, fill: bool = True) -> None:
    points = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
    p.poly(points, c, outline=not fill)


@icon("prevKF.png")
def _prev_key(p: Pen, c: tuple) -> None:
    tri_left(p, 7.5, c, 7, 5)
    diamond(p, 11.5, 8, 3.2, c)


@icon("nextKF.png")
def _next_key(p: Pen, c: tuple) -> None:
    diamond(p, 4.5, 8, 3.2, c)
    tri_right(p, 8.5, c, 7, 5)


@pair("rewind_enabled.png", "rewind.png")
def _rewind(p: Pen, c: tuple) -> None:
    tri_left(p, 12, c, 10, 8)


@pair("play_enabled.png", "play.png")
def _play(p: Pen, c: tuple) -> None:
    tri_right(p, 4, c, 10, 8)


@pair("stopEnabled.png", "stopDisabled.png", on_colour=FG, off_colour=DIM)
def _stop(p: Pen, c: tuple) -> None:
    p.rect(4, 4, 8, 8, c, fill=True, radius=0.6)


@pair("pauseEnabled.png", "pauseDisabled.png")
def _pause(p: Pen, c: tuple) -> None:
    p.rect(4, 3.5, 2.6, 9, c, fill=True, radius=0.4)
    p.rect(9.4, 3.5, 2.6, 9, c, fill=True, radius=0.4)


@icon("loopmode.png")
def _loop(p: Pen, c: tuple) -> None:
    p.arc_arrow(8, 8, 5.2, 195, 345, c, 3.2)
    p.arc_arrow(8, 8, 5.2, 15, 165, c, 3.2)


@icon("bounce.png")
def _bounce(p: Pen, c: tuple) -> None:
    p.line([(2.5, 8), (13.5, 8)], c)
    p.arrow_head(2.5, 8, 180, 3, c)
    p.arrow_head(13.5, 8, 0, 3, c)


@icon("playOnce.png")
def _play_once(p: Pen, c: tuple) -> None:
    p.line([(2.5, 8), (11, 8)], c)
    p.arrow_head(11, 8, 0, 3, c)
    p.line([(13.5, 4), (13.5, 12)], c)


@icon("timelineIn.png")
def _in(p: Pen, c: tuple) -> None:
    p.line([(7, 3), (4, 3), (4, 13), (7, 13)], c)
    tri_right(p, 8, c, 6, 4.5)


@icon("timelineOut.png")
def _out(p: Pen, c: tuple) -> None:
    tri_left(p, 8, c, 6, 4.5)
    p.line([(9, 3), (12, 3), (12, 13), (9, 13)], c)


@pair("turbo_on.png", "turbo_off.png")
def _turbo(p: Pen, c: tuple) -> None:
    p.poly([(9.5, 1.8), (4, 9), (7.6, 9), (6.3, 14.2), (12, 6.8), (8.4, 6.8)], c)


# ---------------------------------------------------------------------------------------------------------------
# Pane and panel headers
# ---------------------------------------------------------------------------------------------------------------

@icon("maximize.png")
def _float(p: Pen, c: tuple) -> None:
    p.rect(3, 5, 8, 8, c)
    p.line([(6, 3), (13, 3), (13, 10)], c)


@icon("minimize.png")
def _minimise(p: Pen, c: tuple) -> None:
    p.line([(3.5, 11), (12.5, 11)], c, 1.2)


@icon(["close.png", "closePanel.png"])
def _close(p: Pen, c: tuple) -> None:
    p.line([(4, 4), (12, 12)], c, 1.1)
    p.line([(12, 4), (4, 12)], c, 1.1)


@icon("help.png")
def _help(p: Pen, c: tuple) -> None:
    p.text(8, 8.2, "?", c, 12.5, bold=True)


def eye(p: Pen, c: tuple) -> None:
    upper = [(1.5 + 13 * t / 12, 8 - 4.6 * math.sin(math.pi * t / 12)) for t in range(13)]
    lower = [(1.5 + 13 * t / 12, 8 + 4.6 * math.sin(math.pi * t / 12)) for t in range(13)]
    p.line(upper, c)
    p.line(lower, c)
    p.circle(8, 8, 2.2, c, fill=True)


@icon("unhide_unmodified.png")
def _unhide(p: Pen, c: tuple) -> None:
    eye(p, c)


@icon("hide_unmodified.png", colour=ACC)
def _hide(p: Pen, c: tuple) -> None:
    eye(p, c)
    p.line([(3, 14), (13, 2)], (40, 40, 40, 255), 2.4)
    p.line([(3, 14), (13, 2)], c)


@icon("groupbox_folded.png", size=11)
def _folded(p: Pen, c: tuple) -> None:
    p.poly([(5, 3), (11.5, 8), (5, 13)], c)


@icon("groupbox_unfolded.png", size=11)
def _unfolded(p: Pen, c: tuple) -> None:
    p.poly([(3, 5), (13, 5), (8, 11.5)], c)


def curved_arrow(p: Pen, c: tuple, mirrored: bool) -> None:
    if not mirrored:
        p.arc_arrow(8.5, 9.5, 4.8, 400, 190, c, 3.6)
    else:
        p.arc_arrow(7.5, 9.5, 4.8, 140, 350, c, 3.6)


@icon("undo.png")
def _undo(p: Pen, c: tuple) -> None:
    curved_arrow(p, c, False)


@icon("redo.png")
def _redo(p: Pen, c: tuple) -> None:
    curved_arrow(p, c, True)


@icon("undo_grayscale.png", colour=DIM)
def _undo_dim(p: Pen, c: tuple) -> None:
    curved_arrow(p, c, False)


@icon("redo_grayscale.png", colour=DIM)
def _redo_dim(p: Pen, c: tuple) -> None:
    curved_arrow(p, c, True)


@pair("restoreDefaultEnabled.png", "restoreDefaultDisabled.png", on_colour=FG, off_colour=DIM)
def _restore(p: Pen, c: tuple) -> None:
    p.arc_arrow(8, 8.5, 5.2, 590, 290, c, 3.4)
    p.circle(8, 8.5, 1.4, c, fill=True)


@icon("layout.png", size=11)
def _layout(p: Pen, c: tuple) -> None:
    for y in (4, 8, 12):
        p.line([(3, y), (13, y)], c, 1.2)


@icon("layout_anchor.png", size=11, colour=ACC)
def _layout_anchor(p: Pen, c: tuple) -> None:
    for y in (4, 8, 12):
        p.line([(3, y), (13, y)], c, 1.2)


@icon("splitHorizontally.png")
def _split_h(p: Pen, c: tuple) -> None:
    p.rect(2.5, 3, 11, 10, c)
    p.line([(2.5, 8), (13.5, 8)], c)


@icon("splitVertically.png")
def _split_v(p: Pen, c: tuple) -> None:
    p.rect(2.5, 3, 11, 10, c)
    p.line([(8, 3), (8, 13)], c)


@icon("enter_group.png")
def _enter_group(p: Pen, c: tuple) -> None:
    p.line([(7, 2.5), (13.5, 2.5), (13.5, 13.5), (7, 13.5)], c)
    p.line([(2, 8), (10, 8)], c)
    p.arrow_head(10, 8, 0, 3, c)


@icon("settings.png")
def _settings(p: Pen, c: tuple) -> None:
    for k in range(8):
        a = math.radians(k * 45)
        p.line([(8 + 4.4 * math.cos(a), 8 + 4.4 * math.sin(a)), (8 + 6.3 * math.cos(a), 8 + 6.3 * math.sin(a))], c, 1.5)
    p.circle(8, 8, 4.2, c)
    p.circle(8, 8, 1.4, c, fill=True)


@icon("colorwheel.png")
def _colorwheel(p: Pen, c: tuple) -> None:
    for start, colour in ((-90, RED), (30, GREEN), (150, BLUE)):
        p.pie(8, 8, 6, start, start + 120, colour)
    p.circle(8, 8, 2.6, (40, 40, 40, 255), fill=True)


@icon("colorwheel_overlay.png")
def _overlay(p: Pen, c: tuple) -> None:
    p.circle(8, 8, 5.5, c)
    p.line([(8, 0.8), (8, 4.5)], c)
    p.line([(8, 11.5), (8, 15.2)], c)
    p.line([(0.8, 8), (4.5, 8)], c)
    p.line([(11.5, 8), (15.2, 8)], c)


@icon("color_picker.png")
def _picker(p: Pen, c: tuple) -> None:
    p.line([(3, 13), (9.5, 6.5)], c, 1.2)
    p.line([(8, 5), (11, 8)], c, 1.4)
    p.poly([(9.8, 2.6), (13.4, 6.2), (12.0, 7.6), (8.4, 4.0)], c)


@icon("open-file.png")
def _open_file(p: Pen, c: tuple) -> None:
    p.line([(2, 4), (6, 4), (7.5, 5.5), (14, 5.5), (14, 13), (2, 13)], c, closed=True)
    p.line([(2, 7.5), (14, 7.5)], c)


# ---------------------------------------------------------------------------------------------------------------
# Viewer bars
# ---------------------------------------------------------------------------------------------------------------

@icon("centerViewer.png")
def _centre(p: Pen, c: tuple) -> None:
    for (x, y), (dx, dy) in (((2.5, 2.5), (1, 1)), ((13.5, 2.5), (-1, 1)), ((2.5, 13.5), (1, -1)),
                             ((13.5, 13.5), (-1, -1))):
        p.line([(x + 3.5 * dx, y), (x, y), (x, y + 3.5 * dy)], c)
    p.rect(5.5, 6, 5, 4, c)


@pair("cliptoprojectEnabled.png", "cliptoprojectDisabled.png")
def _clip(p: Pen, c: tuple) -> None:
    p.line([(4.5, 1.5), (4.5, 11.5), (14.5, 11.5)], c)
    p.line([(1.5, 4.5), (11.5, 4.5), (11.5, 14.5)], c)


@pair("fullFrameOn.png", "fullFrameOff.png")
def _full_frame(p: Pen, c: tuple) -> None:
    p.rect(2, 3, 12, 10, c)
    p.line([(4.5, 10.5), (11.5, 5.5)], c, 0.9)
    p.arrow_head(11.5, 5.5, -35, 2.4, c, 0.9)
    p.arrow_head(4.5, 10.5, 145, 2.4, c, 0.9)


@icon("refresh.png")
def _refresh(p: Pen, c: tuple) -> None:
    p.arc_arrow(8, 8, 5.2, 340, 620, c, 3.4)


@icon("refreshActive.png", colour=ACC)
def _refresh_active(p: Pen, c: tuple) -> None:
    _refresh(p, c)


@pair("viewer_roiEnabled.png", "viewer_roiDisabled.png")
def _roi(p: Pen, c: tuple) -> None:
    for x0, y0, x1, y1 in ((2, 3, 5, 3), (7, 3, 9, 3), (11, 3, 14, 3), (2, 13, 5, 13), (7, 13, 9, 13), (11, 13, 14, 13),
                           (2, 3, 2, 6), (2, 10, 2, 13), (14, 3, 14, 6), (14, 10, 14, 13)):
        p.line([(x0, y0), (x1, y1)], c)
    p.circle(8, 8, 1.4, c, fill=True)


@pair("renderScale_checked.png", "renderScale.png")
def _proxy(p: Pen, c: tuple) -> None:
    p.rect(2, 2, 12, 12, c)
    p.rect(2, 8, 6, 6, c, fill=True)


@pair("AutoContrastON.png", "AutoContrast.png")
def _autocontrast(p: Pen, c: tuple) -> None:
    p.circle(8, 8, 5.5, c)
    p.pie(8, 8, 5.5, 90, 270, c)


@pair("checkerboard_on.png", "checkerboard_off.png")
def _checker(p: Pen, c: tuple) -> None:
    p.rect(2.5, 2.5, 11, 11, c, factor=0.9)
    for i in range(3):
        for j in range(3):
            if (i + j) % 2 == 0:
                p.rect(2.5 + i * 11 / 3, 2.5 + j * 11 / 3, 11 / 3, 11 / 3, c, fill=True)


@pair("zebra_on.png", "zebra_off.png")
def _zebra(p: Pen, c: tuple) -> None:
    p.rect(2.5, 2.5, 11, 11, c, factor=0.9)
    for k in (-4, 0, 4):
        p.line([(2.5 + max(0, k), 13.5 - max(0, -k)), (13.5 - max(0, -k), 2.5 + max(0, k))], c, 0.9)


@pair("gammaON.png", "gammaOFF.png")
def _gamma(p: Pen, c: tuple) -> None:
    p.line([(2.5, 2.5), (2.5, 13.5), (13.5, 13.5)], c, 0.8)
    p.line([(2.5 + 11 * t / 10, 13.5 - 11 * (t / 10) ** 0.45) for t in range(11)], c)


@pair("expoON.png", "expoOFF.png")
def _gain(p: Pen, c: tuple) -> None:
    p.text(8, 8.3, "f", c, 13, bold=True)


@pair("updateViewerEnabled.png", "updateViewerDisabled.png", on_colour=FG, off_colour=ACC)
def _update_viewer(p: Pen, c: tuple) -> None:
    p.rect(4, 3.5, 2.6, 9, c, fill=True, radius=0.4)
    p.rect(9.4, 3.5, 2.6, 9, c, fill=True, radius=0.4)


@icon("locked.png", colour=ACC)
def _locked(p: Pen, c: tuple) -> None:
    p.arc(8, 6.5, 3, 180, 360, c)
    p.line([(5, 6.5), (5, 8)], c)
    p.line([(11, 6.5), (11, 8)], c)
    p.rect(3.5, 7.5, 9, 6.5, c, fill=True, radius=0.8)


@icon("unlocked.png")
def _unlocked(p: Pen, c: tuple) -> None:
    p.arc(10.5, 5, 3, 180, 360, c)
    p.line([(13.5, 5), (13.5, 6)], c)
    p.line([(7.5, 5), (7.5, 8)], c)
    p.rect(2.5, 7.5, 9, 6.5, c, fill=True, radius=0.8)


@pair("visible.png", "unvisible.png", on_colour=FG, off_colour=DIM)
def _visible(p: Pen, c: tuple) -> None:
    eye(p, c)


@pair("inverted.png", "uninverted.png", on_colour=ACC, off_colour=FG)
def _inverted(p: Pen, c: tuple) -> None:
    p.circle(8, 8, 5.5, c)
    p.pie(8, 8, 5.5, 270, 450, c)


@icon("layer.png")
def _layer(p: Pen, c: tuple) -> None:
    p.poly([(8, 2.5), (14, 5.5), (8, 8.5), (2, 5.5)], c, outline=True)
    p.line([(2, 8.5), (8, 11.5), (14, 8.5)], c)
    p.line([(2, 11.2), (8, 14.2), (14, 11.2)], c)


@icon("addKF.png")
def _add_key(p: Pen, c: tuple) -> None:
    diamond(p, 7, 9, 4.5, c, fill=False)
    p.line([(12.5, 1.5), (12.5, 6.5)], c)
    p.line([(10, 4), (15, 4)], c)


@icon("removeKF.png")
def _remove_key(p: Pen, c: tuple) -> None:
    diamond(p, 7, 9, 4.5, c, fill=False)
    p.line([(10, 4), (15, 4)], c)


@icon("clearAnimation.png")
def _clear_anim(p: Pen, c: tuple) -> None:
    diamond(p, 8, 8, 4.5, c, fill=False)
    p.line([(3, 13), (13, 3)], c)


@icon("clearAnimationBw.png")
def _clear_anim_bw(p: Pen, c: tuple) -> None:
    diamond(p, 10, 8, 4, c, fill=False)
    p.line([(1.5, 8), (5, 8)], c)


@icon("clearAnimationFw.png")
def _clear_anim_fw(p: Pen, c: tuple) -> None:
    diamond(p, 6, 8, 4, c, fill=False)
    p.line([(11, 8), (14.5, 8)], c)


# ---------------------------------------------------------------------------------------------------------------
# The left toolbar's node menus (24 px)
# ---------------------------------------------------------------------------------------------------------------

T = 20  # drawn for 20 pixels; the skin sets the toolbar's buttons to that size


@icon("GroupingIcons/Set3/image_grouping_3.png", size=T)
def _image(p: Pen, c: tuple) -> None:
    p.rect(2, 3, 12, 10, c, radius=0.6)
    p.line([(3, 12), (6.5, 7.5), (9, 10), (10.5, 8.5), (13, 12)], c)
    p.circle(10.5, 5.8, 1.1, c, fill=True)


@icon("GroupingIcons/Set3/paint_grouping_3.png", size=T)
def _draw(p: Pen, c: tuple) -> None:
    p.line([(4.5, 11.5), (12.5, 3.5)], c, 1.1)
    p.line([(11, 2.5), (13.5, 5)], c, 1.1)
    p.poly([(3.2, 12.8), (4.0, 10.6), (5.4, 12.0)], c)
    p.line([(2, 14.5), (14, 14.5)], c, 0.8)


@icon("GroupingIcons/Set3/time_grouping_3.png", size=T)
def _time(p: Pen, c: tuple) -> None:
    p.circle(8, 8, 6, c)
    p.line([(8, 4.2), (8, 8), (10.8, 9.8)], c)


@icon("GroupingIcons/Set3/channel_grouping_3.png", size=T)
def _channel(p: Pen, c: tuple) -> None:
    for y in (3.5, 8, 12.5):
        p.line([(2.5, y), (5, y)], c)
        p.line([(11, y), (13.5, y)], c)
    p.line([(5, 3.5), (11, 12.5)], c)
    p.line([(5, 8), (11, 8)], c)
    p.line([(5, 12.5), (11, 3.5)], c)


@icon("GroupingIcons/Set3/color_grouping_3.png", size=T)
def _color(p: Pen, c: tuple) -> None:
    p.circle(8, 5.6, 3.7, c, factor=0.9)
    p.circle(5.6, 9.9, 3.7, c, factor=0.9)
    p.circle(10.4, 9.9, 3.7, c, factor=0.9)


@icon("GroupingIcons/Set3/filter_grouping_3.png", size=T)
def _filter(p: Pen, c: tuple) -> None:
    p.circle(8, 8, 6, c, factor=0.8)
    p.circle(8, 8, 3.6, c, factor=0.8)
    p.circle(8, 8, 1.3, c, fill=True)


@icon("GroupingIcons/Set3/keyer_grouping_3.png", size=T)
def _keyer(p: Pen, c: tuple) -> None:
    p.circle(5, 8, 3, c)
    p.line([(8, 8), (14, 8)], c)
    p.line([(12, 8), (12, 11)], c)
    p.line([(14, 8), (14, 10.5)], c)


@icon("GroupingIcons/Set3/merge_grouping_3.png", size=T)
def _merge(p: Pen, c: tuple) -> None:
    p.rect(2, 2, 8, 8, c)
    p.rect(6, 6, 8, 8, c, fill=True)


@icon("GroupingIcons/Set3/transform_grouping_3.png", size=T)
def _transform(p: Pen, c: tuple) -> None:
    p.line([(8, 1.8), (8, 14.2)], c)
    p.line([(1.8, 8), (14.2, 8)], c)
    p.arrow_head(8, 1.8, 270, 2.6, c)
    p.arrow_head(8, 14.2, 90, 2.6, c)
    p.arrow_head(1.8, 8, 180, 2.6, c)
    p.arrow_head(14.2, 8, 0, 2.6, c)


@icon("GroupingIcons/Set3/3D_grouping_3.png", size=T)
def _three_d(p: Pen, c: tuple) -> None:
    p.poly([(8, 1.8), (13.6, 4.9), (13.6, 11.1), (8, 14.2), (2.4, 11.1), (2.4, 4.9)], c, outline=True)
    p.line([(2.4, 4.9), (8, 8), (13.6, 4.9)], c)
    p.line([(8, 8), (8, 14.2)], c)


@icon("GroupingIcons/Set3/deep_grouping_3.png", size=T)
def _deep(p: Pen, c: tuple) -> None:
    for k, y in enumerate((3, 6.5, 10)):
        p.rect(2 + k * 1.5, y, 9, 3.6, c, fill=k == 2, factor=0.9)


@icon("GroupingIcons/Set3/multiview_grouping_3.png", size=T)
def _views(p: Pen, c: tuple) -> None:
    p.circle(4.8, 9, 3, c)
    p.circle(11.2, 9, 3, c)
    p.line([(7.8, 9), (8.2, 9)], c)
    p.line([(1.8, 9), (1.2, 5.5)], c)
    p.line([(14.2, 9), (14.8, 5.5)], c)


@icon("GroupingIcons/Set3/toolsets_grouping_3.png", size=T)
def _toolsets(p: Pen, c: tuple) -> None:
    p.rect(2, 2, 5, 5, c, fill=True, radius=0.5)
    p.rect(9, 2, 5, 5, c, radius=0.5)
    p.rect(2, 9, 5, 5, c, radius=0.5)
    p.rect(9, 9, 5, 5, c, radius=0.5)


@icon("GroupingIcons/Set3/misc_grouping_3.png", size=T)
def _other(p: Pen, c: tuple) -> None:
    for x in (3.5, 8, 12.5):
        p.circle(x, 8, 1.4, c, fill=True)


@icon("GroupingIcons/Set3/other_grouping_3.png", size=T)
def _plugins(p: Pen, c: tuple) -> None:
    p.rect(3, 6, 10, 8, c, radius=1)
    p.line([(6, 2), (6, 6)], c)
    p.line([(10, 2), (10, 6)], c)


@icon("openeffects.png", size=T)
def _ofx(p: Pen, c: tuple) -> None:
    p.text(8, 8, "fx", c, 10, bold=True)


@icon("readImage.png")
def _read(p: Pen, c: tuple) -> None:
    p.rect(6, 3, 8, 10, c, radius=0.5)
    p.line([(1.5, 8), (9, 8)], c)
    p.arrow_head(9, 8, 0, 2.8, c)


@icon("writeImage.png")
def _write(p: Pen, c: tuple) -> None:
    p.rect(2, 3, 8, 10, c, radius=0.5)
    p.line([(7, 8), (14.5, 8)], c)
    p.arrow_head(14.5, 8, 0, 2.8, c)


# ---------------------------------------------------------------------------------------------------------------
# Script editor
# ---------------------------------------------------------------------------------------------------------------

@icon("clearOutput.png")
def _clear_output(p: Pen, c: tuple) -> None:
    for y in (4, 7, 10):
        p.line([(2.5, y), (9, y)], c, 0.9)
    p.line([(10, 9), (14, 13)], c)
    p.line([(14, 9), (10, 13)], c)


@icon("execScript.png")
def _exec(p: Pen, c: tuple) -> None:
    tri_right(p, 4.5, c, 10, 8)


@icon("loadAndExecScript.png")
def _load_exec(p: Pen, c: tuple) -> None:
    p.line([(1.5, 5), (4.5, 5), (5.5, 6), (9, 6), (9, 13), (1.5, 13)], c, closed=True, factor=0.9)
    tri_right(p, 10, c, 8, 5)


@icon("loadScript.png")
def _load(p: Pen, c: tuple) -> None:
    _open_file(p, c)


@icon("saveScript.png")
def _save(p: Pen, c: tuple) -> None:
    p.line([(2.5, 2.5), (11.5, 2.5), (13.5, 4.5), (13.5, 13.5), (2.5, 13.5)], c, closed=True)
    p.rect(5, 2.5, 6, 3.5, c, fill=True)
    p.rect(4.5, 9, 7, 4.5, c)


@icon("nextScript.png")
def _next_script(p: Pen, c: tuple) -> None:
    p.line([(3, 8), (12, 8)], c)
    p.arrow_head(12.5, 8, 0, 3, c)


@icon("previousScript.png")
def _prev_script(p: Pen, c: tuple) -> None:
    p.line([(4, 8), (13, 8)], c)
    p.arrow_head(3.5, 8, 180, 3, c)


@pair("outputPanelActivated.png", "outputPanelDeactivated.png")
def _output_pane(p: Pen, c: tuple) -> None:
    p.rect(2.5, 2.5, 11, 11, c)
    p.rect(2.5, 9, 11, 4.5, c, fill=True)


# ---------------------------------------------------------------------------------------------------------------
# The stylesheet's own small pictures (ext/icons/qss/, named in nuke.qss; not Natron pictures, so not in the table)
# ---------------------------------------------------------------------------------------------------------------

@icon("qss/check.png", size=12)
def _check(p: Pen, c: tuple) -> None:
    p.line([(3.2, 8.4), (6.6, 11.6), (12.8, 4.2)], c, 1.3)


@icon("qss/check_hover.png", size=12, colour=ACC)
def _check_hover(p: Pen, c: tuple) -> None:
    _check(p, c)


@icon("qss/arrow_down.png", size=9)
def _arrow_down(p: Pen, c: tuple) -> None:
    p.poly([(2.5, 5), (13.5, 5), (8, 11.5)], c)


@icon("qss/arrow_right.png", size=9)
def _arrow_right(p: Pen, c: tuple) -> None:
    p.poly([(5, 2.5), (11.5, 8), (5, 13.5)], c)


@icon("qss/close_tab.png", size=10, colour=DIM)
def _close_tab(p: Pen, c: tuple) -> None:
    p.line([(4, 4), (12, 12)], c, 1.2)
    p.line([(12, 4), (4, 12)], c, 1.2)


@icon("qss/close_tab_hover.png", size=10, colour=ACC)
def _close_tab_hover(p: Pen, c: tuple) -> None:
    _close_tab(p, c)


# ---------------------------------------------------------------------------------------------------------------

def render(name: str, scale: int) -> Image.Image:
    size, function, colour = ICONS[name]
    pen = Pen(size, scale)
    function(pen, colour)
    return pen.done()


THEME = "natron-layer"  # the File menu's icons: an icon theme Qt reads by name (natron_layer/skin.py sets it)
THEME_INDEX = """[Icon Theme]
Name=natron-layer
Comment=The Natron layer's own icons for Natron's menus (our drawings)
Directories=16x16,32x32

[16x16]
Size=16
Type=Fixed

[32x32]
Size=16
Scale=2
Type=Fixed
"""


def write_all(out: Path) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name in sorted(ICONS):
        if name.startswith("theme/"):
            base = out / "theme" / THEME
            for folder, scale in (("16x16", 1), ("32x32", 2)):
                target = base / folder / name[len("theme/"):]
                target.parent.mkdir(parents=True, exist_ok=True)
                render(name, scale).save(target, optimize=True)
            (base / "index.theme").write_text(THEME_INDEX, encoding="ascii")
            written.append(name)
            continue
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        render(name, 1).save(target, optimize=True)
        render(name, 2).save(target.with_name(target.stem + "@2x.png"), optimize=True)
        written.append(name)
    return written


def write_table(out: Path, written: list[str]) -> Path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import natron_pixmaps  # noqa: PLC0415

    rows = natron_pixmaps.table(REPO)
    by_file = {file: (name, number) for name, number, file in rows if file}
    lines = [
        "# SPDX-License-Identifier: GPL-3.0-or-later",
        "# This file is part of the layer of this Natron fork (see FORK.md at the repository root).",
        "#",
        "# Made by layer/tools/make_icons.py: each of our icons with the Natron picture it stands for, by the number",
        "# Natron caches that picture under (its place in Global/Enums.h) and the size it is drawn for. The skin",
        "# (natron_layer/skin.py) reads this; the smoke test checks the numbers against the fork's source.",
        "",
    ]
    for file in written:
        if file.startswith(("qss/", "theme/")):
            continue
        if file not in by_file:
            raise SystemExit(f"{file} isn't one of Natron's pictures (natron_pixmaps.py didn't find it)")
        name, number = by_file[file]
        lines += ["[[icon]]", f'file = "{file}"', f'natron = "{name}"', f"number = {number}",
                  f"size = {ICONS[file][0]}", ""]
    table = out / "pixmaps.toml"
    table.write_text("\n".join(lines), encoding="ascii")
    return table


def contact_sheet(path: Path) -> None:
    names = sorted(ICONS)
    cols = 10
    cell = 120
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cell, rows * cell), (50, 50, 50, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(str(FONT), 10)
    for i, name in enumerate(names):
        x, y = (i % cols) * cell, (i // cols) * cell
        big = render(name, 4)
        sheet.alpha_composite(big, (x + (cell - big.width) // 2, y + 6))
        one = render(name, 1)
        sheet.alpha_composite(one, (x + 4, y + cell - one.height - 18))
        two = render(name, 2)
        sheet.alpha_composite(two, (x + 30, y + cell - two.height - 18))
        draw.text((x + 4, y + cell - 14), Path(name).stem[:20], font=font, fill=(200, 200, 200, 255))
    sheet.save(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sheet", help="also write a contact sheet of every icon to this PNG")
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()
    # The second wave (make_icons_wave2.py) registers its drawings here: it imports this module by name.
    sys.modules.setdefault("make_icons", sys.modules[__name__])
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import make_icons_wave2  # noqa: F401, PLC0415

    out = Path(args.out)
    written = write_all(out)
    table = write_table(out, written)
    print(f"{len(written)} icons (1x and 2x) in {out}; table {table.name}")
    if args.sheet:
        contact_sheet(Path(args.sheet))
        print(f"Contact sheet: {args.sheet}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
