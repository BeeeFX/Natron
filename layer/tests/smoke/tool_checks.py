# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
"""The smoke checks of the layer's tools (roadmap items 5 to 7), run inside NatronRenderer by smoke_checks.py.

- The gizmo pack: each gizmo registered and made by its plug-in ID, and rendering known pixels (values worked out by
  hand, or Natron's own nodes set up by hand for the same result).
- A comp of every gizmo saved for run_smoke.py's run without the layer (project_checks.py), which must render the
  same pixels from the saved Groups alone.
- The workflow scripts on a test comp: layers extracted, similar nodes, Merge cycling, roto linked to a track and
  baked, files collected (the copy rendered again without the layer), a flipbook through NatronRenderer.
- The expression recipes: each one's values on known frames.
- The studio ToolSets' recipes: the CG beauty rebuild adds up to the beauty; the grain and lens stack renders (its
  pixels kept to compare with the pasted ToolSet from the window).

Everything is written in NATRON_LAYER_SMOKE_OUT. This file stays plain ASCII.
"""

import json
import os
import traceback

OUT = os.environ.get("NATRON_LAYER_SMOKE_OUT", "")
COLOUR = "uk.co.thefoundry.OfxImagePlaneColour"
JOBS = []  # projects for project_checks.py: rendered again without the layer


# --- Helpers ---


def folder(name):
    path = os.path.join(OUT, name)
    os.makedirs(path, exist_ok=True)
    return path


def node(app, plugin_id, values=(), inputs=(), name=None):
    from natron_layer import compat

    made = compat.create_node(app, plugin_id)
    if made is None:
        raise RuntimeError("no node " + plugin_id)
    if name:
        made.setScriptName(name)
    for param, value in values:
        if not compat.set_node_value(made, param, value):
            raise RuntimeError(plugin_id + " has no " + param + " taking " + repr(value))
    for number, source in enumerate(inputs):
        if source is not None:
            compat.connect(made, number, source)
    return made


def constant(app, rgba, fmt="square_256", name=None):
    made = node(app, "net.sf.openfx.ConstantPlugin", (("extent", "format"), ("NatronParamFormatChoice", fmt)),
                name=name)
    for d in range(4):
        made.getParam("color").setValue(rgba[d], d)
    return made


def ramp(app, source, horizontal=True):
    end = (256.0, 0.0) if horizontal else (0.0, 256.0)
    return node(app, "net.sf.openfx.Ramp", (("point0", (0.0, 0.0)), ("point1", end), ("color0", (0.0, 0.0, 0.0, 1.0)),
                                             ("color1", (1.0, 1.0, 1.0, 1.0))), (source,))


_NAMES = [0]


def gizmo(app, name, source=None, values=()):
    """A gizmo by its plug-in ID, given a name never used in this session: Natron removes a deleted node's Python
    name later, which would take a new node's away if it reused it (the test deletes nodes between checks)."""
    from natron_layer import compat, gizmos

    made = compat.create_node(app, gizmos.BY_NAME[name].plugin_id)
    if made is None:
        raise RuntimeError("Natron couldn't make " + name)
    _NAMES[0] += 1
    made.setScriptName("T" + str(_NAMES[0]) + name)
    for param, value in values:
        if not compat.set_node_value(made, param, value):
            raise RuntimeError(name + " has no " + param + " taking " + repr(value))
    if source is not None:
        compat.connect(made, 0, source)
    return made


def writer(app, source, path, frame=1, last=None, name=None):
    from natron_layer import compat

    write = app.createWriter(path.replace("\\", "/"))
    if name:
        write.setScriptName(name)
    compat.connect(write, 0, source)
    for param, value in (("frameRange", "manual"), ("firstFrame", frame), ("lastFrame", last or frame),
                         ("formatType", "input")):
        compat.set_node_value(write, param, value)
    space_in, space_out = write.getParam("ocioInputSpace"), write.getParam("ocioOutputSpace")
    if space_in is not None and space_out is not None:
        space_out.setValue(space_in.get())  # the file holds the comp's values
    return write


def render(app, source, name, frame=1, sub="tools"):
    path = os.path.join(folder(sub), name + ".####.exr")
    write = writer(app, source, path, frame)
    app.render(write, frame, frame)
    done = path.replace("####", "%04d" % frame)
    return done if os.path.isfile(done) else None


def buf(path):
    import OpenImageIO as oiio

    return oiio.ImageBuf(path)


def px(path, x, y):
    """A pixel at Natron's (x, y), y up (OpenImageIO counts y down)."""
    image = buf(path)
    return tuple(image.getpixel(x, image.spec().height - 1 - y))


def stats(path):
    import OpenImageIO as oiio

    s = oiio.ImageBufAlgo.computePixelStats(buf(path))
    return {"min": tuple(s.min), "max": tuple(s.max), "avg": tuple(s.avg), "std": tuple(s.stddev)}


def max_diff(a, b, channels=None):
    """The largest difference between two renders (over ``channels``, indexes, or all)."""
    import OpenImageIO as oiio

    if a is None or b is None:
        return 1e9
    one, two = buf(a), buf(b)
    if channels is not None:
        one = oiio.ImageBufAlgo.channels(one, tuple(channels))
        two = oiio.ImageBufAlgo.channels(two, tuple(channels))
    diff = oiio.ImageBufAlgo.absdiff(one, two)
    return max(oiio.ImageBufAlgo.computePixelStats(diff).max)


def near(values, expected, tolerance=1e-4):
    return len(values) >= len(expected) and all(abs(a - b) <= tolerance for a, b in zip(values, expected))


def rounded(values, digits=4):
    return tuple(round(v, digits) for v in values)


def clear(app):
    """Delete every node of the comp, after giving each a name never used again: Natron keeps a deleted node's name
    (and later removes its Python name), so a new node named the same would clash."""
    from natron_layer import compat

    for each in compat.children(app):
        try:
            _NAMES[0] += 1
            each.setScriptName("Gone" + str(_NAMES[0]))
            each.destroy()
        except Exception:
            pass


def section(say, title, check, *args):
    try:
        check(say, *args)
    except Exception:
        say(False, title + " raised:\n" + traceback.format_exc())


# --- Item 5: the gizmo pack ---


def check_registered(say, app):
    import NatronEngine
    from natron_layer import gizmos

    ids = {str(i) for i in NatronEngine.natron.getPluginIDs()}
    say(len(gizmos.available()) == len(gizmos.GIZMOS), "every gizmo's Natron nodes exist in this Natron ("
        + ", ".join(g.name for g in gizmos.GIZMOS) + ")")
    for each in gizmos.GIZMOS:
        made = gizmo(app, each.name)
        inner = len(made.getChildren())
        say(each.plugin_id in ids and inner > 2 and made.getInputLabel(0) in ("Source", "Format"),
            each.name + " is registered as " + each.plugin_id + " in " + each.grouping + " and made by its ID: a "
            "Group of " + str(inner) + " Natron nodes, input " + made.getInputLabel(0))
        made.destroy()


def check_grain(say, app):
    src = constant(app, (0.18, 0.18, 0.18, 1.0))
    grain = gizmo(app, "Grain", src)
    a = render(app, grain, "grain_f1", 1)
    again = render(app, grain, "grain_f1_again", 1)
    b = render(app, grain, "grain_f2", 2)
    s = stats(a)
    scale = 0.5 + 0.5 * 0.18  # Response 0.5 at a value of 0.18
    wanted = [0.035 * scale, 0.03 * scale, 0.045 * scale]
    say(all(abs(s["avg"][c] - 0.18) < 0.004 for c in range(3)) and s["min"][3] == s["max"][3] == 1.0,
        "Grain keeps the image's average (0.18) and its alpha: " + str(rounded(s["avg"])))
    say(all(abs(s["std"][c] - wanted[c]) < 0.2 * wanted[c] for c in range(3)),
        "Grain's spread per channel is Intensity x the response (" + str(rounded(wanted)) + "): "
        + str(rounded(s["std"][:3])))
    say(max_diff(a, again) == 0.0 and max_diff(a, b) > 0.01,
        "the same frame gives the same grain, the next frame another (Animated)")
    grain.getParam("animated").setValue(False)
    c = render(app, grain, "grain_static_f1", 1)
    d = render(app, grain, "grain_static_f2", 2)
    say(max_diff(c, d) == 0.0, "Animated off: the same grain on every frame")
    grain.getParam("response").setValue(0.0)
    e = stats(render(app, grain, "grain_response0", 1))
    say(all(abs(e["std"][ch] - w) < 0.2 * w for ch, w in enumerate((0.035, 0.03, 0.045))),
        "Response 0: the spread is Intensity itself: " + str(rounded(e["std"][:3])))
    grain.getParam("mix").setValue(0.0)
    say(max_diff(render(app, grain, "grain_mix0", 1), render(app, src, "grain_src", 1)) < 1e-6,
        "Mix 0 gives the image back")


def check_zdefocus(say, app):
    import OpenImageIO as oiio
    from natron_layer import compat

    checker = node(app, "net.sf.openfx.CheckerBoardPlugin", (("extent", "format"),
                                                             ("NatronParamFormatChoice", "square_256")))
    reference = render(app, checker, "zd_checker")
    z = gizmo(app, "ZDefocus", checker)
    depth = z.getParam("depthChannel")
    label = list(depth.getOptions())[depth.get()]
    say(label == "B." + COLOUR + ".A", "ZDefocus reads the depth from alpha until a depth.Z is there: " + label)
    say(max_diff(render(app, z, "zd_in_focus"), reference) < 1e-5,
        "depth at the focal point (alpha 1, focal point 1): the image stays sharp, unchanged")
    for param, value in (("focalPoint", 101.0), ("size", 10.0), ("maximum", 8.0)):
        z.getParam(param).setValue(value)
    by_hand = node(app, "net.sf.cimg.CImgBlur", (("size", (8.0, 8.0)), ("filter", "gaussian"), ("boundary", "nearest"),
                                                 ("expandRoD", False)), (checker,))
    say(max_diff(render(app, z, "zd_far"), render(app, by_hand, "zd_far_hand")) < 2e-4,
        "far from the focal point: the maximum blur, as Natron's CImg Blur of 8 pixels set up by hand")
    for param, value in (("focalPoint", 1.1), ("size", 10.0), ("maximum", 10.0)):
        z.getParam(param).setValue(value)
    small = node(app, "net.sf.cimg.CImgBlur", (("size", (2.0, 2.0)), ("filter", "gaussian"), ("boundary", "nearest"),
                                               ("expandRoD", False)), (checker,))
    average = node(app, "net.sf.openfx.MergePlugin", (("operation", "average"),), (checker, small))
    say(max_diff(render(app, z, "zd_between"), render(app, average, "zd_between_hand")) < 2e-3,
        "between two slices (blur 1 px, half-way to the 2 px slice): half sharp, half the 2 px blur, weights adding "
        "up to 1")
    z.getParam("focalPoint").setValue(1.5)
    z.getParam("size").setValue(4.0)
    z.getParam("maximum").setValue(8.0)
    compat.set_node_value(z, "output", "focal plane setup")
    setup = render(app, z, "zd_setup")
    say(setup is not None and near(px(setup, 10, 10)[:3], (0.25, 0.25, 0.25), 1e-4),
        "Output focal plane setup shows the blur as grey: |1 - 1.5| x 4 / 8 = 0.25: " + str(rounded(px(setup, 10, 10))))
    # A CG render's depth.Z is picked by itself when connected.
    exr = os.path.join(folder("tools"), "zd_depth.exr")
    spec = oiio.ImageSpec(64, 64, 5, oiio.FLOAT)
    spec.channelnames = ("R", "G", "B", "A", "depth.Z")
    image = oiio.ImageBuf(spec)
    oiio.ImageBufAlgo.fill(image, (0.3, 0.4, 0.5, 1.0, 5.0))
    image.write(exr)
    read = app.createReader(exr.replace("\\", "/"))
    z2 = gizmo(app, "ZDefocus", read)
    label = list(z2.getParam("depthChannel").getOptions())[z2.getParam("depthChannel").get()]
    say(label == "B.depth.Z", "connected to an EXR with depth.Z, ZDefocus reads depth.Z (as Nuke's): " + label)
    compat.set_node_value(z2, "output", "focal plane setup")
    z2.getParam("focalPoint").setValue(3.0)
    value = px(render(app, z2, "zd_depthz"), 5, 5)[0]
    say(abs(value - 1.0) < 1e-4, "its blur from depth.Z = 5 with the focal point at 3: |5 - 3| x 10 / 20 = 1: "
        + str(round(value, 4)))


def check_edge_extend(say, app):
    from natron_layer import compat

    clear_black = constant(app, (0.0, 0.0, 0.0, 0.0))
    def rectangle(left, colour, source):
        return node(app, "net.sf.openfx.Rectangle", (
            ("extent", "size"), ("bottomLeft", (left, 96.0)), ("size", (32.0, 64.0)), ("color0", (0.0, 0.0, 0.0, 0.0)),
            ("color1", colour), ("softness", 0.0)), (source,))

    red = rectangle(96.0, (1.0, 0.0, 0.0, 1.0), clear_black)
    both = rectangle(128.0, (0.0, 1.0, 0.0, 1.0), red)
    source = render(app, both, "ee_source")
    ee = gizmo(app, "EdgeExtend", both)
    # EdgeExtend's output is unpremultiplied (the extended colour, the input's alpha): read its colour as it is and
    # its alpha apart (a Write would multiply the colour by the alpha).
    premultiplied = ("outputPremult", "Premultiplied")
    raw = node(app, "net.sf.openfx.ShufflePlugin", (("outputA", "1"), premultiplied), (ee,))
    alpha = node(app, "net.sf.openfx.ShufflePlugin", (
        ("outputR", "B." + COLOUR + ".A"), ("outputG", "B." + COLOUR + ".A"), ("outputB", "B." + COLOUR + ".A"),
        ("outputA", "1"), premultiplied), (ee,))
    out, out_alpha = render(app, raw, "ee_out"), render(app, alpha, "ee_alpha")
    inside, left, far_left, right = px(out, 110, 128), px(out, 92, 128), px(out, 70, 128), px(out, 164, 128)
    alphas = [px(out_alpha, x, 128)[0] for x in (110, 92, 70, 164)]
    say(near(inside[:3], (1.0, 0.0, 0.0), 1e-4) and alphas == [1.0, 0.0, 0.0, 0.0],
        "EdgeExtend leaves the inside as it is and keeps the input's alpha: " + str(rounded(inside)) + " "
        + str(alphas))
    say(left[0] > 0.98 and left[1] < 0.02, "4 px left of the shape: the red pushed out: " + str(rounded(left)))
    say(far_left[0] > 0.85 and far_left[0] > 5 * far_left[1],
        "26 px out: mostly red (the widest fills reach the green half too): " + str(rounded(far_left)))
    say(right[1] > 0.98 and right[0] < 0.02, "4 px right of the green half: green: " + str(rounded(right)))
    compat.set_node_value(ee, "premultiply", True)
    say(max_diff(render(app, ee, "ee_premult"), source) < 1e-5,
        "Premultiply on gives the input back (the extended colour where the alpha is 0 is multiplied away)")


def check_chromatic_aberration(say, app):
    from natron_layer import compat

    base = constant(app, (0.0, 0.0, 0.0, 1.0))
    grad = ramp(app, base)
    source = render(app, grad, "ca_source")
    ca = gizmo(app, "ChromaticAberration", grad)
    out = render(app, ca, "ca_out")
    red = node(app, "net.sf.openfx.LensDistortion", (("model", "nuke"), ("k1", 0.003)), (grad,))
    blue = node(app, "net.sf.openfx.LensDistortion", (("model", "nuke"), ("k1", -0.003)), (grad,))
    for each, letter in ((red, "R"), (blue, "B")):
        for other in "RGBA":
            compat.set_node_value(each, "NatronOfxParamProcess" + other, other == letter)
    say(max_diff(out, source, [1, 3]) == 0.0, "ChromaticAberration leaves green and alpha as they are")
    say(max_diff(out, render(app, red, "ca_red_hand"), [0]) < 1e-5 and
        max_diff(out, render(app, blue, "ca_blue_hand"), [2]) < 1e-5,
        "its red and blue are Natron's LensDistortion (k1 +0.003 and -0.003) set up by hand")
    edge = px(out, 2, 128)
    say(abs(px(out, 128, 128)[0] - px(source, 128, 128)[0]) < 1e-3 and edge[0] != edge[2],
        "no shift at the centre, the colours split at the edge: " + str(rounded(edge)))
    ca.getParam("amount").setValue(0.0)
    say(max_diff(render(app, ca, "ca_zero"), source) == 0.0, "Amount 0 gives the image back")


def check_vignette(say, app):
    from natron_layer import compat

    grey = constant(app, (0.5, 0.5, 0.5, 1.0))
    v = gizmo(app, "Vignette", grey, (("softness", 0.0), ("scale", 0.5)))
    out = render(app, v, "vig_square")
    centre, corner, a, b = px(out, 128, 128), px(out, 2, 2), px(out, 40, 128), px(out, 215, 128)
    say(near(centre, (0.5, 0.5, 0.5, 1.0)) and near(corner, (0.35, 0.35, 0.35, 1.0)),
        "Vignette (amount 0.3): the centre as it was, the corner x 0.7: " + str(rounded(centre)) + " "
        + str(rounded(corner)))
    say(near(a, b), "left and right alike")
    wide = constant(app, (0.5, 0.5, 0.5, 1.0), "PC_Video")
    w = gizmo(app, "Vignette", wide, (("softness", 0.0), ("scale", 1.0)))
    out = render(app, w, "vig_wide")
    inside = [px(out, 5, 240), px(out, 634, 240), px(out, 320, 5), px(out, 320, 474)]
    say(all(near(p, (0.5, 0.5, 0.5, 1.0)) for p in inside) and near(px(out, 5, 5), (0.35, 0.35, 0.35, 1.0)),
        "on a 640 x 480 input the ellipse fits its format (edges' middles inside, corners darkened)")
    behind = gizmo(app, "ChromaticAberration", grey, (("amount", 0.0),))
    chained = gizmo(app, "Vignette", behind, (("softness", 0.0), ("scale", 0.5)))
    out = render(app, chained, "vig_chained")
    say(near(px(out, 128, 128), (0.5, 0.5, 0.5, 1.0)) and near(px(out, 2, 2), (0.35, 0.35, 0.35, 1.0)),
        "fed by another gizmo (a Group, whose format Natron reports as the project's HD), it still fits the 256 x 256 "
        "picture: " + str(rounded(px(out, 2, 2))))
    compat.set_node_value(v, "amount", 0.0)
    say(max_diff(render(app, v, "vig_zero"), render(app, grey, "vig_grey")) == 0.0, "Amount 0 gives the image back")


def check_stmap(say, app):
    from natron_layer import compat

    square = constant(app, (0.0, 0.0, 0.0, 1.0))
    st = gizmo(app, "STMapIdentity", square)
    out = render(app, st, "st_square")
    say(near(px(out, 0, 10), (0.5 / 256, 10.5 / 256, 0.0, 1.0), 1e-5) and
        near(px(out, 255, 255), (255.5 / 256, 255.5 / 256, 0.0, 1.0), 1e-5),
        "STMapIdentity on 256 x 256: R = (x + 0.5) / 256, G = (y + 0.5) / 256, B 0, A 1: "
        + str(rounded(px(out, 255, 255), 5)))
    wide = constant(app, (0.0, 0.0, 0.0, 1.0), "PC_Video")
    st2 = gizmo(app, "STMapIdentity", wide)
    out2 = render(app, st2, "st_wide")
    say(near(px(out2, 639, 479), (639.5 / 640, 479.5 / 480, 0.0, 1.0), 5e-4),
        "on 640 x 480 (within the EXR's half floats): " + str(rounded(px(out2, 639, 479), 5)))
    checker = node(app, "net.sf.openfx.CheckerBoardPlugin", (("extent", "format"),
                                                             ("NatronParamFormatChoice", "square_256")))
    uv = gizmo(app, "STMapIdentity", checker)
    warp = node(app, "net.sf.openfx.STMap", (("filter", "impulse"),), (uv, checker))
    say(max_diff(render(app, warp, "st_identity"), render(app, checker, "st_checker")) < 1e-5,
        "Natron's STMap through it gives the picture back unchanged (the identity)")
    compat.set_node_value(warp, "filter", "cubic")


def build_fallback_comp(say, app):
    """Every gizmo with its own settings and a Write, rendered, then the comp saved for project_checks.py (no layer)."""
    from natron_layer import compat

    clear(app)
    ref = folder("fallback_ref")
    grey = constant(app, (0.18, 0.18, 0.18, 1.0), name="Grey")
    checker = node(app, "net.sf.openfx.CheckerBoardPlugin", (("extent", "format"),
                                                             ("NatronParamFormatChoice", "square_256")), name="Checker")
    cases = (
        ("Grain", grey, (("seed", 7), ("intensity", (0.05, 0.05, 0.05)))),
        ("ZDefocus", checker, (("focalPoint", 1.3), ("size", 10.0), ("maximum", 6.0))),
        ("EdgeExtend", checker, (("size", 0.5),)),
        ("ChromaticAberration", checker, (("amount", 0.01),)),
        ("Vignette", checker, (("amount", 0.5), ("scale", 1.0))),
        ("STMapIdentity", checker, ()),
    )
    writers = []
    for name, source, values in cases:
        made = gizmo(app, name, source, values)
        made.setScriptName("My" + name)
        write = writer(app, made, os.path.join(ref, name + ".####.exr"), name="Write" + name)
        app.render(write, 1, 1)
        writers.append({"writer": "Write" + name, "gizmo": "My" + name,
                        "reference": os.path.join(ref, name + ".0001.exr").replace("\\", "/")})
    project = os.path.join(OUT, "gizmos_fallback.ntp")
    saved = compat.save_temp_project(app, project)
    text = open(project, encoding="utf-8").read() if saved else ""
    say(saved and all(w["gizmo"] in text for w in writers) and "layer.gizmo.Grain" in text,
        "a comp of every gizmo saved (each with its inner nodes and its PyPlug's name) for the run without the layer")
    JOBS.append({"name": "gizmos", "project": project.replace("\\", "/"), "writers": writers, "frame": 1,
                 "tolerance": 1e-5, "groups": [w["gizmo"] for w in writers]})
    clear(app)


# --- Item 6: workflow scripts ---


def layered_exr(name, channels, values, size=64):
    import OpenImageIO as oiio

    path = os.path.join(folder("tools"), name)
    spec = oiio.ImageSpec(size, size, len(channels), oiio.FLOAT)
    spec.channelnames = tuple(channels)
    image = oiio.ImageBuf(spec)
    oiio.ImageBufAlgo.fill(image, tuple(values))
    image.write(path)
    return path.replace("\\", "/")


def check_extract_layers(say, app):
    from natron_layer import workflow

    path = layered_exr("layers.exr", ("R", "G", "B", "A", "diffuse.R", "diffuse.G", "diffuse.B", "specular.R",
                                      "specular.G", "specular.B", "depth.Z"),
                       (0.3, 0.4, 0.5, 1.0, 0.1, 0.2, 0.3, 0.01, 0.02, 0.03, 7.0))
    read = app.createReader(path)
    found = workflow.layers_of(app, read)
    say(sorted(found) == [("depth", ["Z"]), ("diffuse", ["R", "G", "B"]), ("specular", ["R", "G", "B"])],
        "the layers of a multi-layer EXR are read from Natron's own channel list: " + str(found))
    made = {s.getScriptName(): s for s in workflow.extract_layers(app, read)}
    say(sorted(made) == ["depth", "diffuse", "specular"], "Extract layers into Shuffles made one Shuffle per layer: "
        + ", ".join(sorted(made)))
    if sorted(made) == ["depth", "diffuse", "specular"]:
        diffuse, depth = px(render(app, made["diffuse"], "extract_diffuse"), 5, 5), px(render(app, made["depth"],
                                                                                               "extract_depth"), 5, 5)
        say(near(diffuse, (0.1, 0.2, 0.3, 1.0)) and near(depth, (7.0, 7.0, 7.0, 1.0)),
            "their pictures: diffuse's colour with the beauty's alpha, depth.Z in R, G and B: " + str(rounded(diffuse))
            + " " + str(rounded(depth)))


def check_select_and_merge(say, app):
    from natron_layer import compat, workflow

    clear(app)
    grades = [node(app, "net.sf.openfx.GradePlugin") for _ in range(3)]
    blur = node(app, "net.sf.cimg.CImgBlur")
    found = workflow.similar(app, grades[0], "class")
    say(sorted(n.getScriptName() for n in found) == sorted(g.getScriptName() for g in grades),
        "Select similar class: the three Grades, not the Blur (similar colour is checked in the window: headless, "
        "Natron's nodes have no colour)")
    merge = node(app, "net.sf.openfx.MergePlugin", (("operation", "over"),))
    steps = [workflow.cycle_merge([merge, blur], 1)[0][1], workflow.cycle_merge([merge], -1)[0][1],
             workflow.cycle_merge([merge], -1)[0][1]]
    compat.set_node_value(merge, "operation", "hypot")
    steps.append(workflow.cycle_merge([merge], 1)[0][1])
    say(steps == ["under", "over", "copy", "over"],
        "Merge operation cycling: over > under, back to over, back to copy (the end), and an operation off the list "
        "goes to over: " + str(steps))


def check_roto_link(say, app):
    from natron_layer import workflow

    clear(app)
    base = constant(app, (0.0, 0.0, 0.0, 0.0))
    roto = node(app, "fr.inria.built-in.Roto", (), (base,))
    shape = roto.getRotoContext().createBezier(10, 10, 1)
    for x, y in ((50, 10), (50, 50), (10, 50)):
        shape.addControlPoint(x, y)
    shape.setCurveFinished(True)
    tracker = node(app, "fr.inria.built-in.Tracker", (), (base,))
    track = tracker.getTrackerContext().createTrack()
    centre = track.getParam("centerPoint")
    for frame in range(1, 6):
        centre.setValueAtTime(100.0 + 10 * frame, frame, 0)
        centre.setValueAtTime(50.0 + 5 * frame, frame, 1)
    after = node(app, "net.sf.openfx.GradePlugin", (), (roto,), name="AfterRoto")
    follow = workflow.link_roto_to_track(app, roto, tracker, reference=1)
    translate = follow.getParam("translate")
    at3 = (translate.getValueAtTime(3, 0), translate.getValueAtTime(3, 1))
    say(follow.getInput(0).getScriptName() == roto.getScriptName() and after.getInput(0).getScriptName()
        == follow.getScriptName() and near(at3, (20.0, 10.0)),
        "Link roto to track: a Transform inserted after the Roto (what it fed now fed by it) moves with the track "
        "since frame 1 (frame 3: +20, +10): " + str(rounded(at3)))
    out = render(app, after, "roto_linked_f3", 3)
    say(out is not None and px(out, 35, 25)[3] > 0.99 and px(out, 12, 12)[3] < 0.01,
        "and the shape renders moved on frame 3")
    baked = workflow.bake_expressions([follow], 1, 5)
    from natron_layer import compat

    at5 = (translate.getValueAtTime(5, 0), translate.getValueAtTime(5, 1))
    say(baked == 2 and not compat.expression_of(translate, 0) and translate.getIsAnimated(0)
        and near(at5, (40.0, 20.0)),
        "Bake expressions to keyframes: the expressions became keyframes (frame 5: +40, +20): " + str(rounded(at5)))


def check_collect(say, app):
    from natron_layer import compat, workflow

    clear(app)
    plate = constant(app, (0.25, 0.5, 0.75, 1.0))
    source_folder = folder("collect_source")
    write = writer(app, plate, os.path.join(source_folder, "plate.####.exr"), 1, 3)
    app.render(write, 1, 3)
    clear(app)
    pattern = os.path.join(source_folder, "plate.####.exr").replace("\\", "/")
    read = app.createReader(pattern)
    read.setScriptName("PlateRead")
    before = str(read.getParam("filename").get())
    target = folder("collected")
    report = workflow.collect_files(app, target)
    copied = sorted(os.path.basename(p) for p in report.copied)
    say(copied == ["plate.0001.exr", "plate.0002.exr", "plate.0003.exr"] and not report.missing,
        "Collect files copied the sequence's three frames into the folder's footage/PlateRead: " + str(copied))
    text = open(report.project, encoding="utf-8").read() if os.path.isfile(report.project) else ""
    say("[Project]/footage/PlateRead/plate.####.exr" in text and os.path.dirname(report.project) == target.replace(
        "\\", "/"), "its copy of the comp, in that folder, reads them as [Project]/footage/... (Natron's [Project] is "
        "the folder a comp opens from; rendered without the layer below)")
    say(str(read.getParam("filename").get()) == before and not compat.project_file(app),
        "the open comp still reads the original files and wasn't saved anywhere")
    JOBS.append({"name": "collected", "project": report.project, "add_writer": "PlateRead", "frame": 2,
                 "expected": [0.25, 0.5, 0.75, 1.0], "tolerance": 1e-4,
                 "file_starts": ["PlateRead", "[Project]/footage/PlateRead/"]})
    clear(app)


def check_flipbook(say, app):
    from natron_layer import compat, workflow

    clear(app)
    plate = constant(app, (0.6, 0.3, 0.1, 1.0), name="FlipPlate")
    grade = node(app, "net.sf.openfx.GradePlugin", (("multiply", (0.5, 0.5, 0.5, 1.0)),), (plate,), name="FlipGrade")
    renderer = compat.renderer_executable()
    say(renderer is not None, "NatronRenderer is found next to this Natron: " + str(renderer))
    if renderer is None:
        return
    started = workflow.flipbook(app, grade, 1, 2, player="none", movie=False, folder=folder("flipbook_frames"),
                                wait=True, renderer=renderer)
    result = started.get("result", {})
    frames = result.get("frames", [])
    say(result.get("ok") and len(frames) == 2 and near(px(frames[1], 4, 4), (0.3, 0.15, 0.05, 1.0)),
        "Flipbook: NatronRenderer rendered the selected node's frames 1-2 from a copy of the comp (no player in the "
        "test): " + (str(rounded(px(frames[1], 4, 4))) if len(frames) == 2 else str(result.get("error", ""))[:300]))
    started = workflow.flipbook(app, grade, 1, 3, player="none", movie=True, folder=folder("flipbook_movie"),
                                wait=True, renderer=renderer)
    movie = started["job"]["output"]
    say(started.get("result", {}).get("ok") and os.path.getsize(movie) > 1000,
        "and as an MP4 for the system's player when RV isn't on the PC: " + os.path.basename(movie)
        + " (" + (str(os.path.getsize(movie)) if os.path.isfile(movie) else "none") + " bytes)")
    say(workflow.find_rv() is None or os.path.isfile(workflow.find_rv()),
        "RV on this PC: " + str(workflow.find_rv() or "not found (the flipbook plays the MP4 in the system's player)"))
    clear(app)


# --- Item 7: expressions and ToolSet recipes ---


def check_expressions(say, app):
    from natron_layer import expressions

    clear(app)
    recipes = expressions.recipes()
    say(len(recipes) >= 15 and all(r.text() for r in recipes), "the expression recipes read and all make valid "
        "Python (" + str(len(recipes)) + ")")
    plate = constant(app, (0.0, 0.0, 0.0, 1.0))
    animated = node(app, "net.sf.openfx.TransformPlugin", (), (plate,), name="Animated")
    translate = animated.getParam("translate")
    for frame in range(1, 21):
        translate.setValueAtTime(2.0 * frame, frame, 0)
        translate.setValueAtTime(3.0 * frame, frame, 1)
    other = node(app, "net.sf.openfx.TransformPlugin", (("translate", (3.0, 4.0)),), (plate,), name="Other")
    del other
    cases = (
        ("frame", {}, 7, 7.0),
        ("frame_offset", {"offset": 3}, 7, 10.0),
        ("hold", {"frame": 5}, 12, 10.0),
        ("time_offset", {"offset": 3}, 12, 18.0),
        ("loop", {"first": 1, "length": 4}, 7, 6.0),
        ("ping_pong", {"first": 1, "length": 4}, 7, 6.0),
        ("ping_pong", {"first": 1, "length": 4}, 4, 8.0),
        ("sine", {"amplitude": 2, "period": 8, "phase": 0, "offset": 1}, 2, 3.0),
        ("ramp", {"start": 10, "end": 20, "from_value": 0, "to_value": 1}, 15, 0.5),
        ("ramp", {"start": 10, "end": 20, "from_value": 0, "to_value": 1}, 25, 1.0),
        ("on_from", {"frame": 10}, 9, 0.0),
        ("on_from", {"frame": 10}, 10, 1.0),
        ("link", {"node": "Other", "param": "translate"}, 1, 3.0),
        ("link_opposite", {"node": "Other", "param": "translate"}, 1, -3.0),
        ("link_at_frame", {"node": "Animated", "param": "translate"}, 1, None),
        ("input_width", {}, 1, 256.0),
        ("first_frame", {}, 1, None),
    )
    results = []
    for number, (recipe, values, frame, wanted) in enumerate(cases):
        target = node(app, "net.sf.openfx.TransformPlugin", (), (plate,), name="Target" + str(number))
        param = target.getParam("translate")
        if recipe in ("hold", "time_offset", "loop", "ping_pong"):
            for f in range(1, 21):
                param.setValueAtTime(2.0 * f, f, 0)
                param.setValueAtTime(3.0 * f, f, 1)
        expressions.apply(target, "translate", recipe, values)
        got = param.getValueAtTime(frame, 0)
        if recipe == "link_at_frame":
            wanted = translate.getValueAtTime(1001, 0)  # the default field: frame 1001 of Animated (held at 40)
        if recipe == "first_frame":
            wanted = float(app.getProjectParam("frameRange").getValue(0))
        results.append((recipe, frame, round(got, 4), wanted, abs(got - wanted) < 1e-6))
    bad = [r for r in results if not r[4]]
    say(not bad, "each recipe gives its value on its frame (" + str(len(results)) + " checked)"
        + ("; wrong: " + str(bad) if bad else ""))
    wiggle = node(app, "net.sf.openfx.TransformPlugin", (), (plate,), name="Wiggle")
    expressions.apply(wiggle, "translate", "wiggle", {"amplitude": 5, "frequency": 0.2})
    values = [wiggle.getParam("translate").getValueAtTime(f, 0) for f in range(1, 30)]
    say(all(abs(v) <= 5.5 for v in values) and len({round(v, 3) for v in values}) > 20,
        "Wiggle wobbles within its amplitude: " + str(rounded(values[:4], 3)))
    rand = node(app, "net.sf.openfx.TransformPlugin", (), (plate,), name="Random")
    expressions.apply(rand, "translate", "random", {"low": 2, "high": 3})
    p = rand.getParam("translate")
    first, again, second = p.getValueAtTime(4, 0), p.getValueAtTime(4, 0), p.getValueAtTime(5, 0)
    say(2.0 <= first < 3.0 and first == again and first != second, "Random per frame: in [2, 3), the same on a frame, "
        "another on the next: " + str(rounded((first, second))))
    lit = constant(app, (0.0, 0.0, 0.0, 1.0))
    expressions.apply(lit, "color", "frame", dimensions=[0])
    value = px(render(app, lit, "expr_frame", 5), 3, 3)[0]
    say(abs(value - 5.0) < 1e-6, "and they render: a Constant's red set to Frame number is 5 on frame 5")
    clear(app)


def check_toolset_recipes(say, app):
    from natron_layer import compat, toolset_recipes, toolsets

    clear(app)
    names = list(toolset_recipes.RECIPES)
    files = [os.path.join(str(toolsets.studio_folder()), toolset_recipes.file_name(n)) for n in names]
    say(all(os.path.isfile(f) and toolsets.looks_like_natron_nodes(open(f, encoding="utf-8").read()) for f in files),
        "each studio ToolSet has its file of Natron's copied nodes in ext/toolsets: "
        + ", ".join(os.path.basename(f) for f in files))
    listed = [t.name for t in toolsets.all_toolsets() if t.place == "Studio"]
    say(sorted(listed) == sorted(names), "the ToolSets menu lists them under Studio, by their titles: "
        + ", ".join(listed))
    # The CG beauty rebuild on a render with Cycles' passes (a view layer's name before each pass, as Blender writes).
    passes = {"DiffDir": 0.1, "DiffInd": 0.05, "DiffCol": 0.8, "GlossDir": 0.2, "GlossInd": 0.1, "GlossCol": 0.5,
              "Emit": 0.03}
    beauty = (0.15 * 0.8) + (0.3 * 0.5) + 0.03
    channels, values = ["R", "G", "B", "A"], [beauty, beauty, beauty, 0.75]
    for name, value in passes.items():
        for letter in "RGB":
            channels.append("ViewLayer." + name + "." + letter)
            values.append(value)
    path = layered_exr("cycles_passes.exr", channels, values)
    read = app.createReader(path)
    made = toolset_recipes.cg_beauty_rebuild(app)
    report = toolsets.after_paste(app, list(made.values()), read)
    say(sorted(report.matched) == sorted(passes) and sorted(report.missing) == ["Env", "TransCol", "TransDir",
                                                                                 "TransInd", "VolumeDir", "VolumeInd"],
        "the rebuild's AOV Shuffles found the passes (ViewLayer.DiffDir...), the ones the render lacks are black: "
        + report.summary("CG beauty rebuild"))
    out = render(app, made["ToolSetOut"], "rebuild_out")
    check = render(app, made["Check"], "rebuild_check")
    say(near(px(out, 5, 5), (beauty, beauty, beauty, 0.75), 1e-3) and max(stats(check)["max"][:3]) < 1e-5,
        "and add up to the beauty ((0.1 + 0.05) x 0.8 + (0.2 + 0.1) x 0.5 + 0.03 = 0.3), alpha the beauty's, the "
        "Check black: " + str(rounded(px(out, 5, 5))) + ", Check " + str(rounded(px(check, 5, 5), 6)))
    clear(app)
    checker = node(app, "net.sf.openfx.CheckerBoardPlugin", (("extent", "format"),
                                                             ("NatronParamFormatChoice", "square_256")))
    made = toolset_recipes.grain_and_lens(app)
    compat.connect(made["ToolSetIn"], 0, checker)
    first = render(app, made["ToolSetOut"], "grain_and_lens_recipe", 1, sub="toolsets_ref")
    again = render(app, made["ToolSetOut"], "grain_and_lens_again", 1)
    s, c = stats(first), stats(render(app, checker, "grain_and_lens_checker"))
    say(max_diff(first, again) == 0.0 and all(abs(s["avg"][i] - c["avg"][i]) < 0.05 for i in range(3)),
        "the grain and lens stack renders, the same twice, near the checker's average: " + str(rounded(s["avg"])))
    with open(os.path.join(OUT, "toolset_references.json"), "w", encoding="utf-8") as file:
        json.dump({"Grain and lens": first}, file)
    clear(app)


def run(say, app):
    if not OUT:
        say(False, "NATRON_LAYER_SMOKE_OUT is set (the tools' checks write their renders there)")
        return
    clear(app)
    for title, check in (("the gizmos' registration", check_registered), ("Grain", check_grain),
                         ("ZDefocus", check_zdefocus), ("EdgeExtend", check_edge_extend),
                         ("ChromaticAberration", check_chromatic_aberration), ("Vignette", check_vignette),
                         ("STMapIdentity", check_stmap), ("the gizmos' comp", build_fallback_comp),
                         ("Extract layers", check_extract_layers), ("Select similar and Merge cycling",
                                                                     check_select_and_merge),
                         ("Link roto to track", check_roto_link), ("Collect files", check_collect),
                         ("Flipbook", check_flipbook), ("the expression recipes", check_expressions),
                         ("the ToolSet recipes", check_toolset_recipes)):
        section(say, title, check, app)
    with open(os.path.join(OUT, "project_jobs.json"), "w", encoding="utf-8") as file:
        json.dump(JOBS, file, indent=1)
