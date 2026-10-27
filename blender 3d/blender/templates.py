"""3D lesson templates, run inside Blender. Each template builds its scene once, then animates one shot per
narration segment. A shot is {"focus": str, "start": frame, "frames": int}; the focus names what the camera and
the objects do. Templates take data only (the planner never writes code)."""
import math
import bpy
from mathutils import Vector, Euler

# ---------------------------------------------------------------- helpers

def srgb(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return (*[x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c], 1.0)


def material(name, color, rough=0.6, emit=0.0, metal=0.0):
    m = bpy.data.materials.new(name)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = srgb(color)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = srgb(color)
        b.inputs["Emission Strength"].default_value = emit
    return m


def sphere(name, r, loc=(0, 0, 0), mat=None, segs=48, shadow=True):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=segs, ring_count=segs // 2)
    ob = bpy.context.active_object
    ob.name = name
    ob.visible_shadow = shadow            # a glowing star with a light inside must not shadow its own light
    bpy.ops.object.shade_smooth()
    if mat:
        ob.data.materials.append(mat)
    return ob


def ring(name, r, thickness, mat, loc=(0, 0, 0), rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=r, minor_radius=thickness, major_segments=128, minor_segments=8,
                                     location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.data.materials.append(mat)
    return ob


def empty(name, loc=(0, 0, 0)):
    ob = bpy.data.objects.new(name, None)
    ob.location = loc
    bpy.context.scene.collection.objects.link(ob)
    return ob


def camera_rig(target):
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    bpy.context.scene.collection.objects.link(cam)
    track = cam.constraints.new("TRACK_TO")
    track.target = target
    track.track_axis, track.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
    bpy.context.scene.camera = cam
    cam.data.lens = 35
    return cam


def key(ob, path, frame, value, index=-1):
    setattr(ob, path, value) if index < 0 else getattr(ob, path).__setitem__(index, value)
    ob.keyframe_insert(path, frame=frame, index=index)


def smooth_all():
    """Ease in and out between keys (Bezier, auto-clamped); linear for continuous spins."""
    for ob in bpy.data.objects:
        ad = ob.animation_data
        if not (ad and ad.action):
            continue
        for fc in _fcurves(ad.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR" if ob.get("linear") else "BEZIER"
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"


def _fcurves(action):
    if hasattr(action, "fcurves"):
        return action.fcurves
    out = []                                # Blender 5 layered actions
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend(bag.fcurves)
    return out


def space_world(strength=0.03):
    w = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    nt = w.node_tree
    nt.nodes.clear()
    bg = nt.nodes.new("ShaderNodeBackground")
    stars = nt.nodes.new("ShaderNodeTexVoronoi"); stars.inputs["Scale"].default_value = 400
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.0, 0.035
    ramp.color_ramp.elements[0].color, ramp.color_ramp.elements[1].color = (1, 1, 1, 1), (0.004, 0.006, 0.02, 1)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(tc.outputs["Generated"], stars.inputs["Vector"])
    nt.links.new(stars.outputs["Distance"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength * 30
    nt.links.new(bg.outputs[0], out.inputs[0])


def studio_world(color="#1B2333", strength=0.6):
    w = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    nt = w.node_tree
    bg = nt.nodes.get("Background") or nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = srgb(color)
    bg.inputs["Strength"].default_value = strength


def earth_material():
    m = bpy.data.materials.new("Earth")
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 2.2; noise.inputs["Detail"].default_value = 8
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    land = nt.nodes.new("ShaderNodeValToRGB")
    els = land.color_ramp.elements
    els[0].position, els[0].color = 0.52, srgb("#1C4E8C")
    els[1].position, els[1].color = 0.55, srgb("#3C7A3A")
    e = els.new(0.68); e.color = srgb("#8C7A4A")
    nt.links.new(noise.outputs["Fac"], land.inputs["Fac"])
    sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    absz = nt.nodes.new("ShaderNodeMath"); absz.operation = "ABSOLUTE"; nt.links.new(sep.outputs["Z"], absz.inputs[0])
    ice = nt.nodes.new("ShaderNodeMath"); ice.operation = "GREATER_THAN"; ice.inputs[1].default_value = 0.38
    nt.links.new(absz.outputs[0], ice.inputs[0])
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
    nt.links.new(ice.outputs[0], mix.inputs[0]); nt.links.new(land.outputs["Color"], mix.inputs[6])
    mix.inputs[7].default_value = (0.92, 0.95, 1.0, 1)
    nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.55
    return m


# ---------------------------------------------------------------- seasons

SEASONS_FOCUS = ("intro", "tilt", "june", "december", "orbit")


def build_seasons(params, shots):
    space_world()
    sun = sphere("Sun", 1.3, mat=material("Sun", "#FFB43A", emit=12), shadow=False)
    light = bpy.data.objects.new("SunLight", bpy.data.lights.new("SunLight", "POINT"))
    light.data.energy, light.data.shadow_soft_size = 28000, 1.3
    bpy.context.scene.collection.objects.link(light)
    R = 7.0
    ring("Orbit", R, 0.012, material("OrbitLine", "#6E7FA8", emit=1.5))
    pivot = empty("EarthOrbit")                       # rotating this carries the Earth around the Sun
    holder = empty("EarthHolder", (R, 0, 0)); holder.parent = pivot
    tilt = empty("EarthTilt", (R, 0, 0))              # keeps the axis pointing the same way in space
    earth = sphere("Earth", 0.5, mat=earth_material()); earth.parent = tilt
    earth["linear"] = True
    axis_mat = material("Axis", "#FF5A5A", emit=3)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.012, depth=1.6)
    axis = bpy.context.active_object; axis.data.materials.append(axis_mat); axis.parent = tilt
    tilt.rotation_euler = (0, math.radians(-23.4), 0)  # north pole leans toward -X
    # the tilt empty follows the holder's position but not its rotation
    c = tilt.constraints.new("COPY_LOCATION"); c.target = holder

    # wide camera looks at the Sun; the Earth camera rides along beside the Earth (sun on one side, night on the other)
    target = empty("CamTarget")
    wide = camera_rig(target); wide.name = "WideCam"
    key(wide, "location", 0, (0, -16, 9))
    follow = empty("Follow"); fc = follow.constraints.new("COPY_LOCATION"); fc.target = tilt
    near = bpy.data.objects.new("EarthCam", bpy.data.cameras.new("EarthCam"))
    bpy.context.scene.collection.objects.link(near)
    near.parent = follow; near.location = (0, -2.6, 0.7); near.data.lens = 35
    tc = near.constraints.new("TRACK_TO"); tc.target = tilt; tc.track_axis, tc.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"

    def ahead(a, target):
        """Next orbit angle at or after `a` that equals `target` (mod 360): the Earth only moves forward."""
        t = target
        while t < a:
            t += 360
        return t

    # The north pole leans toward -X, so at angle 0 (Earth at +X) it leans toward the Sun: northern summer (June).
    a = 120.0
    for shot in shots:
        f0, f1, focus = shot["start"], shot["start"] + shot["frames"], shot["focus"]
        start = a
        end = {"june": ahead(a, 360), "december": ahead(a, 180), "orbit": a + 300, "intro": a + 30, "tilt": a + 10}[focus]
        key(pivot, "rotation_euler", f0, math.radians(start), 2)
        if focus in ("june", "december"):            # swing into position early, then drift so the close-up holds
            key(pivot, "rotation_euler", f0 + max(1, int(shot["frames"] * 0.3)), math.radians(end), 2)
            end += 6
        key(pivot, "rotation_euler", f1, math.radians(end), 2)
        a = end
        m = bpy.context.scene.timeline_markers.new(focus, frame=f0)
        m.camera = wide if focus in ("intro", "orbit") else near
        if m.camera is wide:
            key(wide, "location", f0, (0, -16, 9)); key(wide, "location", f1 - 1, (3, -15, 8))
        for f in (f0, f1):                                                 # a day every 2 seconds
            key(earth, "rotation_euler", f, f / 48 * 2 * math.pi, 2)
    smooth_all()
    return {"sun": sun}


# ---------------------------------------------------------------- solar system

PLANETS = [  # name, colour, radius, orbit, period (s per orbit in the video)
    ("Mercury", "#9C8F86", 0.18, 3.0, 4), ("Venus", "#D9B47A", 0.32, 4.2, 7), ("Earth", "#3C7AC8", 0.34, 5.6, 10),
    ("Mars", "#C2552E", 0.25, 7.0, 16), ("Jupiter", "#D8B48C", 0.85, 10.0, 40), ("Saturn", "#E3CB8F", 0.72, 13.0, 70),
    ("Uranus", "#8FD3DB", 0.5, 15.8, 120), ("Neptune", "#4E6FD8", 0.48, 18.2, 180),
]
SOLAR_FOCUS = ("overview", "inner", "outer", "earth", "sun")


def build_solar(params, shots):
    space_world()
    sphere("Sun", 1.6, mat=material("Sun", "#FFB43A", emit=12), shadow=False)
    light = bpy.data.objects.new("SunLight", bpy.data.lights.new("SunLight", "POINT"))
    light.data.energy, light.data.shadow_soft_size = 45000, 1.6
    bpy.context.scene.collection.objects.link(light)
    line = material("OrbitLine", "#56628A", emit=1.2)
    total = shots[-1]["start"] + shots[-1]["frames"]
    fps = bpy.context.scene.render.fps
    bodies = {}
    for name, col, r, orbit, period in PLANETS:
        ring(f"{name}Orbit", orbit, 0.01, line)
        pivot = empty(f"{name}Pivot"); pivot["linear"] = True
        p = sphere(name, r, (orbit, 0, 0), material(name, col, 0.7)); p.parent = pivot
        if name == "Saturn":
            r2 = ring("SaturnRing", r * 1.8, r * 0.25, material("SaturnRing", "#CDB685", 0.8), (orbit, 0, 0), (math.radians(70), 0, 0))
            r2.scale.z = 0.08; r2.parent = pivot
        phase = sum(map(ord, name)) * 37 % 360          # fixed, spread-out starting positions
        key(pivot, "rotation_euler", 0, math.radians(phase), 2)
        key(pivot, "rotation_euler", total, math.radians(phase) + total / fps / period * 2 * math.pi, 2)
        bodies[name] = p
    target = empty("CamTarget")
    cam = camera_rig(target)
    # Earth camera rides along with the Earth, so the close-up holds while it orbits
    follow = empty("Follow"); fc = follow.constraints.new("COPY_LOCATION"); fc.target = bodies["Earth"]
    near = bpy.data.objects.new("EarthCam", bpy.data.cameras.new("EarthCam"))
    bpy.context.scene.collection.objects.link(near)
    near.parent = follow; near.location = (0, -2.0, 0.6); near.data.lens = 35
    tc = near.constraints.new("TRACK_TO"); tc.target = bodies["Earth"]; tc.track_axis, tc.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
    views = {"overview": (0, -30, 18), "inner": (0, -11, 6), "outer": (6, -38, 14), "sun": (0, -6, 2)}
    for shot in shots:
        f0, f1 = shot["start"], shot["start"] + shot["frames"] - 1        # end one frame early: a clean cut
        m = bpy.context.scene.timeline_markers.new(shot["focus"], frame=f0)
        m.camera = near if shot["focus"] == "earth" else cam
        if m.camera is cam:
            c0 = views[shot["focus"]]
            key(cam, "location", f0, c0); key(cam, "location", f1, tuple(Vector(c0) * 0.92))
    smooth_all()
    return bodies


# ---------------------------------------------------------------- atom (Bohr model)

ELEMENTS = {"hydrogen": (1, 0), "helium": (2, 2), "lithium": (3, 4), "carbon": (6, 6), "nitrogen": (7, 7),
            "oxygen": (8, 8), "neon": (10, 10), "sodium": (11, 12), "magnesium": (12, 12), "chlorine": (17, 18),
            "argon": (18, 22), "calcium": (20, 20)}
ATOM_FOCUS = ("overview", "nucleus", "shells", "electrons")


def build_atom(params, shots):
    studio_world("#151C2B", 0.5)
    el = str(params.get("element", "carbon")).lower()
    z, n = ELEMENTS.get(el, ELEMENTS["carbon"])
    key_light = bpy.data.objects.new("Key", bpy.data.lights.new("Key", "AREA"))
    key_light.data.energy, key_light.data.size = 900, 4
    key_light.location = (4, -5, 6)
    key_light.rotation_euler = (Vector((0, 0, 0)) - key_light.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(key_light)
    proton, neutron = material("Proton", "#E0443A", 0.35), material("Neutron", "#B9C0CC", 0.4)
    golden = math.pi * (3 - math.sqrt(5))
    nucleus = empty("Nucleus"); nucleus["linear"] = True
    count = z + n
    rad = 0.16 * count ** (1 / 3)
    for i in range(count):                           # nucleons packed on a fibonacci ball
        y = 1 - 2 * (i + 0.5) / count
        r, th = math.sqrt(1 - y * y), golden * i
        d = rad * (0.35 + 0.65 * ((i * 7919) % 100) / 100)
        s = sphere(f"N{i}", 0.13, (math.cos(th) * r * d, y * d, math.sin(th) * r * d), proton if i % 2 == 0 and i // 2 < z else neutron, 20)
        s.parent = nucleus
    shells, left = [], z
    for cap in (2, 8, 8, 18):
        if left <= 0:
            break
        shells.append(min(cap, left)); left -= cap
    electron = material("Electron", "#4FC3F7", 0.2, emit=4)
    total = shots[-1]["start"] + shots[-1]["frames"]
    for k, count_e in enumerate(shells):
        radius = 1.4 + k * 0.9
        tilt = (math.radians(70 + 25 * k), math.radians(15 * k), 0)
        ring(f"Shell{k}", radius, 0.008, material(f"ShellLine{k}", "#7C8FBF", emit=1.2), rot=tilt)
        pivot = empty(f"ShellPivot{k}"); pivot.rotation_euler = tilt; pivot["linear"] = True
        spin = empty(f"ShellSpin{k}"); spin.parent = pivot; spin["linear"] = True
        for j in range(count_e):
            a = 2 * math.pi * j / count_e
            e = sphere(f"e{k}_{j}", 0.07, (radius * math.cos(a), radius * math.sin(a), 0), electron, 16)
            e.parent = spin
        key(spin, "rotation_euler", 0, 0, 2)
        key(spin, "rotation_euler", total, total / 24 * (1.2 / (k + 1)) * 2 * math.pi, 2)
    key(nucleus, "rotation_euler", 0, 0, 2)
    key(nucleus, "rotation_euler", total, total / 24 * 0.3, 2)
    target = empty("CamTarget")
    cam = camera_rig(target)
    outer = 1.4 + (len(shells) - 1) * 0.9
    views = {"overview": (0, -outer * 4.6, outer * 1.6), "nucleus": (0, -rad * 5 - 0.5, rad * 1.5),
             "shells": (outer * 2.4, -outer * 3.4, outer * 2.2), "electrons": (0, -outer * 3.2, outer * 0.8)}
    for shot in shots:
        f0, f1 = shot["start"], shot["start"] + shot["frames"] - 1        # end one frame early: a clean cut
        c = Vector(views[shot["focus"]])
        key(cam, "location", f0, tuple(c)); key(cam, "location", f1, tuple(c * 0.9))
    smooth_all()
    return {"element": el, "protons": z, "neutrons": n, "shells": shells}


TEMPLATES = {
    "seasons": (build_seasons, SEASONS_FOCUS),
    "solar_system": (build_solar, SOLAR_FOCUS),
    "atom": (build_atom, ATOM_FOCUS),
}
