"""
Jelly Island — a Blender scene generator
-----------------------------------------
A three-layer fluted jelly mold (strawberry, lime, orange) rising out of a
blue-raspberry jelly sea, ringed by a sugar beach, with a gummy palm tree,
cherry "coconuts", jelly-cube boulders, and a looping wobble animation.

How to use:
  1. Open Blender (3.6+ or 4.x).
  2. Go to the Scripting tab, click "New", paste this script, press Run.
  3. Press Numpad 0 to look through the camera, F12 to render,
     or Space to play the wobble animation.

Note: the script clears the current scene first.
"""

import bpy
import bmesh
import math
import random

random.seed(7)

# ---------------------------------------------------------------- helpers

def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.lights,
                 bpy.data.cameras, bpy.data.textures):
        for block in list(coll):
            if block.users == 0:
                coll.remove(block)


def set_input(node, names, value):
    """Set the first matching socket (names differ across Blender versions)."""
    for n in names:
        if n in node.inputs:
            node.inputs[n].default_value = value
            return True
    return False


def make_material(name, color, transmission=0.9, roughness=0.05,
                  subsurface=0.15, coat=0.6, ior=1.36):
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    set_input(bsdf, ["Base Color"], (*color, 1.0))
    set_input(bsdf, ["Transmission Weight", "Transmission"], transmission)
    set_input(bsdf, ["Roughness"], roughness)
    set_input(bsdf, ["IOR"], ior)
    set_input(bsdf, ["Subsurface Weight", "Subsurface"], subsurface)
    set_input(bsdf, ["Subsurface Color"], (*color, 1.0))  # older Blender only
    set_input(bsdf, ["Coat Weight", "Clearcoat"], coat)
    mat.diffuse_color = (*color, 1.0)  # viewport solid-mode colour
    # Let EEVEE show refraction too (attribute names vary by version)
    for attr in ("use_raytrace_refraction", "use_screen_refraction"):
        if hasattr(mat, attr):
            setattr(mat, attr, True)
    return mat


def add_bump(mat, scale=40.0, strength=0.25):
    """Add a fine noise bump (used for the sugar-crystal beach)."""
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def smooth(obj, subdiv=2):
    for p in obj.data.polygons:
        p.use_smooth = True
    if subdiv:
        m = obj.modifiers.new("Subdivision", "SUBSURF")
        m.levels = 1
        m.render_levels = subdiv


def lathe(name, profile, mat, flutes=0, flute_depth=0.0, segs=96, subdiv=2):
    """Spin a (radius, z) profile around Z. Radius 0 points become poles.
    Flutes give the classic ridged jelly-mold look."""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        if r <= 1e-6:
            rings.append(bm.verts.new((0.0, 0.0, z)))
        else:
            ring = []
            for i in range(segs):
                a = 2 * math.pi * i / segs
                f = 1 - flute_depth * 0.5 * (1 - math.cos(flutes * a)) if flutes else 1
                ring.append(bm.verts.new((r * f * math.cos(a), r * f * math.sin(a), z)))
            rings.append(ring)

    for a, b in zip(rings, rings[1:]):
        if isinstance(a, list) and isinstance(b, list):
            for i in range(segs):
                j = (i + 1) % segs
                bm.faces.new((a[i], a[j], b[j], b[i]))
        elif isinstance(a, list):          # ring -> top pole
            for i in range(segs):
                bm.faces.new((a[i], a[(i + 1) % segs], b))
        else:                               # bottom pole -> ring
            for i in range(segs):
                bm.faces.new((a, b[(i + 1) % segs], b[i]))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = link(bpy.data.objects.new(name, mesh))
    obj.data.materials.append(mat)
    smooth(obj, subdiv)
    return obj


def uv_sphere(name, location, scale, mat, rotation=(0, 0, 0), subdiv=1):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16,
                                         location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    smooth(obj, subdiv)
    return obj


# ---------------------------------------------------------------- scene

clear_scene()
scene = bpy.context.scene

# Materials
M = {
    "strawberry": make_material("Strawberry Jelly", (0.85, 0.05, 0.12)),
    "lime":       make_material("Lime Jelly",       (0.30, 0.85, 0.10)),
    "orange":     make_material("Orange Jelly",     (1.00, 0.45, 0.02)),
    "sea":        make_material("Blue Raspberry Sea", (0.05, 0.45, 0.95),
                                transmission=0.95, roughness=0.02, subsurface=0.05),
    "sugar":      make_material("Sugar Sand", (1.0, 0.93, 0.78),
                                transmission=0.0, roughness=0.45, subsurface=0.05, coat=0.0),
    "gummy_a":    make_material("Gummy Orange", (1.0, 0.55, 0.05),
                                transmission=0.55, roughness=0.18, subsurface=0.35),
    "gummy_b":    make_material("Gummy Yellow", (1.0, 0.85, 0.10),
                                transmission=0.55, roughness=0.18, subsurface=0.35),
    "leaf":       make_material("Gummy Leaf", (0.10, 0.75, 0.15),
                                transmission=0.6, roughness=0.12, subsurface=0.3),
    "cherry":     make_material("Cherry", (0.75, 0.0, 0.05),
                                transmission=0.4, roughness=0.08, subsurface=0.3),
    "grape":      make_material("Grape Jelly", (0.45, 0.05, 0.75)),
}
add_bump(M["sugar"])

# Wobble controller: everything on the island is parented to this
wobble = link(bpy.data.objects.new("Jelly Wobble", None))
wobble.empty_display_type = "SPHERE"
wobble.empty_display_size = 0.5

def parent(obj):
    obj.parent = wobble
    return obj

# --- The island: three stacked, fluted jelly tiers
parent(lathe("Tier 1 Strawberry", [
    (0, 0.0), (3.0, 0.0), (3.15, 0.35), (3.05, 0.95), (2.7, 1.25), (0, 1.25)
], M["strawberry"], flutes=14, flute_depth=0.10))

parent(lathe("Tier 2 Lime", [
    (0, 1.15), (2.55, 1.15), (2.6, 1.5), (2.4, 2.05), (2.05, 2.3), (0, 2.3)
], M["lime"], flutes=12, flute_depth=0.12))

parent(lathe("Tier 3 Orange Dome", [
    (0, 2.2), (1.95, 2.2), (1.95, 2.55), (1.75, 2.95), (1.3, 3.25),
    (0.7, 3.42), (0, 3.47)
], M["orange"], flutes=10, flute_depth=0.14))

# --- Sugar beach ring around the base
lathe("Sugar Beach", [
    (0, -0.15), (4.3, -0.15), (4.2, 0.0), (3.7, 0.12), (3.2, 0.18), (0, 0.18)
], M["sugar"], segs=96, subdiv=2)

# --- Blue raspberry jelly sea
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, 0.02))
sea = bpy.context.active_object
sea.name = "Jelly Sea"
sea.data.materials.append(M["sea"])
sub = sea.modifiers.new("Subdivision", "SUBSURF")
sub.subdivision_type = "SIMPLE"
sub.levels = sub.render_levels = 6
tex = bpy.data.textures.new("Sea Ripples", type="CLOUDS")
tex.noise_scale = 2.5
disp = sea.modifiers.new("Ripples", "DISPLACE")
disp.texture = tex
disp.strength = 0.25
disp.mid_level = 0.5
for p in sea.data.polygons:
    p.use_smooth = True

# --- Gummy palm tree on the summit
base = (0.25, 0.1, 3.35)
trunk_segments = 9
pos = list(base)
for i in range(trunk_segments):
    t = i / trunk_segments
    pos = [base[0] + 0.55 * t * t, base[1] + 0.15 * t, base[2] + i * 0.2]
    s = 0.26 - 0.06 * t
    parent(uv_sphere(f"Trunk Gummy {i + 1}", pos, (s, s, 0.13),
                     M["gummy_a"] if i % 2 == 0 else M["gummy_b"]))
top = (pos[0], pos[1], pos[2] + 0.12)

for i in range(8):
    a = 2 * math.pi * i / 8 + random.uniform(-0.15, 0.15)
    droop = random.uniform(0.35, 0.6)
    loc = (top[0] + 0.6 * math.cos(a), top[1] + 0.6 * math.sin(a), top[2] - 0.18)
    parent(uv_sphere(f"Leaf {i + 1}", loc, (0.75, 0.2, 0.05), M["leaf"],
                     rotation=(0, droop, a)))

for i in range(3):
    a = 2 * math.pi * i / 3 + 0.4
    parent(uv_sphere(f"Cherry {i + 1}",
                     (top[0] + 0.15 * math.cos(a), top[1] + 0.15 * math.sin(a), top[2] - 0.15),
                     (0.12, 0.12, 0.12), M["cherry"]))

# --- Jelly-cube boulders scattered on the beach
palette = [M["grape"], M["lime"], M["strawberry"], M["orange"]]
for i in range(9):
    a = 2 * math.pi * i / 9 + random.uniform(-0.2, 0.2)
    r = random.uniform(3.35, 3.85)
    size = random.uniform(0.22, 0.42)
    bpy.ops.mesh.primitive_cube_add(
        size=size * 2,
        location=(r * math.cos(a), r * math.sin(a), 0.1 + size * 0.8),
        rotation=(random.uniform(-0.2, 0.2), random.uniform(-0.2, 0.2),
                  random.uniform(0, math.pi)))
    cube = bpy.context.active_object
    cube.name = f"Jelly Cube {i + 1}"
    cube.data.materials.append(random.choice(palette))
    bev = cube.modifiers.new("Bevel", "BEVEL")
    bev.width = size * 0.35
    bev.segments = 4
    smooth(cube, subdiv=1)

# ---------------------------------------------------------------- wobble animation
# A squash-and-stretch jiggle that settles, then repeats every 40 frames.
scene.frame_start, scene.frame_end = 1, 120
jiggle = [(0, (1.00, 1.00, 1.00)), (6, (1.05, 1.05, 0.91)),
          (12, (0.97, 0.97, 1.06)), (18, (1.025, 1.025, 0.96)),
          (24, (0.99, 0.99, 1.02)), (30, (1.0, 1.0, 1.0))]
for start in range(1, scene.frame_end + 1, 40):
    for offset, s in jiggle:
        wobble.scale = s
        wobble.keyframe_insert("scale", frame=start + offset)
wobble.scale = (1, 1, 1)

# ---------------------------------------------------------------- lighting & camera
world = scene.world or bpy.data.worlds.new("World")
scene.world = world
try:
    world.use_nodes = True
except Exception:
    pass
bg = world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.55, 0.75, 1.0, 1.0)
bg.inputs["Strength"].default_value = 0.9

sun_data = bpy.data.lights.new("Sun", "SUN")
sun_data.energy = 4.0
sun_data.angle = math.radians(3)
sun = link(bpy.data.objects.new("Sun", sun_data))
sun.rotation_euler = (math.radians(45), 0, math.radians(35))

fill_data = bpy.data.lights.new("Pink Fill", "AREA")
fill_data.energy = 600
fill_data.size = 6
fill_data.color = (1.0, 0.75, 0.85)
fill = link(bpy.data.objects.new("Pink Fill", fill_data))
fill.location = (-7, 6, 5)

target = link(bpy.data.objects.new("Camera Target", None))
target.location = (0, 0, 1.6)

cam_data = bpy.data.cameras.new("Camera")
cam_data.lens = 40
cam = link(bpy.data.objects.new("Camera", cam_data))
cam.location = (10.5, -10.5, 5.5)
track = cam.constraints.new("TRACK_TO")
track.target = target
track.track_axis = "TRACK_NEGATIVE_Z"
track.up_axis = "UP_Y"
scene.camera = cam

# ---------------------------------------------------------------- render settings
# Cycles renders the see-through jelly best.
scene.render.engine = "CYCLES"
scene.cycles.samples = 128
if hasattr(scene.cycles, "use_denoising"):
    scene.cycles.use_denoising = True
scene.cycles.transmission_bounces = 12
scene.cycles.max_bounces = 16
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.frame_set(1)

print("Jelly Island built! Numpad 0 for camera view, F12 to render, Space to wobble.")
