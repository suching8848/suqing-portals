"""Freeze the user-accepted 0.1.4 release for the existing Workshop item; no upload."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import hashlib
import json
import shutil
import zipfile
from PIL import Image
from workshop_identity import resolve_workshop_item

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'mods/SuQingPortals'
PUB = ROOT / 'publishing/Release_0.1.4'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree(folder):
    result = {}
    for path in sorted(folder.rglob('*')):
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            raise RuntimeError('Linked release input: ' + str(path))
        if path.is_file():
            result[path.relative_to(folder).as_posix()] = {'bytes': path.stat().st_size, 'sha256': sha(path)}
    return result


def write(path, record):
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    accepted = json.loads((PUB / 'acceptance.json').read_text(encoding='utf-8'))
    validation = json.loads((ROOT / 'tests/results/offline-validation.json').read_text(encoding='utf-8'))
    info = dict(line.split('=', 1) for line in (SOURCE / '42/mod.info').read_text(encoding='utf-8').splitlines() if '=' in line)
    if info['id'] != 'SuQingPortals' or info['modversion'] != '0.1.4' or resolve_workshop_item(ROOT / 'publishing', 'SuQingPortals') != '3834693880':
        raise RuntimeError('Release identity/version differs')
    if validation['result'] != 'PASS' or validation['version'] != '0.1.4':
        raise RuntimeError('Successful stable-version validation is missing')
    source = tree(SOURCE)
    current = {p.removeprefix('42/'): entry['sha256'] for p, entry in source.items()}
    if current != validation['runtime_sha256'] or any(Path(p).suffix.lower() in {'.jar', '.dll', '.class', '.so', '.dylib'} for p in source):
        raise RuntimeError('Source differs from validated pure-Lua release')
    changed = {p for p in set(current) | set(accepted['tested_runtime_sha256']) if current.get(p) != accepted['tested_runtime_sha256'].get(p)}
    if changed != {'mod.info', 'media/lua/shared/SuQingPortals/Core.lua'}:
        raise RuntimeError('Promotion changed files beyond the approved metadata/version constants')
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
    output = ROOT / 'release' / ('0.1.4_' + stamp + '_release')
    if output.exists():
        raise RuntimeError('Preserve the earlier frozen release')
    upload = output / 'workshop-upload/SuQingPortals'
    content = upload / 'Contents'
    runtime = content / 'mods/SuQingPortals'
    shutil.copytree(SOURCE, runtime)
    if tree(runtime) != source:
        raise RuntimeError('Frozen runtime readback differs')
    texts = output / 'publication-text'
    shutil.copytree(PUB / 'text', texts)
    title = (texts / 'title.txt').read_text(encoding='utf-8').strip()
    description = (texts / 'workshop-description.zh-en.bbcode.txt').read_text(encoding='utf-8').strip()
    note_path = texts / 'changelog.zh-en.md'
    if not 0 < len(title.encode('utf-8')) <= 128 or not 0 < len(description.encode('utf-8')) < 8000:
        raise RuntimeError('Title/description size exceeds native limits')
    with Image.open(SOURCE / '42/poster.png') as im:
        im.convert('RGB').resize((512, 512), Image.Resampling.LANCZOS).save(upload / 'preview.png', optimize=True)
    with Image.open(upload / 'preview.png') as im:
        if im.format != 'PNG' or im.size != (512, 512) or (upload / 'preview.png').stat().st_size >= 1_000_000:
            raise RuntimeError('Invalid preview')
    fields = ['version=1', 'id=3834693880', 'title=' + title]
    fields += ['description=' + line for line in description.splitlines()]
    fields += ['tags=Build 42;Building;Items;QoL', 'visibility=public']
    (upload / 'workshop.txt').write_text('\n'.join(fields) + '\n', encoding='utf-8')
    files = tree(content)
    tree_hash = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()
    release = dict(schema_version=1, slug='portals', appid=108600, owner='76561198881912882', version='0.1.4',
        content_path=str(content), mod_ids=['SuQingPortals'], mod_versions={'SuQingPortals': '0.1.4'},
        existing_item_id='3834693880', required_workshop_ids=[], tags=['Build 42', 'Building', 'Items', 'QoL'],
        duplicate_keywords=['SuQingPortals', '蘇清的传送门', "SuQing's Portals"], content_tree_sha256=tree_hash,
        new_item_visibility=0, publication_authorized=True,
        readiness=dict(native_structure_complete=True, publication_ready=True, gameplay_accepted=True,
            icon_approved=False, icon_policy='Retain the already installed/published runtime icon; no unselected proposal applied',
            acceptance_scope='User confirmed all tests normal in the isolated B42.21 single-player candidate; no vehicles/multiplayer claim'),
        authorization=dict(user_statement=accepted['user_statement'], backup_required_before_any_publication_or_personal_deployment=True,
            preserve_current_visibility=True),
        title_file=str(texts / 'title.txt'), description_file=str(texts / 'workshop-description.zh-en.bbcode.txt'),
        preview_file=str(upload / 'preview.png'), changenote_file=str(note_path))
    for name in ('title', 'description', 'preview', 'changenote'):
        release[name + '_sha256'] = sha(Path(release[name + '_file']))
    write(output / 'release.json', release)
    archive = output / 'SuQingPortals_0.1.4-native-workshop.zip'
    archived = tree(upload)
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(upload.rglob('*')):
            if path.is_file(): z.write(path, 'SuQingPortals/' + path.relative_to(upload).as_posix())
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise RuntimeError('Frozen archive CRC failed')
        for rel, entry in archived.items():
            data = z.read('SuQingPortals/' + rel)
            if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
                raise RuntimeError('Frozen archive member differs')
    if tree(SOURCE) != source:
        raise RuntimeError('Source changed during freeze')
    pointer = dict(version='0.1.4', frozen_at_bjt=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        output=str(output), release_json=str(output / 'release.json'), workshop_item_id='3834693880',
        archive=str(archive), archive_sha256=sha(archive), runtime_files=len(source), source_equals_frozen=True,
        all_archive_members_verified=True, uploaded=False, personal_deployed=False,
        user_gameplay_accepted=True, gameplay_logic_unchanged_from_tested_candidate=True)
    write(PUB / 'latest-frozen.json', pointer)
    write(output / 'freeze-receipt.json', pointer)
    print(json.dumps(pointer, ensure_ascii=False))


if __name__ == '__main__':
    main()
