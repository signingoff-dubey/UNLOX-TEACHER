"""Generic 3D scene builder for any topic, run inside Blender. The planner writes a scene as JSON data (never code):

  {"environment": "space|studio|sky|lab|underwater",
   "objects": [{"id", "kind", "color", "finish", "x", "y", "z", "size", "label", "param"}],
   "shots": [{"camera": "wide|close|orbit|top|side|low", "focus": object id or "",
              "actions": [{"do", "target", "with", "x", "y", "z", "amount"}],
              "start": frame, "frames": int}]}

Every field is validated by the caller (planner.py); this module trusts its input but still clamps what it uses.
Labels arrive as pre-rendered PNG masks (Windows text shaping handles Indic scripts) and face the camera."""
import math
import bpy
from mathutils import Vector

from templates import (srgb, sphere, ring, empty, earth_material, space_world, studio_world, smooth_all, key,
                       ELEMENTS)

PALETTE = {"red": "#E04B3A", "orange": "#F08A2B", "yellow": "#F2C641", "green": "#4CAF50", "teal": "#26A69A",
           "blue": "#3D7BD9", "sky": "#7EC8F0", "purple": "#8E5BD9", "pink": "#EC7FB0", "white": "#F2F2F2",
           "grey": "#9AA0A8", "black": "#2B2B2E", "brown": "#8B5A3C", "gold": "#D4A73A", "silver": "#C8CCD2",
           "skin": "#C68E6A"}
FINISH = {"matte": (0.8, 0.0, 0.0, 0.0), "glossy": (0.25, 0.0, 0.0, 0.0), "metal": (0.3, 1.0, 0.0, 0.0),
          "glass": (0.05, 0.0, 0.0, 0.85), "glow": (0.5, 0.0, 2.0, 0.0)}
CPK = {"H": "#F2F2F2", "C": "#3A3A3E", "O": "#E04B3A", "N": "#3D7BD9", "Cl": "#4CAF50", "Na": "#8E5BD9",
       "S": "#F2C641", "P": "#F08A2B", "Fe": "#B0582E", "Mg": "#7FD17F", "K": "#9A6BD9", "Ca": "#9AA0A8"}
MOLECULES = {  # atom symbol, x, y, z (angstrom-ish); bonds by index
    "H2O": ([("O", 0, 0, 0), ("H", 0.76, 0, 0.59), ("H", -0.76, 0, 0.59)], [(0, 1), (0, 2)]),
    "CO2": ([("C", 0, 0, 0), ("O", 1.16, 0, 0), ("O", -1.16, 0, 0)], [(0, 1), (0, 2)]),
    "O2": ([("O", 0.6, 0, 0), ("O", -0.6, 0, 0)], [(0, 1)]),
    "H2": ([("H", 0.37, 0, 0), ("H", -0.37, 0, 0)], [(0, 1)]),
    "N2": ([("N", 0.55, 0, 0), ("N", -0.55, 0, 0)], [(0, 1)]),
    "CH4": ([("C", 0, 0, 0), ("H", 0.63, 0.63, 0.63), ("H", -0.63, -0.63, 0.63), ("H", -0.63, 0.63, -0.63),
             ("H", 0.63, -0.63, -0.63)], [(0, 1), (0, 2), (0, 3), (0, 4)]),
    "NH3": ([("N", 0, 0, 0.1), ("H", 0.94, 0, -0.3), ("H", -0.47, 0.81, -0.3), ("H", -0.47, -0.81, -0.3)],
            [(0, 1), (0, 2), (0, 3)]),
    "NACL": ([("Na", -1.2, 0, 0), ("Cl", 1.2, 0, 0)], [(0, 1)]),
    "HCL": ([("H", -0.64, 0, 0), ("Cl", 0.64, 0, 0)], [(0, 1)]),
    "C6H6": ([("C", 1.4 * math.cos(a), 1.4 * math.sin(a), 0) for a in [i * math.pi / 3 for i in range(6)]] +
             [("H", 2.48 * math.cos(a), 2.48 * math.sin(a), 0) for a in [i * math.pi / 3 for i in range(6)]],
             [(i, (i + 1) % 6) for i in range(6)] + [(i, i + 6) for i in range(6)]),
}
ARROW_DIRS = {"right": (1, 0, 0), "left": (-1, 0, 0), "up": (0, 0, 1), "down": (0, 0, -1), "toward": (0, -1, 0),
              "away": (0, 1, 0)}


# ---------------------------------------------------------------- materials

def make_material(color, finish, name):
    rough, metal, emit, trans = FINISH.get(finish, FINISH["matte"])
    m = bpy.data.materials.new(name)
    b = m.node_tree.nodes["Principled BSDF"]
    col = srgb(PALETTE.get(color, color if str(color).startswith("#") else PALETTE["grey"]))
    b.inputs["Base Color"].default_value = col
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Emission Color"].default_value = col
    b.inputs["Emission Strength"].default_value = emit
    if trans:
        b.inputs["Alpha"].default_value = 1 - trans * 0.75
        _blend(m)
    return m


def _blend(m):
    for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
        try:
            setattr(m, attr, val)
        except (AttributeError, TypeError):
            pass


# ---------------------------------------------------------------- geometry kinds

def _prim(op, **kw):
    op(**kw)
    ob = bpy.context.active_object
    if ob.type == "MESH":
        bpy.ops.object.shade_smooth()
    return ob


def _cyl_between(a, b, r, mat):
    a, b = Vector(a), Vector(b)
    d = b - a
    ob = _prim(bpy.ops.mesh.primitive_cylinder_add, radius=r, depth=d.length, vertices=24, location=(a + b) / 2)
    ob.rotation_euler = Vector((0, 0, 1)).rotation_difference(d).to_euler()
    ob.data.materials.append(mat)
    return ob


def build_kind(o, mat):
    """Geometry for one object, centred on the origin, about `size` across. Returns the mesh objects."""
    k, s, p = o["kind"], o["size"], str(o.get("param", "")).strip()
    parts = []
    if k in ("sphere", "planet", "star"):
        m = mat
        if k == "planet":
            m = {"earth": earth_material()}.get(p.lower(), mat)
            if p.lower() in ("mars", "jupiter", "moon", "venus", "saturn", "mercury", "neptune", "uranus"):
                col = {"mars": "#C1440E", "jupiter": "#D8B48C", "moon": "#A8A8A8", "venus": "#D9B47A", "saturn": "#E3CB8F",
                       "mercury": "#9C8F86", "neptune": "#4E6FD8", "uranus": "#8FD3DB"}[p.lower()]
                m = make_material(col, "matte", f"{o['id']}_planet")
        parts.append(sphere(o["id"] + "_geo", s / 2, mat=m, shadow=k != "star"))
        if k == "planet" and p.lower() == "saturn":
            r = ring(o["id"] + "_ring", s * 0.9, s * 0.12, make_material("#CDB685", "matte", "satring"), rot=(math.radians(70), 0, 0))
            r.scale.z = 0.08
            parts.append(r)
        if k == "star" and bpy.context.scene.get("env") == "space":
            light = bpy.data.objects.new(o["id"] + "_light", bpy.data.lights.new(o["id"] + "_light", "POINT"))
            light.data.energy, light.data.shadow_soft_size = 4000 * max(s, 0.5) ** 2, s / 2
            bpy.context.scene.collection.objects.link(light)
            parts.append(light)
    elif k == "box":
        parts.append(_prim(bpy.ops.mesh.primitive_cube_add, size=s))
    elif k == "bar":                                  # chart bar standing on its base
        ob = _prim(bpy.ops.mesh.primitive_cube_add, size=1, location=(0, 0, s / 2))
        ob.scale = (0.5, 0.5, s)
        parts.append(ob)
    elif k == "cylinder":
        parts.append(_prim(bpy.ops.mesh.primitive_cylinder_add, radius=s / 2, depth=s, vertices=48))
    elif k == "cone":
        parts.append(_prim(bpy.ops.mesh.primitive_cone_add, radius1=s / 2, depth=s, vertices=48))
    elif k in ("torus", "ring"):
        parts.append(_prim(bpy.ops.mesh.primitive_torus_add, major_radius=s / 2, minor_radius=s * (0.15 if k == "torus" else 0.03),
                           major_segments=96, minor_segments=16))
    elif k == "plane":
        parts.append(_prim(bpy.ops.mesh.primitive_plane_add, size=s))
    elif k == "arrow":
        d = Vector(ARROW_DIRS.get(p.lower(), ARROW_DIRS["right"]))
        tip = d * s / 2
        parts.append(_cyl_between(-tip, tip * 0.55, s * 0.04, mat))
        head = _prim(bpy.ops.mesh.primitive_cone_add, radius1=s * 0.11, depth=s * 0.25, vertices=32, location=tip * 0.78)
        head.rotation_euler = Vector((0, 0, 1)).rotation_difference(d).to_euler()
        parts.append(head)
    elif k == "atom":
        z, n = ELEMENTS.get(p.lower(), ELEMENTS["carbon"])
        nuc_r = s * 0.12
        golden = math.pi * (3 - math.sqrt(5))
        pm, nm = make_material("#E04B3A", "glossy", "proton"), make_material("#B9C0CC", "glossy", "neutron")
        for i in range(z + n):
            y = 1 - 2 * (i + 0.5) / (z + n)
            r, th = math.sqrt(1 - y * y), golden * i
            parts.append(sphere(f"{o['id']}_n{i}", nuc_r * 0.45, (math.cos(th) * r * nuc_r, y * nuc_r, math.sin(th) * r * nuc_r),
                                pm if i < z else nm, 16))
        left, k_shell = z, 0
        em = make_material("#4FC3F7", "glow", "electron")
        lm = make_material("#7C8FBF", "glow", "shell")
        for cap in (2, 8, 8, 18):
            if left <= 0:
                break
            cnt = min(cap, left); left -= cap
            rad = s * (0.22 + 0.13 * k_shell)
            parts.append(ring(f"{o['id']}_shell{k_shell}", rad, s * 0.004, lm, rot=(math.radians(90), 0, 0)))
            spin = empty(f"{o['id']}_spin{k_shell}"); spin["linear"] = True; spin["spin_speed"] = 120 / (k_shell + 1)
            spin.rotation_euler.x = math.radians(90)
            for j in range(cnt):
                a = 2 * math.pi * j / cnt
                e = sphere(f"{o['id']}_e{k_shell}_{j}", s * 0.025, (rad * math.cos(a), rad * math.sin(a), 0), em, 12)
                e.parent = spin
            parts.append(spin)
            k_shell += 1
    elif k == "molecule":
        atoms, bonds = MOLECULES.get(p.upper().replace(" ", ""), (None, None))
        if atoms is None:                            # unknown formula: central atom with the rest around it
            import re
            syms = [sym for sym, c in re.findall(r"([A-Z][a-z]?)(\d*)", p or "H2O") for _ in range(int(c or 1))] or ["O"]
            heavy = next((i for i, a in enumerate(syms) if a != "H"), 0)
            syms.insert(0, syms.pop(heavy))
            golden = math.pi * (3 - math.sqrt(5))
            atoms = [(syms[0], 0, 0, 0)] + [(sym, 1.2 * math.cos(golden * i) * math.sqrt(1 - (1 - 2 * (i + .5) / (len(syms) - 1)) ** 2),
                                            1.2 * (1 - 2 * (i + .5) / (len(syms) - 1)),
                                            1.2 * math.sin(golden * i) * math.sqrt(1 - (1 - 2 * (i + .5) / (len(syms) - 1)) ** 2))
                                            for i, sym in enumerate(syms[1:])]
            bonds = [(0, i) for i in range(1, len(atoms))]
        span = max(max(abs(c) for c in a[1:]) for a in atoms) or 1
        f = s / 2 / (span + 0.6)
        bm = make_material("#C8CCD2", "glossy", "bond")
        for i, (sym, x, y, zz) in enumerate(atoms):
            parts.append(sphere(f"{o['id']}_{sym}{i}", f * (0.32 if sym == "H" else 0.48), (x * f, y * f, zz * f),
                                make_material(CPK.get(sym, "#EC7FB0"), "glossy", f"cpk_{sym}"), 32))
        for a, b in bonds:
            parts.append(_cyl_between([c * f for c in atoms[a][1:]], [c * f for c in atoms[b][1:]], f * 0.09, bm))
    elif k == "cell":
        mem = make_material("#7FD17F", "glass", "membrane")
        parts.append(sphere(o["id"] + "_membrane", s / 2, mat=mem))
        parts.append(sphere(o["id"] + "_nucleus", s * 0.17, (s * 0.05, 0, 0), make_material("#8E5BD9", "glossy", "nucleus")))
        mito = make_material("#F08A2B", "glossy", "mito")
        for i, (x, y, zz) in enumerate(((-0.22, 0.1, 0.05), (0.18, -0.2, -0.1), (-0.05, 0.25, -0.15), (0.2, 0.18, 0.15))):
            mo = sphere(f"{o['id']}_mito{i}", s * 0.06, (x * s, y * s, zz * s), mito, 24)
            mo.scale = (2.2, 1, 1); mo.rotation_euler = (0, i * 0.7, i * 1.3)
            parts.append(mo)
    elif k == "wave":
        ob = _prim(bpy.ops.mesh.primitive_grid_add, x_subdivisions=80, y_subdivisions=80, size=s)
        wm = ob.modifiers.new("Wave", "WAVE")
        wm.height, wm.width, wm.speed, wm.narrowness = s * 0.06, s * 0.12, 0.12, 1.5
        parts.append(ob)
    elif k == "spring":
        cu = bpy.data.curves.new(o["id"] + "_spring", "CURVE"); cu.dimensions = "3D"
        sp = cu.splines.new("POLY")
        turns, pts = 8, 240
        sp.points.add(pts - 1)
        for i in range(pts):
            t = i / (pts - 1)
            sp.points[i].co = (s * 0.18 * math.cos(t * turns * 2 * math.pi), s * 0.18 * math.sin(t * turns * 2 * math.pi), (t - 0.5) * s, 1)
        cu.bevel_depth = s * 0.015
        ob = bpy.data.objects.new(o["id"] + "_spring", cu); bpy.context.scene.collection.objects.link(ob)
        parts.append(ob)
    elif k == "leaf":
        lf = sphere(o["id"] + "_leaf", s / 2, mat=mat, segs=32)
        lf.scale = (0.45, 1.0, 0.06); lf.rotation_euler = (math.radians(70), 0, 0)      # face the camera
        parts.append(lf)
        parts.append(_cyl_between((0, -s * 0.18, -s * 0.52), (0, s * 0.15, s * 0.45), s * 0.012,
                                  make_material("#3E7B2E", "matte", "vein")))
    elif k == "tree":
        bark = make_material("#6B4630", "matte", "bark")
        parts.append(_cyl_between((0, 0, -s / 2), (0, 0, 0), s * 0.07, bark))
        for i, (x, y, zz, r) in enumerate(((0, 0, 0.12, 0.32), (0.2, 0.05, 0.02, 0.22), (-0.18, -0.06, 0.04, 0.24), (0.02, 0.15, 0.3, 0.2))):
            parts.append(sphere(f"{o['id']}_crown{i}", s * r, (x * s, y * s, zz * s), mat, 24))
    elif k == "cloud":
        white = make_material("#F4F6F8", "matte", "cloud")
        for i, (x, zz, r) in enumerate(((0, 0, 0.3), (-0.3, -0.06, 0.22), (0.3, -0.05, 0.24), (0.12, 0.12, 0.2))):
            parts.append(sphere(f"{o['id']}_puff{i}", s * r, (x * s, 0, zz * s), white, 24))
    elif k == "drop":
        dp = sphere(o["id"] + "_drop", s * 0.35, mat=mat, segs=32)
        parts.append(dp)
        tip = _prim(bpy.ops.mesh.primitive_cone_add, radius1=s * 0.3, depth=s * 0.5, vertices=32, location=(0, 0, s * 0.3))
        parts.append(tip)
    else:
        parts.append(sphere(o["id"] + "_geo", s / 2))
    for ob in parts:
        if ob.type in ("MESH", "CURVE") and not ob.data.materials:
            ob.data.materials.append(mat)
    return parts


# ---------------------------------------------------------------- environment

def environment(kind, radius, floor_z=0.0):
    """Exposure-safe lighting: a sun key + a softer sun fill and a dim coloured world; mid-tone floors."""
    if kind == "space":
        space_world()
    else:
        color = {"studio": "#1E2533", "sky": "#8DB8E0", "lab": "#9AA3AE", "underwater": "#0F4A5C"}.get(kind, "#1E2533")
        studio_world(color, {"sky": 0.55, "lab": 0.45}.get(kind, 0.35))
    for name, rot, energy in (("Key", (52, 0, 35), 2.6), ("Fill", (65, 0, -140), 0.7)):
        L = bpy.data.objects.new(name, bpy.data.lights.new(name, "SUN"))
        L.data.energy = energy * (0.6 if kind == "space" else 1.0)
        L.data.angle = math.radians(6)
        L.rotation_euler = [math.radians(a) for a in rot]
        bpy.context.scene.collection.objects.link(L)
    if kind in ("sky", "lab", "studio"):
        floor = _prim(bpy.ops.mesh.primitive_plane_add, size=radius * 12, location=(0, 0, floor_z))
        floor.name = "Floor"
        floor.data.materials.append(make_material({"sky": "#5E8C4C", "lab": "#7D8590", "studio": "#2A3242"}[kind], "matte", "floor"))


# ---------------------------------------------------------------- labels

def label(o, root, png, aspect, height, cam, lift):
    img = bpy.data.images.load(png)
    m = bpy.data.materials.new(o["id"] + "_label")
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img
    emit = nt.nodes.new("ShaderNodeEmission"); emit.inputs["Strength"].default_value = 1.0
    transp = nt.nodes.new("ShaderNodeBsdfTransparent")
    mixc = nt.nodes.new("ShaderNodeMix"); mixc.data_type = "RGBA"              # white text on a dark pill
    mixc.inputs[6].default_value = (0.02, 0.03, 0.05, 1); mixc.inputs[7].default_value = (1, 1, 1, 1)
    alpha = nt.nodes.new("ShaderNodeMath"); alpha.operation = "MAXIMUM"; alpha.inputs[1].default_value = 0.55
    shader = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(tex.outputs["Color"], mixc.inputs[0])
    nt.links.new(mixc.outputs[2], emit.inputs["Color"])
    nt.links.new(tex.outputs["Color"], alpha.inputs[0])
    nt.links.new(alpha.outputs[0], shader.inputs[0])
    nt.links.new(transp.outputs[0], shader.inputs[1]); nt.links.new(emit.outputs[0], shader.inputs[2])
    nt.links.new(shader.outputs[0], out.inputs[0])
    _blend(m)
    bpy.ops.mesh.primitive_plane_add(size=1)
    pl = bpy.context.active_object; pl.name = o["id"] + "_labelplane"
    pl.scale = (height * aspect, height, 1)
    pl.data.materials.append(m)
    pl.visible_shadow = False
    cl = pl.constraints.new("COPY_LOCATION"); cl.target = root; cl.use_offset = True
    pl.location = (0, 0, lift)
    cs = pl.constraints.new("COPY_SCALE"); cs.target = root; cs.use_offset = True; cs.use_add = False
    tr = pl.constraints.new("TRACK_TO"); tr.target = cam; tr.track_axis, tr.up_axis = "TRACK_Z", "UP_Y"
    return pl


# ---------------------------------------------------------------- build + animate

def build_scene(scene, shots, labels, fps):
    objs = {o["id"]: o for o in scene["objects"]}
    total = shots[-1]["start"] + shots[-1]["frames"]
    centre = sum((Vector((o["x"], o["y"], o["z"])) for o in objs.values()), Vector()) / max(len(objs), 1)
    radius = max([(Vector((o["x"], o["y"], o["z"])) - centre).length + o["size"] for o in objs.values()] + [2.0])
    floor_z = min(o["z"] - o["size"] / 2 for o in objs.values()) - 0.02 if objs else 0.0
    bpy.context.scene["env"] = scene.get("environment", "studio")
    environment(scene.get("environment", "studio"), radius, floor_z)

    roots, state = {}, {}
    for o in objs.values():
        root = empty(o["id"])
        root.location = (o["x"], o["y"], o["z"])
        mat = make_material(o["color"], o["finish"], o["id"] + "_mat")
        stretch = Vector((o.get("sx", 1), o.get("sy", 1), o.get("sz", 1)))
        for part in build_kind(o, mat):
            if part.parent is None:
                part.parent = root
                if stretch != Vector((1, 1, 1)):                 # planks, rods, walls
                    part.location = [a * b for a, b in zip(part.location, stretch)]   # element-wise
                    part.scale = [a * b for a, b in zip(part.scale, stretch)]
        roots[o["id"]] = root
        state[o["id"]] = {"loc": Vector(root.location), "rot": 0.0, "scale": 1.0, "mat": mat}

    def kloc(i, f, v): key(roots[i], "location", f, tuple(v))
    def kscale(i, f, v): key(roots[i], "scale", f, (v, v, v))
    def krot(i, f, v): key(roots[i], "rotation_euler", f, v, 2)

    appears = {a["target"] for s in shots for a in s["actions"] if a["do"] == "appear"}
    for i in roots:
        kloc(i, 0, state[i]["loc"]); krot(i, 0, 0.0)
        kscale(i, 0, 0.0 if i in appears else 1.0)
        if i in appears:
            state[i]["scale"] = 0.0
    for o in objs.values():                                  # built-in continuous motion (electron shells)
        for part in [c for c in roots[o["id"]].children_recursive if c.get("spin_speed")]:
            key(part, "rotation_euler", 0, 0.0, 2)
            key(part, "rotation_euler", total, math.radians(part["spin_speed"]) * total / fps, 2)

    for shot in shots:
        f0, n = shot["start"], shot["frames"]
        a0, a1 = f0 + 3, f0 + max(10, int(n * 0.55))
        for act in shot["actions"]:
            i, st, do, amt = act["target"], state[act["target"]], act["do"], act.get("amount", 0) or 0
            if do == "appear":
                kscale(i, a0, 0.0); kscale(i, a0 + 8, 1.12); kscale(i, a0 + 12, 1.0); st["scale"] = 1.0
            elif do == "disappear":
                kscale(i, a0, st["scale"]); kscale(i, a0 + 10, 0.0); st["scale"] = 0.0
            elif do == "move":
                kloc(i, a0, st["loc"]); st["loc"] = Vector((act["x"], act["y"], act["z"])); kloc(i, a1, st["loc"])
            elif do == "rotate":
                krot(i, a0, st["rot"]); st["rot"] += math.radians(amt or 90); krot(i, a1, st["rot"])
            elif do in ("grow", "shrink", "stretch"):
                target = st["scale"] * (amt or (1.6 if do == "grow" else 0.6))
                kscale(i, a0, st["scale"]); kscale(i, a1, target); st["scale"] = target
            elif do == "pulse":
                for k in range(a0, f0 + n - 6, 16):
                    kscale(i, k, st["scale"]); kscale(i, k + 8, st["scale"] * 1.15)
                kscale(i, f0 + n - 2, st["scale"])
            elif do == "spin":
                roots[i]["linear"] = True
                krot(i, f0, st["rot"]); end = st["rot"] + math.radians(amt or 90) * (total - f0) / fps
                krot(i, total, end)
            elif do == "orbit" and act.get("with") in roots:
                c = state[act["with"]]["loc"]
                piv = empty(f"{i}_orbit", tuple(c)); piv["linear"] = True
                root = roots[i]
                mw = root.matrix_world.copy()
                root.parent = piv
                root.matrix_parent_inverse = piv.matrix_world.inverted()
                key(piv, "rotation_euler", f0, 0.0, 2)
                key(piv, "rotation_euler", total, math.radians(amt or 60) * (total - f0) / fps, 2)
            elif do == "highlight":
                b = st["mat"].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
                base = b.default_value
                for f, v in ((a0, base), (a0 + 10, base + 3.0), (f0 + n - 6, base + 3.0), (f0 + n, base)):
                    b.default_value = v; b.keyframe_insert("default_value", frame=f)
                b.default_value = base

    # camera follows the plan; it is placed after the motion so it can frame moving objects
    target = empty("CamTarget")
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    bpy.context.scene.collection.objects.link(cam)
    cam.data.lens = 35
    tr = cam.constraints.new("TRACK_TO"); tr.target = target; tr.track_axis, tr.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
    bpy.context.scene.camera = cam
    dirs = {"wide": (0, -1, 0.45), "close": (0.35, -1, 0.3), "top": (0, -0.25, 1), "side": (1, -0.25, 0.3),
            "low": (0.25, -1, 0.02), "orbit": (0, -1, 0.35)}
    smooth_all()                                       # evaluate object motion with its final interpolation
    for shot in shots:
        f0, f1 = shot["start"], shot["start"] + shot["frames"] - 1
        focus = shot.get("focus") if shot.get("focus") in roots else None
        if focus:
            dist = objs[focus]["size"] * 2.6 + 0.8
        else:
            dist = radius * 2.3
        d = Vector(dirs.get(shot["camera"], dirs["wide"])).normalized()
        for f in list(range(f0, f1, 6)) + [f1]:
            bpy.context.scene.frame_set(f)
            t = roots[focus].matrix_world.translation.copy() if focus else centre
            if shot["camera"] == "orbit":
                ang = math.radians(100) * (f - f0) / max(f1 - f0, 1)
                d2 = Vector((d.x * math.cos(ang) - d.y * math.sin(ang), d.x * math.sin(ang) + d.y * math.cos(ang), d.z)).normalized()
            else:
                d2 = d
            dolly = 1 - 0.08 * (f - f0) / max(f1 - f0, 1)
            key(target, "location", f, tuple(t))
            key(cam, "location", f, tuple(t + d2 * dist * dolly))
    # labels: sized by their object, raised to a higher tier when they would collide with a neighbour's label
    placed = []
    for i in sorted((i for i in labels if i in roots), key=lambda i: objs[i]["x"]):
        png, aspect = labels[i]
        o = objs[i]
        h = min(0.45, max(0.14, o["size"] * 0.22, radius * 0.035))
        w = h * aspect
        lift = o["size"] / 2 * max(1.0, o.get("sz", 1)) + h * 0.9
        z = o["z"] + lift
        for _ in range(6):
            hit = next((q for q in placed if abs(q[0] - o["x"]) < (q[1] + w) / 2 + 0.05 and abs(q[2] - z) < (q[3] + h) / 2 + 0.03), None)
            if not hit:
                break
            z = hit[2] + (hit[3] + h) / 2 + 0.05
        placed.append((o["x"], w, z, h))
        label(o, roots[i], png, aspect, h, cam, z - o["z"])
    smooth_all()
    return {"objects": len(roots), "radius": round(radius, 2)}
