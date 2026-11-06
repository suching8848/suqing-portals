"""Export project-owned imagegen masters without replacing their originals."""
from pathlib import Path
from PIL import Image
import argparse
import json
import shutil

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('cover')
parser.add_argument('icon')
args = parser.parse_args()
art = root / 'art'
mod = root / 'mods/SuQingPortals/42'
art.mkdir(exist_ok=True)
for name, source in [('cover-original.png', args.cover), ('icon-original.png', args.icon)]:
    shutil.copy2(source, art / name)
cover = Image.open(art / 'cover-original.png').convert('RGB')
cover.resize((1024, 1024), Image.Resampling.LANCZOS).save(mod / 'poster.png')
cover.resize((1024, 1024), Image.Resampling.LANCZOS).save(root / 'publishing/preview.png')
icon = Image.open(art / 'icon-original.png').convert('RGBA')
exports = art / 'icon-exports'
exports.mkdir(exist_ok=True)
for n in (32, 64, 128, 256):
    icon.resize((n, n), Image.Resampling.LANCZOS).save(exports / ('icon-' + str(n) + '.png'))
icon.resize((256, 256), Image.Resampling.LANCZOS).save(mod / 'icon.png')
(art / 'exports.json').write_text(json.dumps(dict(cover_master=str(art / 'cover-original.png'),
    icon_master=str(art / 'icon-original.png'), icon_alpha_extrema=icon.getchannel('A').getextrema(),
    icon_independently_generated=True, tool='built-in image_gen',
    note='Only format/size exports; source images and character references retained.'), indent=2), encoding='utf-8')
print('Exported cover, independent icon and four actual-size icon previews.')
