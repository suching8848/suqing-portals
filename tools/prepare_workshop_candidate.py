"""Prepare and verify a new local native Workshop draft; never call Steam or deploy.

The selected C cover is exported mechanically to a 512px preview. Runtime files
remain byte-identical to the offline-validated source. The independent icon is
copied outside upload content for user review, without inferring its approval.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import argparse
import hashlib
import json
import re
import shutil
from PIL import Image
from workshop_identity import resolve_workshop_item, native_item_id_lines

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT / 'publishing/ReleasePrep_20261106'
SOURCE = ROOT / 'mods/SuQingPortals'

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def tree(folder):
    result = {}
    for p in sorted(folder.rglob('*')):
        if p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()):
            raise ValueError('Linked candidate resource: ' + str(p))
        if p.is_file():
            result[p.relative_to(folder).as_posix()] = {'bytes': p.stat().st_size, 'sha256': digest(p)}
    if not result or len(result) != len({p.casefold() for p in result}):
        raise ValueError('Empty or case-colliding candidate tree')
    return result

def json_write(p, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stamp', default=datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S'))
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9]{8}_[0-9]{6}', args.stamp):
        raise ValueError('Use a dated, path-free stamp')
    info = dict(line.split('=', 1) for line in (SOURCE / '42/mod.info').read_text(encoding='utf-8-sig').splitlines() if '=' in line)
    version = info['modversion']
    item_id = resolve_workshop_item(ROOT / 'publishing', info['id'])
    assert info['id'] == 'SuQingPortals' and 'test' in version and not info.get('require')
    validation_path = ROOT / 'tests/results/offline-validation.json'
    validation = json.loads(validation_path.read_text(encoding='utf-8'))
    runtime = tree(SOURCE / '42')
    assert validation['result'] == 'PASS' and validation['version'] == version
    assert {p: e['sha256'] for p, e in runtime.items()} == validation['runtime_sha256'], 'Runtime changed after offline validation'
    source = tree(SOURCE)
    assert not any(Path(p).suffix.lower() in {'.jar', '.dll', '.class', '.so', '.dylib'} for p in source), 'Pure-Lua package contains a binary loader'
    selected = json.loads((PREP / 'art/selection.json').read_text(encoding='utf-8'))
    assert selected['selected_variant'] == selected['user_selection'] == 'C'
    cover = PREP / selected['selected_cover']
    assert digest(cover) == selected['selected_cover_sha256']
    description_path = PREP / 'text/workshop-description.bilingual-short.bbcode.txt'
    description = description_path.read_text(encoding='utf-8-sig').replace('\r\n', '\n').strip()
    title = "蘇清的传送门 | SuQing's Portals [SP Test]"
    assert 0 < len(title.encode('utf-8')) <= 128
    assert 0 < len(description.encode('utf-8')) < 8000 and '\0' not in description
    output = ROOT / 'release' / (version + '_' + args.stamp + '_candidate')
    if output.exists():
        raise FileExistsError('Keep the previous frozen draft: ' + str(output))
    upload = output / 'workshop-upload/SuQingPortals'
    content = upload / 'Contents/mods/SuQingPortals'
    content.parent.mkdir(parents=True)
    shutil.copytree(SOURCE, content)
    assert tree(content) == source
    for name in ('workshop-description.zh.bbcode.txt', 'workshop-description.en.bbcode.txt', 'workshop-description.bilingual-short.bbcode.txt', 'changelog.zh-en.md'):
        dst = output / 'publication-text' / name
        dst.parent.mkdir(exist_ok=True)
        shutil.copy2(PREP / 'text' / name, dst)
    with Image.open(cover) as im:
        im.convert('RGB').resize((512, 512), Image.Resampling.LANCZOS).save(upload / 'preview.png', optimize=True)
    with Image.open(upload / 'preview.png') as im:
        assert im.format == 'PNG' and im.size == (512, 512)
    assert (upload / 'preview.png').stat().st_size < 1_000_000
    fields = ['version=1'] + native_item_id_lines(item_id) + ['title=' + title]
    fields += ['description=' + line for line in description.split('\n')]
    fields += ['tags=Build 42;Building;Items;QoL', 'visibility=private']
    (upload / 'workshop.txt').write_text('\n'.join(fields) + '\n', encoding='utf-8')
    parsed = (upload / 'workshop.txt').read_text(encoding='utf-8').splitlines()
    readback = '\n'.join(line.split('=', 1)[1] for line in parsed if line.startswith('description='))
    assert readback == description
    proposal = output / 'art-review/icon-128.png'
    proposal.parent.mkdir()
    shutil.copy2(PREP / 'art/exports/icon-128.png', proposal)
    manifest = {
        'prepared_at_bjt': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'mod_id': info['id'], 'version': version, 'workshop_item_id': item_id, 'status': 'LOCAL_PRIVATE_TEST_CANDIDATE_NOT_UPLOADED',
        'native_structure_complete': True, 'publication_ready': False,
        'gameplay_accepted': False, 'icon_approved': False,
        'required_workshop_ids': [], 'optional_mod_ids': ['Viewpoint'],
        'upload_directory': str(upload), 'title_utf8_bytes': len(title.encode('utf-8')),
        'description_utf8_bytes': len(description.encode('utf-8')),
        'preview_bytes': (upload / 'preview.png').stat().st_size,
        'selected_cover_variant': 'C', 'selected_cover_sha256': digest(cover),
        'preview_export': 'Mechanical 512px RGB PNG export; selected master unchanged',
        'runtime_source_equal': True, 'runtime_files': source,
        'offline_validation': {'path': str(validation_path), 'sha256': digest(validation_path), 'runtime_hashes_match': True, 'tests_rerun': False},
        'icon': {'status': 'INDEPENDENT_PROPOSAL_PENDING_USER_REVIEW', 'proposal': 'art-review/icon-128.png', 'sha256': digest(proposal), 'runtime_test_icon_retained': True},
        'open_items': ['User reviews independent icon before runtime art replacement', 'User tests latest UI, power/recipe and long-distance/recovery behavior', 'Explicit later Git push / Workshop publication instruction'],
        'workshop_mutations': [], 'personal_environment_modified': False,
    }
    json_write(output / 'candidate.json', manifest)
    manifest['upload_files'] = tree(upload)
    archive = output / 'SuQingPortals-native-workshop-draft.zip'
    with ZipFile(archive, 'x', compression=ZIP_DEFLATED) as z:
        for p in sorted(upload.rglob('*')):
            if p.is_file():
                z.write(p, 'SuQingPortals/' + p.relative_to(upload).as_posix())
    with ZipFile(archive) as z:
        assert z.testzip() is None
        entries = {i.filename.removeprefix('SuQingPortals/'): {'bytes': i.file_size, 'sha256': hashlib.sha256(z.read(i)).hexdigest()} for i in z.infolist()}
        assert entries == manifest['upload_files']
    manifest['archive_sha256'] = digest(archive)
    json_write(output / 'candidate.json', manifest)
    assert tree(SOURCE) == source, 'Source changed while freezing'
    (output / 'README-CANDIDATE.txt').write_text(
        'LOCAL TEST CANDIDATE ONLY. Not uploaded or published.\n'
        'Native upload folder: workshop-upload/SuQingPortals. Keep candidate.json and art-review outside Contents.\n'
        'The selected C cover is used. The independent icon still needs user review; runtime test icon is retained.\n'
        'Latest gameplay and recovery acceptance remains pending. No game, Git push or Workshop action is run here.\n'
        '本地测试候选，尚未上传或发布。封面沿用选定C；独立icon待确认，包内仍为测试icon。\n'
        '最新游戏行为仍待用户验收；准备材料不表示稳定版或已公开。\n', encoding='utf-8')
    json_write(ROOT / 'publishing/latest-preparation.json', {
        'prepared_at_bjt': manifest['prepared_at_bjt'], 'mod_id': info['id'], 'version': version,
        'release_manifest': str(output / 'candidate.json'), 'workshop_upload_folder': str(upload),
        'workshop_item_id': item_id,
        'uploaded': False, 'git_committed_or_pushed': False, 'publication_ready': False,
        'description_utf8_bytes': manifest['description_utf8_bytes'],
    })
    print(json.dumps({'output': str(output), 'files': len(source), 'description_utf8_bytes': manifest['description_utf8_bytes'], 'preview_bytes': manifest['preview_bytes'], 'zip_verified': True, 'runtime_unchanged': True, 'publication_ready': False}, ensure_ascii=False))

if __name__ == '__main__':
    main()
