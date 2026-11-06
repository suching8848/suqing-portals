"""Author original portal geometry, 64 matched sprites and a Viewpoint pack.

Offline deterministic mesh authoring and software rendering only. This script
does not start PZ, initialize its engine, or connect to an existing game.
Requires numpy and Pillow. Internal geometry uses X=east, Y=up, Z=south;
the exported OBJ explicitly converts to the installed Viewpoint Z-up convention.
"""
from __future__ import annotations
import io
import json
import math
import shutil
import struct
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "mods/SuQingPortals/42/media"
ART = ROOT / "art/model-source"
MODEL = MEDIA / "models/SuQingPortals"
SPRITES = MEDIA / "textures/SuQingPortals"
VP = MEDIA / "viewpoint"
SHEET = "suqing_portal_01"
PACK = "SuQingPortals_tiles"
TILEDEF = 7836
FACINGS = ["S", "E", "N", "W"]
VP_ROTATIONS = [0, -90, 180, 90]
SPRITE_SIZE = (128, 256)
NATIVE_ANCHOR = (64, 192)
GROUND_ORIGIN = (64, 224)
LEGACY_TOP_CROP = 128
for folder in (ART, MODEL, SPRITES, VP, MEDIA / "texturepacks"):
    folder.mkdir(parents=True, exist_ok=True)


def font(size, bold=False):
    return ImageFont.truetype("C:/Windows/Fonts/" + ("arialbd.ttf" if bold else "arial.ttf"), size)


palette = {
    "enamel": (229, 228, 233), "side": (185, 184, 200),
    "purple": (117, 91, 162), "lilac": (176, 147, 223),
    "light": (220, 205, 253), "steel": (126, 133, 150),
    "dark": (34, 38, 52), "rubber": (47, 49, 58),
    "battery": (61, 64, 75), "cap": (148, 115, 194),
    "positive": (190, 81, 93), "negative": (101, 151, 178),
    "ready": (123, 207, 187), "gold": (216, 190, 126),
}
atlas = Image.new("RGBA", (1024, 1024), (229, 228, 233, 255))
regions = {}
rng = np.random.default_rng(20261106)
for n, (name, rgb) in enumerate(palette.items()):
    x, y = n % 8 * 128, n // 8 * 128
    pixels = np.clip(np.asarray(rgb)[None, None, :] + rng.normal(0, .65, (128, 128, 1)), 0, 255).astype("uint8")
    patch = Image.fromarray(pixels).convert("RGBA")
    ImageDraw.Draw(patch).line((0, 127, 127, 127), fill=tuple(max(0, c - 15) for c in rgb), width=2)
    atlas.paste(patch, (x, y))
    regions[name] = (x + 2, y + 2, x + 126, y + 126)

ad = ImageDraw.Draw(atlas)
ad.rounded_rectangle((2, 258, 510, 382), radius=18, fill=(111, 88, 148), outline=(200, 186, 221), width=4)
ad.text((256, 280), "SUQING", anchor="mt", font=font(44, True), fill=(244, 238, 254))
ad.text((256, 334), "PORTAL SYSTEM", anchor="mt", font=font(18, True), fill=(218, 209, 237))
regions["logo"] = (0, 256, 512, 384)
ad.rounded_rectangle((516, 258, 766, 510), radius=18, fill=(27, 36, 48), outline=(171, 157, 197), width=6)
ad.text((641, 284), "ENERGY", anchor="mt", font=font(26, True), fill=(200, 224, 224))
for n in range(4):
    x = 545 + n * 49
    ad.rounded_rectangle((x, 338, x + 35, 396), radius=4, fill=(126, 193, 182), outline=(191, 224, 216), width=2)
    ad.rectangle((x + 12, 331, x + 23, 338), fill=(191, 224, 216))
ad.text((641, 430), "4 BANKS", anchor="mt", font=font(22, True), fill=(195, 182, 216))
regions["screen"] = (512, 256, 768, 512)
for n in range(4):
    x = n * 128
    ad.rectangle((x, 512, x + 127, 639), fill=(57, 60, 70))
    ad.rounded_rectangle((x + 7, 522, x + 120, 629), 6, fill=(181, 168, 207), outline=(221, 214, 235), width=3)
    ad.text((x + 63, 531), f"B{n+1}", anchor="mt", font=font(32, True), fill=(66, 54, 92))
    ad.text((x + 63, 580), "12 V", anchor="mt", font=font(20, True), fill=(84, 71, 108))
    regions[f"label{n}"] = (x, 512, x + 128, 640)
atlas.save(MODEL / "portal_atlas.png")


def mesh_for_mask(mask):
    count = bin(mask).count("1")
    verts, uv, faces = [], [], []

    def polygon(points, mat, coords=None):
        coords = coords or ([(0, 1), (1, 1), (1, 0), (0, 0)] if len(points) == 4 else [(0, 0)] * len(points))
        x0, y0, x1, y1 = regions[mat]
        start = len(verts)
        verts.extend(points)
        uv.extend(((x0 + (x1 - x0) * u) / 1024, 1 - (y0 + (y1 - y0) * v) / 1024) for u, v in coords)
        faces.extend((start, start + n, start + n + 1) for n in range(1, len(points) - 1))

    def box(cx, cy, cz, w, h, d, mat, front=None):
        x0, x1 = cx - w / 2, cx + w / 2
        y0, y1 = cy - h / 2, cy + h / 2
        z0, z1 = cz - d / 2, cz + d / 2
        polygon([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], front or mat)
        polygon([(x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0)], mat)
        polygon([(x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1)], mat)
        polygon([(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)], mat)
        polygon([(x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)], mat)
        polygon([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], mat)

    def ring_arc(rx, ry, irx, iry, cy, z0, z1, mat, steps=24):
        for n in range(steps):
            a, b = math.pi * n / steps, math.pi * (n + 1) / steps
            oa, ob = (rx * math.cos(a), cy + ry * math.sin(a)), (rx * math.cos(b), cy + ry * math.sin(b))
            ia, ib = (irx * math.cos(a), cy + iry * math.sin(a)), (irx * math.cos(b), cy + iry * math.sin(b))
            polygon([(*oa, z1), (*ob, z1), (*ib, z1), (*ia, z1)], mat)
            polygon([(*ob, z0), (*oa, z0), (*ia, z0), (*ib, z0)], mat)
            polygon([(*oa, z0), (*ob, z0), (*ob, z1), (*oa, z1)], mat)
            polygon([(*ib, z0), (*ia, z0), (*ia, z1), (*ib, z1)], mat)

    # One-tile footprint, open arch, four inspectable front battery bays.
    box(0, .055, 0, .96, .11, .66, "dark")
    box(0, .12, 0, .92, .055, .62, "side")
    box(0, .167, .035, .89, .04, .59, "purple")
    for x in (-.405, .405):
        box(x, .797, 0, .14, 1.27, .28, "enamel")
        box(x, .785, .15, .105, 1.18, .025, "purple")
        box(x, .785, .168, .018, 1.10, .012, "light")
        box(x, .235, -.11, .15, .14, .08, "steel")
        for y in (.48, .60, .72):
            box(x, y, -.153, .076, .014, .018, "dark")
    ring_arc(.475, .58, .335, .44, 1.425, -.14, .14, "enamel")
    ring_arc(.445, .55, .355, .46, 1.425, .141, .16, "purple")
    ring_arc(.351, .456, .337, .442, 1.425, .155, .17, "light")
    # Portal heart remains open; a visible engineered frame, not a flat billboard.
    box(0, 1.935, .164, .38, .10, .025, "purple", "logo")
    box(.405, 1.10, .177, .115, .17, .025, "dark", "screen")
    box(-.405, 1.11, .178, .042, .042, .023, "lilac")
    box(-.405, 1.04, .178, .027, .027, .025, "ready" if count >= 2 else "gold")
    # Raised four-bay rack: batteries appear as 3D blocks with caps and terminals.
    for slot in range(4):
        x = -.315 + slot * .21
        box(x, .208, .202, .193, .09, .235, "dark")
        box(x, .257, .315, .187, .025, .015, "steel")
        box(x - .097, .271, .21, .012, .145, .23, "side")
        if mask & (1 << slot):
            box(x, .292, .198, .158, .144, .176, "battery", f"label{slot}")
            box(x, .373, .198, .165, .022, .182, "cap")
            box(x - .049, .393, .24, .025, .02, .025, "positive")
            box(x + .049, .393, .24, .025, .02, .025, "negative")
            box(x, .398, .184, .070, .013, .014, "dark")
        else:
            box(x, .254, .198, .135, .012, .16, "rubber")
            box(x, .263, .20, .062, .008, .045, "steel")
        box(x, .187, .332, .14, .024, .012, "lilac")
    box(.435, .365, -.13, .034, .24, .06, "steel")
    return np.asarray(verts, dtype=float), np.asarray(uv, dtype=float), faces


def rotate(points, degrees):
    angle = math.radians(degrees)
    c, s = math.cos(angle), math.sin(angle)
    return points @ np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])


def render(mesh, degrees=0, size=(512, 768), scale=220, origin=None):
    v, uv, faces = mesh
    width, height = size
    origin = origin or (width / 2, height - 70)
    points = rotate(v, degrees)
    px = (points[:, 0] - points[:, 2]) * scale + origin[0]
    py = (points[:, 0] + points[:, 2]) * scale * .5 - points[:, 1] * scale * 1.5 + origin[1]
    depth = points[:, 0] + points[:, 2] + points[:, 1] * 1.3
    image = np.zeros((height, width, 4), dtype=np.uint8)
    zbuf = np.full((height, width), -1e12)
    texture = np.asarray(atlas)
    light = np.asarray([-.25, .85, .75]); light /= np.linalg.norm(light)
    for triangle in faces:
        ids = np.asarray(triangle)
        a, b, c = points[ids]
        normal = np.cross(b - a, c - a)
        norm = np.linalg.norm(normal)
        if norm < 1e-10:
            continue
        normal /= norm
        shade = .76 + .26 * max(0, np.dot(normal, light))
        x, y, z = px[ids], py[ids], depth[ids]
        xa, xb = max(0, int(np.floor(x.min()))), min(width - 1, int(np.ceil(x.max())))
        ya, yb = max(0, int(np.floor(y.min()))), min(height - 1, int(np.ceil(y.max())))
        if xa > xb or ya > yb:
            continue
        xx, yy = np.meshgrid(np.arange(xa, xb + 1) + .5, np.arange(ya, yb + 1) + .5)
        den = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(den) < 1e-10:
            continue
        q0 = ((y[1] - y[2]) * (xx - x[2]) + (x[2] - x[1]) * (yy - y[2])) / den
        q1 = ((y[2] - y[0]) * (xx - x[2]) + (x[0] - x[2]) * (yy - y[2])) / den
        q2 = 1 - q0 - q1
        dz = q0 * z[0] + q1 * z[1] + q2 * z[2]
        target = zbuf[ya:yb + 1, xa:xb + 1]
        mask = (q0 >= -1e-7) & (q1 >= -1e-7) & (q2 >= -1e-7) & (dz > target)
        if not mask.any():
            continue
        fu = q0 * uv[ids[0], 0] + q1 * uv[ids[1], 0] + q2 * uv[ids[2], 0]
        fv = q0 * uv[ids[0], 1] + q1 * uv[ids[1], 1] + q2 * uv[ids[2], 1]
        tx = np.clip((fu * 1024).astype(int), 0, 1023)
        ty = np.clip(((1 - fv) * 1024).astype(int), 0, 1023)
        color = texture[ty, tx].copy()
        color[:, :, :3] = np.clip(color[:, :, :3] * shade, 0, 255).astype("uint8")
        mask &= color[:, :, 3] > 0
        image[ya:yb + 1, xa:xb + 1][mask] = color[mask]
        target[mask] = dz[mask]
    return Image.fromarray(image)


def export_obj(mesh, mask):
    verts, uv, faces = mesh
    exported = verts[:, [0, 2, 1]]
    reversed_faces = [(a, c, b) for a, b, c in faces]
    result = ["# Original SuQing portal; X east, Y south, Z up; 1 unit = 1 tile.", "mtllib portal.mtl", f"o SuQingPortal_mask_{mask}", "usemtl portal_atlas"]
    result.extend("v %.7f %.7f %.7f" % tuple(p) for p in exported)
    result.extend("vt %.7f %.7f" % tuple(p) for p in uv)
    for face in reversed_faces:
        a, b, c = exported[list(face)]
        normal = np.cross(b - a, c - a); normal /= np.linalg.norm(normal)
        result.append("vn %.7f %.7f %.7f" % tuple(normal))
    result.extend("f " + " ".join(f"{i+1}/{i+1}/{n+1}" for i in face) for n, face in enumerate(reversed_faces))
    filename = f"portal_{mask}.obj"
    (MODEL / filename).write_text("\n".join(result) + "\n", encoding="ascii")
    shutil.copy2(MODEL / filename, VP / filename)
    return {"slotMask": mask, "occupiedSlots": [slot + 1 for slot in range(4) if mask & (1 << slot)], "count": bin(mask).count("1"), "vertices": len(verts), "triangles": len(faces), "bounds_xyz": [exported.min(axis=0).tolist(), exported.max(axis=0).tolist()]}


meshes = [mesh_for_mask(n) for n in range(16)]
records = [export_obj(mesh, n) for n, mesh in enumerate(meshes)]
(MODEL / "portal.mtl").write_text("newmtl portal_atlas\nKa 1 1 1\nKd 1 1 1\nKs 0.1 0.1 0.1\nNs 20\nd 1\nillum 2\nmap_Kd portal_atlas.png\n", encoding="ascii")
for name in ("portal.mtl", "portal_atlas.png"):
    shutil.copy2(MODEL / name, VP / name)

sprites = []
visual_records = []
for mask, mesh in enumerate(meshes):
    for facing in range(4):
        # Preserve the original mesh, scale, lighting and rasterization. Remove
        # only the 128 entirely transparent top rows; no mesh Z adjustment.
        legacy = render(mesh, facing * 90, (256, 768), 128, (128, 704)).resize((128, 384), Image.Resampling.LANCZOS)
        if legacy.crop((0, 0, 128, LEGACY_TOP_CROP)).getbbox() is not None:
            raise AssertionError("Legacy top crop would lose geometry")
        image = legacy.crop((0, LEGACY_TOP_CROP, 128, 384))
        name = f"{SHEET}_{mask*4+facing}"
        image.save(SPRITES / f"{name}.png")
        sprites.append(image)
        rows = {}
        alpha = np.asarray(image)[:, :, 3]
        for y in range(256):
            occupied = np.flatnonzero(alpha[y] >= 16)
            if len(occupied) == 0:
                continue
            changes = np.where(np.diff(occupied) > 1)[0]
            starts = np.concatenate(([occupied[0]], occupied[changes + 1]))
            ends = np.concatenate((occupied[changes] + 1, [occupied[-1] + 1]))
            rows[y] = [int(n) for pair in zip(starts, ends) for n in pair]
        visual_records.append({"name": name, "slotMask": mask, "facing": FACINGS[facing], "bounds": list(image.getbbox()), "rows": rows})
        if mask == 15 and facing == 0:
            legacy.save(ART / "legacy_full_bank_reference.png")

# Independent, tight-framed inventory/build render from the original mesh.
icon_path = MEDIA / "textures/Item_SuQingPortal.png"
if not icon_path.exists():
    icon = render(meshes[15], 0, (512, 768), 220, (256, 705))
    box = icon.getbbox()
    icon = icon.crop(box)
    canvas = Image.new("RGBA", (128, 128))
    icon.thumbnail((114, 114), Image.Resampling.LANCZOS)
    canvas.alpha_composite(icon, ((128-icon.width)//2, (128-icon.height)//2))
    canvas.save(icon_path)

# A 4x16 atlas preserves every actual slot combination on a four-facing row.
sheet = Image.new("RGBA", (4*128, 16*256))
for i, sprite in enumerate(sprites):
    sheet.paste(sprite, ((i % 4)*128, (i // 4)*256))
sheet.save(ART / f"{SHEET}.png")
wi = lambda n: struct.pack("<i", n)
def ws(value):
    data = value.encode("utf-8")
    return wi(len(data)) + data
png = io.BytesIO(); sheet.save(png, format="PNG"); imagebytes = png.getvalue()
pack = bytearray(b"PZPK" + wi(1) + wi(1) + ws(PACK+"_0") + wi(64) + wi(1))
for i in range(64):
    pack += ws(f"{SHEET}_{i}") + struct.pack("<8i", (i % 4)*128, (i // 4)*256, 128, 256, 0, 0, 128, 256)
pack += wi(len(imagebytes)) + imagebytes
(MEDIA / "texturepacks" / f"{PACK}.pack").write_bytes(pack)

properties = {"BlocksPlacement": "", "CustomName": "Portal", "GroupName": "SuQing", "Material": "MetalScrap", "Material2": "Electric", "solidtrans": ""}
tile = bytearray(b"tdef" + wi(1) + wi(1) + (SHEET+"\n"+SHEET+".png\n").encode("ascii") + struct.pack("<4i", 4, 16, 1, 64))
tile_records = []
for i in range(64):
    props = {**properties, "Facing": FACINGS[i % 4]}
    tile += wi(len(props))
    for key, value in sorted(props.items()):
        tile += (key+"\n"+value+"\n").encode("ascii")
    mask = i // 4
    tile_records.append({"name": f"{SHEET}_{i}", "slotMask": mask, "installedCount": bin(mask).count("1"), "properties": props})
(MEDIA / f"{SHEET}.tiles").write_bytes(tile)
(ART / "tile_properties.json").write_text(json.dumps({"tiledef": TILEDEF, "sprites": tile_records}, indent=2), encoding="utf-8")

manifest = ["# Original SuQing portal. One tile unit, Z up; optional Viewpoint integration.", "id=suqing-portals", "name=SuQing Portals", "version=1"]
for n in range(16):
    manifest.append(f"model.suqing_portal_{n}=portal_{n}.obj")
for i in range(64):
    manifest.append(f"bind.{SHEET}_{i}=suqing_portal_{i//4},{VP_ROTATIONS[i%4]},0,0,0,1")
(VP / "package.properties").write_text("\n".join(manifest)+"\n", encoding="ascii")

preview = Image.new("RGB", (1600, 1390), (27, 28, 39))
pd = ImageDraw.Draw(preview)
pd.text((42, 24), "SUQING / PORTAL BATTERY BANK", font=font(29, True), fill=(231, 224, 245))
pd.text((42, 66), "Actual four-slot occupancy. Standard 128x256 sprites, unchanged geometry and scale.", font=font(18), fill=(178, 171, 192))
for column, mask in enumerate((0, 10, 15)):
    frame = render(meshes[mask], 0, (500, 690), 193, (250, 648))
    preview.paste(frame, (25+column*530, 110), frame)
    slots = ",".join(str(slot+1) for slot in range(4) if mask & (1 << slot)) or "NONE"
    pd.text((265+column*530, 834), "SLOTS " + slots, anchor="mt", font=font(24, True), fill=(199, 179, 224))
for facing in range(4):
    tiny = sprites[60+facing]
    preview.paste(tiny, (55+facing*360, 1040), tiny)
    pd.text((119+facing*360, 1320), FACINGS[facing], anchor="mt", font=font(19, True), fill=(199, 179, 224))
preview.save(ART / "portal_model_preview.png")
hero = render(meshes[15], 0, (700, 1000), 285, (350, 940)); hero.save(ART / "portal_front_transparent.png")

# Static resource data for exact fallback picking. No camera assumptions are
# encoded here; the client converts screen coordinates into native texture pixels.
lua = ["-- Generated original sprite bounds/alpha runs. Do not edit manually.", "SuQingPortals = SuQingPortals or {}", "SuQingPortals.VisualData = {", f"    width = 128, height = 256, anchorX = {NATIVE_ANCHOR[0]}, anchorY = {NATIVE_ANCHOR[1]},", f"    groundX = {GROUND_ORIGIN[0]}, groundY = {GROUND_ORIGIN[1]}, alphaThreshold = 16,", "    sprites = {"]
for record in visual_records:
    bounds = ", ".join(str(n) for n in record["bounds"])
    lua.append(f'        ["{record["name"]}"] = {{ slotMask = {record["slotMask"]}, facing = "{record["facing"]}", bounds = {{{bounds}}}, rows = {{')
    for y, runs in record["rows"].items():
        encoded = "".join("\\%03d" % n for n in runs)
        lua.append(f'            [{y}] = "{encoded}",')
    lua.append("        } },")
lua += ["    }", "}", "return SuQingPortals.VisualData"]
visual_data_path = MEDIA / "lua/client/SuQingPortals/VisualData.lua"
visual_data_path.parent.mkdir(parents=True, exist_ok=True)
visual_data_path.write_text("\n".join(lua)+"\n", encoding="ascii")
(ART / "screen_pick_metadata.json").write_text(json.dumps({"width": 128, "height": 256, "anchor": NATIVE_ANCHOR, "ground": GROUND_ORIGIN, "alphaThreshold": 16, "sprites": visual_records}, indent=2), encoding="utf-8")

# The native floor diamond and sprite use the same world anchor in both new
# preview and placed-object diagrams. This is a projection check, not real FBO.
alignment = Image.new("RGBA", (1500, 1040), (27, 28, 39, 255))
draw = ImageDraw.Draw(alignment)
draw.text((35, 22), "SAME NATIVE TILE ANCHOR / NO MESH Z OFFSET", font=font(26, True), fill=(237, 229, 249))
old_image = Image.open(ART / "legacy_full_bank_reference.png").convert("RGBA")
new_image = sprites[60]
for column, (label, asset, ghost) in enumerate((("LEGACY / 128x384", old_image, False), ("FIXED PREVIEW / 128x256", new_image, True), ("FIXED PLACED / 128x256", new_image, False))):
    center_x, origin_y = column*500+250, 520
    polygon = [(center_x, origin_y), (center_x+128, origin_y+64), (center_x, origin_y+128), (center_x-128, origin_y+64)]
    draw.polygon(polygon, fill=(37, 72, 59, 255), outline=(100, 232, 153, 255))
    image = asset.resize((asset.width*2, asset.height*2), Image.Resampling.NEAREST)
    if ghost:
        image.putalpha(image.getchannel("A").point(lambda value: int(value*.6)))
    alignment.alpha_composite(image, (center_x-128, origin_y-384))
    draw.line((center_x-12, origin_y, center_x+12, origin_y), fill=(249, 206, 97, 255), width=2)
    draw.line((center_x, origin_y-12, center_x, origin_y+12), fill=(249, 206, 97, 255), width=2)
    ground_y = origin_y + ((352 if column == 0 else 224)-192)*2
    draw.ellipse((center_x-5, ground_y-5, center_x+5, ground_y+5), fill=(236, 166, 240, 255))
    draw.text((column*500+24, 84), label, font=font(21, True), fill=(219, 205, 238))
    draw.text((column*500+24, 952), "native anchor = (64,192)", font=font(17), fill=(229, 199, 127))
    draw.text((column*500+24, 981), "ground = " + ("(64,352) WRONG" if column == 0 else "(64,224), floor center"), font=font(17), fill=(215, 174, 226))
alignment.convert("RGB").save(ART / "anchor_alignment.png")

four = Image.new("RGBA", (1200, 1430), (27, 28, 39, 255))
fd = ImageDraw.Draw(four)
fd.text((34, 22), "FOUR FACINGS / ONE NATIVE FLOOR REFERENCE", font=font(26, True), fill=(237, 229, 249))
for facing in range(4):
    panel_x, panel_y = (facing % 2)*600, 80+(facing // 2)*660
    center_x, origin_y = panel_x+300, panel_y+470
    diamond = [(center_x, origin_y), (center_x+128, origin_y+64), (center_x, origin_y+128), (center_x-128, origin_y+64)]
    fd.polygon(diamond, fill=(37, 72, 59, 255), outline=(100, 232, 153, 255))
    asset = sprites[60+facing].resize((256, 512), Image.Resampling.NEAREST)
    four.alpha_composite(asset, (center_x-128, origin_y-384))
    fd.line((center_x-10, origin_y+64, center_x+10, origin_y+64), fill=(236, 166, 240, 255), width=2)
    fd.line((center_x, origin_y+54, center_x, origin_y+74), fill=(236, 166, 240, 255), width=2)
    fd.text((panel_x+32, panel_y+8), FACINGS[facing]+" / GROUND=(64,224)", font=font(22, True), fill=(221, 207, 239))
    fd.text((panel_x+32, panel_y+624), "Tile center +32px; native anchor (64,192)", font=font(17), fill=(189, 214, 193))
four.convert("RGB").save(ART / "anchor_four_facings.png")

receipt = {"generator": "tools/build_portal_assets.py", "seed": 20261106, "models": records, "sprite_names": [f"{SHEET}_{i}" for i in range(64)], "spriteSize": SPRITE_SIZE, "nativeAnchor": NATIVE_ANCHOR, "groundOrigin": GROUND_ORIGIN, "legacyTopCrop": LEGACY_TOP_CROP, "facings": FACINGS, "mapping": "index = actual slot occupancy mask * 4 + facingIndex; mask bits 0..3 correspond to slots 1..4; S=0,E=1,N=2,W=3", "viewpointRotation": VP_ROTATIONS, "pack": PACK, "tiledef": TILEDEF, "source": "Original deterministic geometry and hand-authored texture atlas. No third-party mesh or texture.", "scope": "Offline mesh/sprite/model-pack generation and common-anchor overlay. Actual PZ placement/FBO rendering and Viewpoint camera views remain for user acceptance."}
(ART / "model_manifest.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print(json.dumps({"models": len(records), "sprites": len(sprites), "pack": PACK, "tiledef": TILEDEF, "spriteSize": SPRITE_SIZE, "nativeAnchor": NATIVE_ANCHOR, "groundOrigin": GROUND_ORIGIN}, indent=2))
