"""Mechanical size exports and comparison layouts only; generated masters stay intact."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import hashlib
import json
import html

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT / 'publishing/ReleasePrep_20261106'
ART = PREP / 'art'
EXPORTS = ART / 'exports'
EXPORTS.mkdir(exist_ok=True)
LABELS = {'A': '工坊初启', 'B': '跨门归来', 'C': '雨夜归途', 'D': '双门远行'}
masters = {name: ART / 'masters' / (name + '.png') for name in (*LABELS, 'icon')}
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
before = {name: sha(p) for name, p in masters.items()}
font_path = Path(r'C:\Windows\Fonts\msyh.ttc')
font = ImageFont.truetype(str(font_path), 28)
small = ImageFont.truetype(str(font_path), 17)
exports = []

sheet = Image.new('RGB', (1280, 1400), '#171323')
draw = ImageDraw.Draw(sheet)
for index, (name, label) in enumerate(LABELS.items()):
    source = Image.open(masters[name]).convert('RGB')
    if source.width != source.height:
        raise RuntimeError('Cover master is not square: ' + name)
    for size in (256, 1024):
        target = EXPORTS / f'{name}-{size}.png'
        source.resize((size, size), Image.Resampling.LANCZOS).save(target, format='PNG')
        exports.append(target)
    x = 24 + (index % 2) * 632
    y = 16 + (index // 2) * 696
    draw.text((x, y), name + '  ' + label, font=font, fill='#f2eaff')
    sheet.paste(source.resize((608, 608), Image.Resampling.LANCZOS), (x, y + 48))
sheet.save(ART / '四版封面对比.png', format='PNG')

icon = Image.open(masters['icon']).convert('RGBA')
alpha = icon.getchannel('A')
if alpha.getextrema()[0] != 0 or not any(x > 0 for x in alpha.getdata()):
    raise RuntimeError('Icon has no real transparent/visible pixel combination')
for size in (32, 64, 128, 256):
    target = EXPORTS / f'icon-{size}.png'
    icon.resize((size, size), Image.Resampling.LANCZOS).save(target, format='PNG')
    exports.append(target)

# These icons are pasted at their actual 32/64/128/256 pixel dimensions.
qa = Image.new('RGB', (820, 700), '#171323')
q = ImageDraw.Draw(qa)
for row, background in enumerate(('#252033', '#eeeaf5')):
    q.text((18, row * 340 + 8), '实际像素尺寸 · ' + ('深色底' if row == 0 else '浅色底'), font=small, fill='#d6c8ed')
    for index, size in enumerate((32, 64, 128, 256)):
        x = (18, 120, 262, 478)[index]
        y = row * 340 + 44
        q.rectangle((x, y, x + size + 16, y + 272), fill=background)
        qa.paste(Image.open(EXPORTS / f'icon-{size}.png'), (x + 8, y + 8), Image.open(EXPORTS / f'icon-{size}.png'))
        q.text((x, y + 280), str(size) + ' px', font=small, fill='#d6c8ed')
qa.save(ART / 'icon实际尺寸检查.png', format='PNG')

cards = ''.join(f'<article><h2>{name} · {html.escape(label)}</h2><a href="art/masters/{name}.png" target="_blank"><img src="art/exports/{name}-1024.png" alt="{name} {html.escape(label)}"></a><p><a href="art/masters/{name}.png">查看原图</a> · <a href="art/exports/{name}-1024.png">1024导出</a></p></article>' for name, label in LABELS.items())
gallery = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>蘇清的传送门 · 封面候选</title><style>body{{margin:0;background:#171323;color:#eee8fa;font-family:system-ui,"Microsoft YaHei",sans-serif}}main{{max-width:1300px;margin:auto;padding:24px}}h1{{font-size:26px}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}}article{{background:#252033;border:1px solid #58436e;border-radius:14px;padding:14px}}h2{{margin:0 0 12px;font-size:21px}}img{{width:100%;height:auto;border-radius:8px}}a{{color:#d1afff}}.icon{{width:128px;background:repeating-conic-gradient(#d9d3e4 0% 25%,#f7f3fb 0% 50%) 50%/20px 20px;padding:16px}}@media(max-width:700px){{.grid{{grid-template-columns:1fr}}}}</style><main><h1>蘇清的传送门 · 四版封面候选</h1><p>请看图后在对话中回复 A／B／C／D；当前没有选定稿，也没有发布。点击图片查看1254像素原图。</p><div class="grid">{cards}</div><h2>独立生成的四槽拱门 icon</h2><img class="icon" src="art/exports/icon-256.png" alt="独立透明icon"><p><a href="art/icon实际尺寸检查.png">查看32／64／128／256实际尺寸</a> · <a href="text/workshop-description.zh.bbcode.txt">中文介绍</a> · <a href="text/workshop-description.en.bbcode.txt">English description</a></p></main></html>'''
(PREP / '封面候选.html').write_text(gallery, encoding='utf-8')
if before != {name: sha(p) for name, p in masters.items()}:
    raise RuntimeError('Master changed during mechanical export')
record = dict(operation='Mechanical size exports/contact sheet/gallery only; no creative raster editing',
    selected_cover=None, published=False, masters_sha256=before, masters_preserved=True,
    icon_independently_generated=True, icon_alpha_extrema=alpha.getextrema(),
    exports={p.relative_to(PREP).as_posix(): dict(bytes=p.stat().st_size, sha256=sha(p)) for p in exports},
    comparison='art/四版封面对比.png', icon_actual_sizes='art/icon实际尺寸检查.png', gallery='封面候选.html',
    generation='built-in image_gen; original prompts in art/prompts.json', runtime_art_replaced=False)
(ART / 'exports.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(dict(exports=len(exports), comparison=str(ART / '四版封面对比.png'), gallery=str(PREP / '封面候选.html'), masters_preserved=True), ensure_ascii=False))
