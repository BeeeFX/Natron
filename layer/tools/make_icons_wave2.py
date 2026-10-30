# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The skin's second wave of icons, drawn by ``make_icons.py`` (which imports this module): the Merge operations'
pictures, the roto and paint tools, the tracker's buttons, the curve editor's interpolation buttons, a few text and
style buttons, and the File menu's icons (an icon theme, ``theme/``, which Qt reads by name).

Our own drawings in the same flat grey line style as the first wave, nothing traced or copied. Merge operations are
drawn as two shapes, A (a square) and B (a circle): the parts the operation keeps are filled (A's light, B's grey),
and the operations that mix colours rather than cut shapes show a short sign over the two shapes.
"""

from __future__ import annotations

from PIL import Image, ImageChops, ImageDraw

from make_icons import ACC, DIM, FG, RED, Pen, icon, pair

A_FILL = FG
B_FILL = (150, 150, 150, 255)
DARK = (40, 40, 40, 255)

# ---------------------------------------------------------------------------------------------------------------
# Merge operations: (A only, B only, both) kept, or a sign for the colour operations
# ---------------------------------------------------------------------------------------------------------------

SHAPES = {  # region fills: "A", "B" or "" for A only, B only, A and B
    "over": ("A", "B", "A"), "under": ("A", "B", "B"), "in": ("", "", "A"), "out": ("A", "", ""),
    "atop": ("", "B", "A"), "xor": ("A", "B", ""), "mask": ("", "", "B"), "stencil": ("", "B", ""),
    "copy": ("A", "", "A"), "matte": ("A", "B", "A"), "conjoint_over": ("A", "B", "A"),
    "disjoint_over": ("A", "B", "A"),
}
SIGNS = {
    "plus": "+", "minus": "−", "from": "−", "multiply": "×", "divide": "÷",
    "difference": "Δ", "average": "½", "max": "↑", "min": "↓", "hypot": "√",
    "screen": "S", "overlay": "O", "hard_light": "H", "soft_light": "s", "color": "C", "hue": "h",
    "saturation": "Sa", "luminosity": "L", "color_burn": "cb", "color_dodge": "cd", "exclusion": "ex",
    "freeze": "fz", "geometric": "g", "grain_extract": "ge", "grain_merge": "gm", "pinlight": "pl",
    "reflect": "rf",
}
TAGS = {"matte": "m", "conjoint_over": "c", "disjoint_over": "d"}


def _venn(p: Pen, fills: tuple[str, str, str]) -> None:
    """A as a square (upper left), B as a circle (lower right); each region filled with A's or B's grey."""
    size = p.px
    a = Image.new("L", (size, size), 0)
    b = Image.new("L", (size, size), 0)
    ImageDraw.Draw(a).rectangle((*p.p(1.5, 1.5), *p.p(10, 10)), fill=255)
    ImageDraw.Draw(b).ellipse((*p.p(6, 6), *p.p(14.8, 14.8)), fill=255)
    regions = (ImageChops.subtract(a, b), ImageChops.subtract(b, a), ImageChops.multiply(a, b))
    for mask, fill in zip(regions, fills):
        if fill:
            p.image.paste(Image.new("RGBA", (size, size), A_FILL if fill == "A" else B_FILL), (0, 0), mask)
    p.rect(1.5, 1.5, 8.5, 8.5, FG, factor=0.8)
    p.circle(10.4, 10.4, 4.4, FG, factor=0.8)


def _merge_drawing(op: str):
    def draw(p: Pen, c: tuple) -> None:
        if op in SHAPES:
            _venn(p, SHAPES[op])
            if op in TAGS:
                p.text(12.3, 4.0, TAGS[op], ACC, 6.5, bold=True)
        else:
            p.rect(1.5, 1.5, 8.5, 8.5, DIM, factor=0.8)
            p.circle(10.4, 10.4, 4.4, DIM, factor=0.8)
            sign = SIGNS[op]
            p.text(8, 8.2, sign, c, 11 if len(sign) == 1 else 7.5, bold=True)

    return draw


for _op in list(SHAPES) + list(SIGNS):
    icon(f"merge_{_op}.png")(_merge_drawing(_op))


# ---------------------------------------------------------------------------------------------------------------
# Roto: shapes and point tools
# ---------------------------------------------------------------------------------------------------------------

def _bez(p0, p1, p2, p3, steps=24):
    out = []
    for k in range(steps + 1):
        t = k / steps
        mt = 1 - t
        out.append((mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t ** 3 * p3[0],
                    mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t ** 3 * p3[1]))
    return out


def _curve(p: Pen, c: tuple, factor: float = 1.0) -> None:
    p.line(_bez((2, 12.5), (4, 3), (10, 14), (14, 3.5)), c, factor)


@icon(["bezier.png", "bezier32.png"])
def _bezier(p: Pen, c: tuple) -> None:
    p.line(_bez((2, 13), (3, 4), (12, 4), (14, 13)), c)
    p.line([(1.5, 5.5), (8, 5.5), (14.5, 5.5)], DIM, 0.7)
    p.rect(6.6, 4.1, 2.8, 2.8, c, fill=True)
    for x in (1.5, 14.5):
        p.circle(x, 5.5, 1.1, c, fill=True)


@icon("rotoToolPencil.png")
def _pencil(p: Pen, c: tuple) -> None:
    p.poly([(11, 2), (14, 5), (6, 13), (3, 13), (3, 10)], c, outline=True)
    p.line([(9.5, 3.5), (12.5, 6.5)], c)


@icon("curve.png")
def _curve_icon(p: Pen, c: tuple) -> None:
    _curve(p, c)


@icon("ellipse.png")
def _ellipse(p: Pen, c: tuple) -> None:
    p.draw.ellipse((*p.p(1.8, 3.5), *p.p(14.2, 12.5)), outline=c, width=int(round(p.width())))


@icon("rectangle.png")
def _rectangle(p: Pen, c: tuple) -> None:
    p.rect(2, 3.5, 12, 9, c)


def _plus(p: Pen, x: float, y: float, c: tuple, r: float = 2.6) -> None:
    p.line([(x - r, y), (x + r, y)], c, 1.1)
    p.line([(x, y - r), (x, y + r)], c, 1.1)


@icon("addPoints.png")
def _add_points(p: Pen, c: tuple) -> None:
    p.line(_bez((1.5, 13), (3, 6), (7, 5), (10, 9)), c)
    p.circle(5.0, 7.3, 1.2, c, fill=True)
    _plus(p, 12.2, 4.0, ACC)


@icon("removePoints.png")
def _remove_points(p: Pen, c: tuple) -> None:
    p.line(_bez((1.5, 13), (3, 6), (7, 5), (10, 9)), c)
    p.circle(5.0, 7.3, 1.2, c, fill=True)
    p.line([(9.6, 4.0), (14.8, 4.0)], ACC, 1.1)


@icon("cuspPoints.png")
def _cusp(p: Pen, c: tuple) -> None:
    p.line([(2, 12), (8, 4), (14, 12)], c)
    p.rect(6.7, 2.7, 2.6, 2.6, c, fill=True)


@icon("smoothPoints.png")
def _smooth(p: Pen, c: tuple) -> None:
    p.line(_bez((2, 12), (4, 3), (12, 3), (14, 12)), c)
    p.line([(3, 5.3), (13, 5.3)], DIM, 0.7)
    p.rect(6.7, 4.0, 2.6, 2.6, c, fill=True)


def _dashed(p: Pen, points, c: tuple, factor: float = 0.9) -> None:
    for k in range(0, len(points) - 1, 2):
        p.line([points[k], points[k + 1]], c, factor)


@icon("removeFeather.png")
def _remove_feather(p: Pen, c: tuple) -> None:
    _dashed(p, _bez((2, 13), (3, 3), (11, 3), (12, 9), steps=14), c)
    p.line([(10, 10), (14.5, 14.5)], RED, 1.1)
    p.line([(14.5, 10), (10, 14.5)], RED, 1.1)


@icon("openCloseCurve.png")
def _open_close(p: Pen, c: tuple) -> None:
    p.arc(8, 8, 5.5, 40, 320, c)
    p.circle(8 + 5.5 * 0.766, 8 - 5.5 * 0.643, 1.2, c, fill=True)
    p.circle(8 + 5.5 * 0.766, 8 + 5.5 * 0.643, 1.2, c, fill=True)


def _cursor(p: Pen, c: tuple, x: float = 2.5, y: float = 1.8, s: float = 1.0) -> None:
    p.poly([(x, y), (x, y + 11 * s), (x + 3 * s, y + 8.2 * s), (x + 5.2 * s, y + 12.4 * s),
            (x + 6.8 * s, y + 11.6 * s), (x + 4.7 * s, y + 7.6 * s), (x + 8.4 * s, y + 7.4 * s)], c)


@icon("cursor.png")
def _select_all(p: Pen, c: tuple) -> None:
    _cursor(p, c, 4, 2)


@icon("selectPoints.png")
def _select_points(p: Pen, c: tuple) -> None:
    _cursor(p, c, 1.5, 1.5, 0.8)
    for x, y in ((10, 9), (13.5, 12.5), (12.5, 6)):
        p.rect(x - 1.1, y - 1.1, 2.2, 2.2, c, fill=True)


@icon("selectFeather.png")
def _select_feather(p: Pen, c: tuple) -> None:
    _cursor(p, c, 1.5, 1.5, 0.8)
    _dashed(p, _bez((7, 14.5), (9, 7), (13, 6), (15, 10), steps=10), c, 0.8)


@icon("selectCurves.png")
def _select_curves(p: Pen, c: tuple) -> None:
    _cursor(p, c, 1.5, 1.5, 0.8)
    p.line(_bez((7, 14.5), (9, 7), (13, 6), (15, 10)), c, 0.9)


def _key(p: Pen, c: tuple, cx: float = 8, cy: float = 8, r: float = 4.5, fill: bool = True) -> None:
    p.poly([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], c, outline=not fill)


@pair("autoKeyingEnabled.png", "autoKeyingDisabled.png")
def _auto_key(p: Pen, c: tuple) -> None:
    _key(p, c, 6.5, 9, 4.5)
    p.text(12.5, 4.5, "A", c, 7, bold=True)


@pair("stickySelectionEnabled.png", "stickySelectionDisabled.png")
def _sticky(p: Pen, c: tuple) -> None:
    p.circle(8, 5.5, 3.3, c, fill=True)
    p.line([(8, 8.5), (8, 14.5)], c, 1.1)
    p.line([(4.5, 9.5), (11.5, 9.5)], c)


@pair("featherLinkEnabled.png", "featherLinkDisabled.png")
def _feather_link(p: Pen, c: tuple) -> None:
    p.rect(1.8, 5.5, 7, 5, c, radius=2.4)
    p.rect(7.2, 5.5, 7, 5, c, radius=2.4)


@pair("featherEnabled.png", "featherDisabled.png", on_colour=FG, off_colour=DIM)
def _feather_visible(p: Pen, c: tuple) -> None:
    p.rect(4.5, 4.5, 7, 7, c)
    pts = []
    for k in range(17):
        t = k / 16
        side = int(t * 4) % 4
        f = t * 4 - int(t * 4)
        corners = [(1.8, 1.8), (14.2, 1.8), (14.2, 14.2), (1.8, 14.2), (1.8, 1.8)]
        (x0, y0), (x1, y1) = corners[side], corners[side + 1]
        pts.append((x0 + (x1 - x0) * f, y0 + (y1 - y0) * f))
    _dashed(p, pts, c, 0.8)


@pair("rippleEditEnabled.png", "rippleEditDisabled.png")
def _ripple(p: Pen, c: tuple) -> None:
    p.circle(8, 8, 1.6, c, fill=True)
    p.arc(8, 8, 4.2, 200, 340, c, 0.9)
    p.arc(8, 8, 4.2, 20, 160, c, 0.9)
    p.arc(8, 8, 6.6, 210, 330, c, 0.8)
    p.arc(8, 8, 6.6, 30, 150, c, 0.8)


# ---------------------------------------------------------------------------------------------------------------
# Paint tools
# ---------------------------------------------------------------------------------------------------------------

@icon("rotopaint_solid.png")
def _solid(p: Pen, c: tuple) -> None:
    p.line(_bez((2, 12), (5, 3), (9, 13), (14, 4)), c, 2.4)


@icon("rotopaint_eraser.png")
def _eraser(p: Pen, c: tuple) -> None:
    p.poly([(2, 10.5), (8.5, 4), (14, 9.5), (9.5, 14), (5.5, 14)], c, outline=True)
    p.poly([(2, 10.5), (5.2, 7.3), (10.6, 12.7), (9.3, 14), (5.5, 14)], c)


@icon("rotopaint_clone.png")
def _clone(p: Pen, c: tuple) -> None:
    p.rect(3.5, 9.5, 9, 3, c, fill=True, radius=0.6)
    p.line([(8, 9.5), (8, 5.5)], c, 1.4)
    p.circle(8, 4.2, 2.4, c, fill=True)
    p.line([(2.5, 14.5), (13.5, 14.5)], c)


@icon("rotopaint_reveal.png")
def _reveal(p: Pen, c: tuple) -> None:
    p.rect(2, 2.5, 12, 11, DIM, factor=0.8)
    p.line(_bez((3, 11), (6, 4), (9, 12), (13, 5)), c, 2.0)


@icon("rotopaint_blur.png")
def _blur(p: Pen, c: tuple) -> None:
    p.poly([(8, 2), (12, 9), (12, 10.5), (10.5, 13.4), (8, 14.2), (5.5, 13.4), (4, 10.5), (4, 9)], c, outline=True)


@icon("rotopaint_sharpen.png")
def _sharpen(p: Pen, c: tuple) -> None:
    p.poly([(8, 1.8), (11, 14), (5, 14)], c, outline=True)
    p.line([(8, 6), (8, 12)], c, 0.8)


@icon("rotopaint_smear.png")
def _smear(p: Pen, c: tuple) -> None:
    for dy, cc in ((-3, DIM), (0, c), (3, DIM)):
        p.line(_bez((2, 9 + dy), (6, 5 + dy), (9, 11 + dy), (14, 7 + dy)), cc, 0.9)


@icon("rotopaint_dodge.png")
def _dodge(p: Pen, c: tuple) -> None:
    p.circle(6.5, 6.5, 4.0, c)
    p.line([(9.4, 9.4), (14, 14)], c, 1.3)


@icon("rotopaint_burn.png")
def _burn(p: Pen, c: tuple) -> None:
    p.circle(5.0, 11.0, 2.4, c, fill=True)
    p.line([(6.8, 9.2), (13.5, 2.5)], c, 1.1)
    p.line([(12.0, 5.5), (14.5, 8.0)], c, 0.8)


@pair("rotopaint_buildup_on.png", "rotopaint_buildup_off.png")
def _buildup(p: Pen, c: tuple) -> None:
    for k, y in enumerate((12.5, 9, 5.5)):
        p.rect(3 + k, y - 1.2, 10 - 2 * k, 2.4, c, fill=True, radius=1)


@pair("rotopaint_pressure_on.png", "rotopaint_pressure_off.png")
def _pressure(p: Pen, c: tuple) -> None:
    p.poly([(12.5, 1.5), (14.5, 3.5), (7, 11), (4.5, 11.5), (5, 9)], c, outline=True)
    p.poly([(1.5, 14.5), (4.8, 12.8), (13.5, 14.5)], c)


@icon("roto_merge.png")
def _roto_merge(p: Pen, c: tuple) -> None:
    _venn(p, ("A", "B", "A"))


# ---------------------------------------------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------------------------------------------

def _target(p: Pen, c: tuple, cx: float = 8, cy: float = 8, r: float = 4.5) -> None:
    p.rect(cx - r, cy - r, 2 * r, 2 * r, c, factor=0.9)
    p.line([(cx - 1.4, cy), (cx + 1.4, cy)], c, 0.8)
    p.line([(cx, cy - 1.4), (cx, cy + 1.4)], c, 0.8)


@icon("addTrack.png")
def _add_track(p: Pen, c: tuple) -> None:
    _target(p, c, 6.5, 9.5, 4.5)
    _plus(p, 12.8, 3.4, ACC)


@icon("addUserKey.png")
def _add_user_key(p: Pen, c: tuple) -> None:
    _key(p, c, 6.5, 9.5, 4.5)
    _plus(p, 12.8, 3.4, ACC)


@icon("removeUserKey.png")
def _remove_user_key(p: Pen, c: tuple) -> None:
    _key(p, c, 6.5, 9.5, 4.5)
    p.line([(10.2, 3.4), (15.2, 3.4)], ACC, 1.1)


@icon("removeUserKeys.png")
def _reset_user_keys(p: Pen, c: tuple) -> None:
    _key(p, c, 5.5, 8, 3.6, fill=False)
    _key(p, c, 10.5, 8, 3.6, fill=False)
    p.line([(2, 14), (14, 2)], RED, 1.1)


@pair("showTrackError.png", "hideTrackError.png", on_colour=FG, off_colour=DIM)
def _track_error(p: Pen, c: tuple) -> None:
    p.line([(2, 2), (2, 14), (14, 14)], c, 0.8)
    p.line([(3, 12), (6, 9), (8, 11), (10.5, 5), (13.5, 7)], RED, 1.0)


@icon("resetTrackOffset.png")
def _reset_offset(p: Pen, c: tuple) -> None:
    _target(p, c, 9.5, 9.5, 4.2)
    p.line([(9.5, 9.5), (3, 3)], c, 0.9)
    p.arrow_head(3, 3, 225, 2.6, c, 0.9)


@pair("createKeyOnMoveOn.png", "createKeyOnMoveOff.png")
def _key_on_move(p: Pen, c: tuple) -> None:
    _key(p, c, 6, 10, 3.8)
    for dx, dy in ((1, 0), (0, -1)):
        x0, y0 = 11.5, 4.5
        p.line([(x0 - 3 * dx, y0 - 3 * dy), (x0 + 3 * dx, y0 + 3 * dy)], c, 0.8)
    p.arrow_head(14.5, 4.5, 0, 1.8, c, 0.8)
    p.arrow_head(11.5, 1.5, -90, 1.8, c, 0.8)


@icon("centerOnTrack.png")
def _center_on_track(p: Pen, c: tuple) -> None:
    p.circle(8, 8, 5.5, c, factor=0.9)
    p.circle(8, 8, 1.5, c, fill=True)
    for (x0, y0), (x1, y1) in (((8, 0.8), (8, 3.6)), ((8, 12.4), (8, 15.2)), ((0.8, 8), (3.6, 8)), ((12.4, 8), (15.2, 8))):
        p.line([(x0, y0), (x1, y1)], c, 0.9)


def _tri(p: Pen, c: tuple, x: float, direction: int, h: float = 8.0, w: float = 6.0) -> None:
    p.poly([(x, 8 - h / 2), (x + w * direction, 8), (x, 8 + h / 2)], c)


@pair("trackBackwardOn.png", "trackBackwardOff.png")
def _track_backward(p: Pen, c: tuple) -> None:
    _tri(p, c, 8.5, -1)
    p.line([(10.5, 4), (10.5, 12)], c, 0.9)
    p.line([(13.5, 4), (13.5, 12)], c, 0.9)


@pair("trackForwardOn.png", "trackForwardOff.png")
def _track_forward(p: Pen, c: tuple) -> None:
    _tri(p, c, 7.5, 1)
    p.line([(2.5, 4), (2.5, 12)], c, 0.9)
    p.line([(5.5, 4), (5.5, 12)], c, 0.9)


@icon("trackPrev.png")
def _track_prev(p: Pen, c: tuple) -> None:
    _tri(p, c, 10, -1)
    p.line([(12, 4), (12, 12)], c)


@icon("trackNext.png")
def _track_next(p: Pen, c: tuple) -> None:
    _tri(p, c, 6, 1)
    p.line([(4, 4), (4, 12)], c)


@icon("trackRange.png")
def _track_range(p: Pen, c: tuple) -> None:
    p.line([(1.5, 3.5), (1.5, 12.5)], c)
    p.line([(14.5, 3.5), (14.5, 12.5)], c)
    p.line([(3.5, 8), (12.5, 8)], c, 0.9)
    p.arrow_head(3.5, 8, 180, 2.4, c, 0.9)
    p.arrow_head(12.5, 8, 0, 2.4, c, 0.9)


@icon("trackAllKeyframes.png")
def _track_all_keys(p: Pen, c: tuple) -> None:
    for x in (3.5, 8, 12.5):
        _key(p, c, x, 8, 2.6)
    p.line([(1, 13.5), (15, 13.5)], DIM, 0.8)


@icon("trackCurrentKeyframe.png")
def _track_current_key(p: Pen, c: tuple) -> None:
    _key(p, DIM, 3.5, 8, 2.4, fill=False)
    _key(p, ACC, 8, 8, 3.2)
    _key(p, DIM, 12.5, 8, 2.4, fill=False)


@icon("prevUserKey.png")
def _prev_user_key(p: Pen, c: tuple) -> None:
    _key(p, c, 10.5, 8, 3.8)
    p.poly([(5.5, 4.5), (2, 8), (5.5, 11.5)], c)


@icon("nextUserKey.png")
def _next_user_key(p: Pen, c: tuple) -> None:
    _key(p, c, 5.5, 8, 3.8)
    p.poly([(10.5, 4.5), (14, 8), (10.5, 11.5)], c)


# ---------------------------------------------------------------------------------------------------------------
# Curve editor and dope sheet: interpolation
# ---------------------------------------------------------------------------------------------------------------

def _keys_at(p: Pen, c: tuple, points) -> None:
    for x, y in points:
        p.rect(x - 1.2, y - 1.2, 2.4, 2.4, c, fill=True)


@icon("interp_constant.png")
def _interp_constant(p: Pen, c: tuple) -> None:
    p.line([(2, 12), (8, 12), (8, 4), (14, 4)], c)
    _keys_at(p, ACC, [(2, 12), (8, 4)])


@icon("interp_linear.png")
def _interp_linear(p: Pen, c: tuple) -> None:
    p.line([(2, 12), (14, 4)], c)
    _keys_at(p, ACC, [(2, 12), (14, 4)])


@icon("interp_curve.png")
def _interp_curve(p: Pen, c: tuple) -> None:
    p.line(_bez((2, 12), (8, 12), (8, 4), (14, 4)), c)
    _keys_at(p, ACC, [(2, 12), (14, 4)])


@icon("interp_curve_z.png")  # smooth
def _interp_smooth(p: Pen, c: tuple) -> None:
    p.line(_bez((2, 12), (6, 12), (10, 4), (14, 4)), c)
    p.line([(4.5, 12), (11.5, 4)], DIM, 0.6)
    _keys_at(p, ACC, [(2, 12), (14, 4)])


@icon("interp_curve_r.png")  # cubic
def _interp_cubic(p: Pen, c: tuple) -> None:
    p.line(_bez((2, 13), (4, 2), (12, 14), (14, 3)), c)
    _keys_at(p, ACC, [(2, 13), (14, 3)])


@icon("interp_curve_c.png")  # Catmull-Rom
def _interp_catmull(p: Pen, c: tuple) -> None:
    p.line(_bez((2, 12), (5, 6), (6, 5), (8, 6)) + _bez((8, 6), (10, 7), (11, 5), (14, 4))[1:], c)
    _keys_at(p, ACC, [(2, 12), (8, 6), (14, 4)])


@icon("interp_curve_h.png")  # horizontal
def _interp_horizontal(p: Pen, c: tuple) -> None:
    p.line(_bez((2, 12), (7, 12), (9, 4), (14, 4)), c)
    p.line([(0.8, 12), (4.5, 12)], DIM, 0.7)
    p.line([(11.5, 4), (15.2, 4)], DIM, 0.7)
    _keys_at(p, ACC, [(2, 12), (14, 4)])


@icon("interp_break.png")
def _interp_break(p: Pen, c: tuple) -> None:
    p.line(_bez((2, 12), (4, 6), (6, 5), (8, 5)), c)
    p.line(_bez((8, 5), (10, 8), (12, 12), (14, 12)), c)
    p.line([(5, 3.5), (8, 5)], DIM, 0.7)
    p.line([(8, 5), (11, 3.5)], DIM, 0.7)
    _keys_at(p, ACC, [(8, 5)])


# ---------------------------------------------------------------------------------------------------------------
# Text style buttons
# ---------------------------------------------------------------------------------------------------------------

@pair("bold_checked.png", "bold_unchecked.png")
def _bold(p: Pen, c: tuple) -> None:
    p.text(8, 8.3, "B", c, 12, bold=True)


@pair("italic_checked.png", "italic_unchecked.png")
def _italic(p: Pen, c: tuple) -> None:
    p.line([(9.5, 3), (6.5, 13)], c, 1.5)
    p.line([(7, 3), (12, 3)], c, 1.1)
    p.line([(4, 13), (9, 13)], c, 1.1)


# ---------------------------------------------------------------------------------------------------------------
# The File menu: an icon theme read by name (QIcon::fromTheme in Natron's Gui.cpp); 16 px at 1x
# ---------------------------------------------------------------------------------------------------------------

def _page(p: Pen, c: tuple) -> None:
    p.line([(3.5, 1.5), (9.5, 1.5), (12.5, 4.5), (12.5, 14.5), (3.5, 14.5)], c, closed=True)
    p.line([(9.5, 1.5), (9.5, 4.5), (12.5, 4.5)], c, 0.8)


@icon("theme/document-new.png", size=16)
def _doc_new(p: Pen, c: tuple) -> None:
    _page(p, c)
    _plus(p, 8, 9.5, ACC, 2.4)


@icon("theme/document-open.png", size=16)
def _doc_open(p: Pen, c: tuple) -> None:
    p.line([(1.5, 3.5), (5.5, 3.5), (7, 5), (13, 5), (13, 7)], c)
    p.line([(1.5, 3.5), (1.5, 13.5), (12.5, 13.5), (15, 7), (4, 7), (1.5, 13.5)], c)


@icon("theme/document-close.png", size=16)
def _doc_close(p: Pen, c: tuple) -> None:
    _page(p, c)
    p.line([(6, 7.5), (10, 11.5)], c, 1.1)
    p.line([(10, 7.5), (6, 11.5)], c, 1.1)


@icon("theme/document-save.png", size=16)
def _doc_save(p: Pen, c: tuple) -> None:
    p.line([(2, 2), (12, 2), (14, 4), (14, 14), (2, 14)], c, closed=True)
    p.rect(4.5, 2, 6, 4, c, fill=True)
    p.rect(4.5, 9, 7, 5, c, factor=0.8)


@icon("theme/document-save-as.png", size=16)
def _doc_save_as(p: Pen, c: tuple) -> None:
    p.line([(2, 2), (10, 2), (12, 4), (12, 8)], c)
    p.line([(2, 2), (2, 14), (7, 14)], c)
    p.rect(4, 2, 5, 3.5, c, fill=True)
    p.poly([(13, 7.5), (15, 9.5), (10, 14.5), (8, 14.8), (8.2, 12.6)], ACC, outline=True, factor=0.8)


@icon("theme/application-exit.png", size=16)
def _exit(p: Pen, c: tuple) -> None:
    p.line([(9, 2), (2.5, 2), (2.5, 14), (9, 14)], c)
    p.line([(6.5, 8), (14, 8)], c)
    p.arrow_head(14, 8, 0, 3, c)


@icon("theme/document-properties.png", size=16)
def _doc_properties(p: Pen, c: tuple) -> None:
    for y in (4, 8, 12):
        p.line([(2, y), (14, y)], c, 0.8)
    for x, y in ((10, 4), (5, 8), (11, 12)):
        p.rect(x - 1.5, y - 1.5, 3, 3, c, fill=True)


@icon("theme/view-fullscreen.png", size=16)
def _fullscreen(p: Pen, c: tuple) -> None:
    for (x, y), (dx, dy) in (((2, 2), (1, 1)), ((14, 2), (-1, 1)), ((2, 14), (1, -1)), ((14, 14), (-1, -1))):
        p.line([(x + 4 * dx, y), (x, y), (x, y + 4 * dy)], c)


_ = (DARK,)  # kept for later drawings
