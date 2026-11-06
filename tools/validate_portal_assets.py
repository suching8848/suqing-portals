"""Read back portal binary assets and true geometry; never starts the game."""
from pathlib import Path
import hashlib
import io
import json
import struct
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "mods/SuQingPortals/42/media"
ART = ROOT / "art/model-source"
SHEET = "suqing_portal_01"
PACK = "SuQingPortals_tiles"
FACING = ["S", "E", "N", "W"]
checks = []
def check(value, label):
    if not value:
        raise AssertionError(label)
    checks.append(label)
def ri(f):
    raw = f.read(4); check(len(raw) == 4, "binary int complete")
    return struct.unpack("<i", raw)[0]
def rs(f):
    n = ri(f); check(0 <= n <= 100000, "string length within bounds")
    raw = f.read(n); check(len(raw) == n, "string complete")
    return raw.decode("utf-8")
def line(f):
    b = f.readline(); check(b.endswith(b"\n"), "tile string newline")
    return b[:-1].decode("ascii")

packpath = MEDIA / "texturepacks" / f"{PACK}.pack"
f = io.BytesIO(packpath.read_bytes())
check(f.read(4) == b"PZPK", "pack magic")
check(ri(f) == 1 and ri(f) == 1, "pack version and one page")
check(rs(f) == PACK + "_0", "page name")
check(ri(f) == 64 and ri(f) == 1, "64 RGBA sprites")
for i in range(64):
    check(rs(f) == f"{SHEET}_{i}", f"sprite name {i}")
    actual = struct.unpack("<8i", f.read(32))
    check(actual == ((i % 4)*128, (i // 4)*256, 128, 256, 0, 0, 128, 256), f"standard rectangle and origin {i}")
length = ri(f); png = f.read(length)
check(len(png) == length and not f.read(), "pack png/eof")
page = Image.open(io.BytesIO(png)); page.load()
check(page.mode == "RGBA" and page.size == (512, 4096), "page RGBA decode")
hashes = []
for i in range(64):
    sprite = Image.open(MEDIA / f"textures/SuQingPortals/{SHEET}_{i}.png").convert("RGBA")
    check(sprite.size == (128, 256), f"standard dimensions {i}")
    crop = page.crop(((i % 4)*128, (i // 4)*256, (i % 4+1)*128, (i // 4+1)*256))
    check(sprite.tobytes() == crop.tobytes(), f"atlas/source pixels match {i}")
    bounds = sprite.getbbox()
    check(bounds is not None and bounds[0] > 0 and bounds[1] > 0 and bounds[2] < 128 and bounds[3] < 256, f"unclipped {i}")
    hashes.append(hashlib.sha256(sprite.tobytes()).hexdigest())
check(len(set(hashes)) == 64, "all actual occupancy/facing combinations distinct")

f = io.BytesIO((MEDIA / f"{SHEET}.tiles").read_bytes())
check(f.read(4) == b"tdef", "tiles magic")
check(ri(f) == 1 and ri(f) == 1, "tiles version and count")
check(line(f) == SHEET and line(f) == SHEET + ".png", "tileset identity")
check(tuple(ri(f) for _ in range(4)) == (4, 16, 1, 64), "tile dimensions and entries")
for i in range(64):
    n = ri(f); props = {}
    for _ in range(n):
        key, value = line(f), line(f)
        check(key not in props, f"unique property {i}")
        props[key] = value
    check(props["Facing"] == FACING[i % 4], f"tile facing {i}")
    check(props["CustomName"] == "Portal" and props["GroupName"] == "SuQing", f"tile display namespace {i}")
    check("BlocksPlacement" in props and "solidtrans" in props, f"fixed collision/placement {i}")
    check("IsMoveAble" not in props and "container" not in props, f"no generic battery bypass or duplicate moveable ID {i}")
check(not f.read(), "tiles eof")

manifest = {}
for row in (MEDIA / "viewpoint/package.properties").read_text().splitlines():
    if "=" in row and not row.startswith("#"):
        key, value = row.split("=", 1)
        check(key not in manifest, "unique Viewpoint property")
        manifest[key] = value
geometry = []
for mask in range(16):
    vertices, uv, normals, faces = [], [], [], []
    path = MEDIA / f"models/SuQingPortals/portal_{mask}.obj"
    for row in path.read_text().splitlines():
        data = row.split()
        if not data: continue
        if data[0] == "v": vertices.append([float(x) for x in data[1:]])
        if data[0] == "vt": uv.append([float(x) for x in data[1:]])
        if data[0] == "vn": normals.append([float(x) for x in data[1:]])
        if data[0] == "f": faces.append([[int(x) for x in p.split("/")] for p in data[1:]])
    v, t, normals = np.asarray(vertices), np.asarray(uv), np.asarray(normals)
    check(np.isfinite(v).all() and np.isfinite(t).all() and np.isfinite(normals).all(), f"finite geometry {mask}")
    check(len(faces) == 1128 + 36*bin(mask).count("1"), f"real actual-slot battery geometry {mask}")
    check((v.min(axis=0) >= np.asarray([-.5, -.5, 0])).all() and (v.max(axis=0) <= np.asarray([.5, .5, 2.1])).all(), f"one tile bounds Z up {mask}")
    check(abs(v[:, 2].min()) < 1e-8, f"OBJ floor remains Z zero {mask}")
    check(t.min() >= 0 and t.max() <= 1, f"UV inside atlas {mask}")
    check(np.allclose(np.linalg.norm(normals, axis=1), 1, atol=1e-6), f"unit normals {mask}")
    triangles = np.asarray(faces, dtype=int)
    check(triangles.shape == (len(faces), 3, 3) and (triangles[:, :, 0] >= 1).all() and (triangles[:, :, 0] <= len(v)).all() and (triangles[:, :, 1] >= 1).all() and (triangles[:, :, 1] <= len(t)).all() and (triangles[:, :, 2] >= 1).all() and (triangles[:, :, 2] <= len(normals)).all(), f"valid triangle indices {mask}")
    points = v[triangles[:, :, 0] - 1]
    check((np.linalg.norm(np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0]), axis=1) > 1e-10).all(), f"nondegenerate geometry {mask}")
    # A battery's terminals above the empty rack occupy only its actual slot.
    for slot in range(4):
        cx = -.315 + slot*.21
        battery_region = (np.abs(v[:, 0] - cx) <= .085) & (v[:, 1] >= .10) & (v[:, 1] <= .30) & (v[:, 2] > .35) & (v[:, 2] < .41)
        check(bool(battery_region.any()) == bool(mask & (1 << slot)), f"physical slot occupancy mask {mask} slot {slot+1}")
    check(path.read_bytes() == (MEDIA / f"viewpoint/portal_{mask}.obj").read_bytes(), f"Viewpoint mesh same as sprite mesh {mask}")
    check(manifest[f"model.suqing_portal_{mask}"] == f"portal_{mask}.obj", f"model relative path {mask}")
    for direction, degrees in enumerate([0, -90, 180, 90]):
        i = mask*4+direction
        check(manifest[f"bind.{SHEET}_{i}"] == f"suqing_portal_{mask},{degrees},0,0,0,1", f"model occupancy/facing binding {i}")
    geometry.append({"slotMask": mask, "batteryCount": bin(mask).count("1"), "vertices": len(v), "triangles": len(faces)})
for name in ("portal.mtl", "portal_atlas.png"):
    check((MEDIA / "models/SuQingPortals" / name).read_bytes() == (MEDIA / "viewpoint" / name).read_bytes(), "canonical material/atlas matches VP")
check("map_Kd portal_atlas.png" in (MEDIA / "viewpoint/portal.mtl").read_text(), "texture reference")
atlas = Image.open(MEDIA / "viewpoint/portal_atlas.png"); atlas.load()
check(atlas.size == (1024, 1024) and atlas.mode == "RGBA", "model atlas decode")
icon = Image.open(MEDIA / "textures/Item_SuQingPortal.png"); icon.load()
check(icon.mode == "RGBA" and icon.size == (128, 128) and icon.getbbox() is not None, "independent build icon")
metadata = json.loads((ART / "screen_pick_metadata.json").read_text(encoding="utf-8"))
check(metadata["width"] == 128 and metadata["height"] == 256 and metadata["anchor"] == [64, 192] and metadata["ground"] == [64, 224], "native anchor and floor origin contract")
check(len(metadata["sprites"]) == 64, "64 precise picking masks")
for record in metadata["sprites"]:
    sprite = Image.open(MEDIA / f'textures/SuQingPortals/{record["name"]}.png').convert("RGBA")
    pixels = np.asarray(sprite)[:, :, 3]
    recovered = np.zeros((256, 128), dtype=bool)
    check(all(len(intervals) % 2 == 0 for intervals in record["rows"].values()), f'alpha interval pairs {record["name"]}')
    for y, intervals in record["rows"].items():
        for left, right in zip(intervals[::2], intervals[1::2]):
            recovered[int(y), left:right] = True
    check(np.array_equal(recovered, pixels >= metadata["alphaThreshold"]), f'exact exported alpha hit mask {record["name"]}')
    check(record["bounds"] == list(sprite.getbbox()), f'exact exported bounding box {record["name"]}')
legacy = Image.open(ART / "legacy_full_bank_reference.png").convert("RGBA")
fixed = Image.open(MEDIA / f"textures/SuQingPortals/{SHEET}_60.png").convert("RGBA")
check(legacy.size == (128, 384) and legacy.crop((0, 0, 128, 128)).getbbox() is None, "removed top rows were entirely transparent")
check(legacy.crop((0, 128, 128, 384)).tobytes() == fixed.tobytes(), "full-bank new sprite is exact unscaled old crop")
alignment = Image.open(ART / "anchor_alignment.png"); alignment.load()
check(alignment.size == (1500, 1040), "native tile diamond comparison exported")
four = Image.open(ART / "anchor_four_facings.png"); four.load()
check(four.size == (1200, 1430), "four facings share the same native floor-center overlay")
report = {"result": "PASS", "structuralChecks": len(checks), "models": geometry, "spriteCombinations": 64, "meaningfulChecks": sorted(set(checks)), "scope": "Offline binary PNG/pack/tiles/OBJ/UV/normals/material/occupancy/model-pack and common-native-anchor/alpha-picking verification. No game engine/world or renderer execution. Actual FBO occlusion, 2D picking and Viewpoint display remain for user acceptance."}
(ART / "asset_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in report.items() if k != "meaningfulChecks"}, indent=2))
