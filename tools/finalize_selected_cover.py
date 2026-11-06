"""Apply the user's selected existing cover; only copies PNGs and updates local receipts."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json
import shutil

from PIL import Image
from deploy_power_ui_upgrade import deployment as deploy


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    root, out = deploy.ROOT, deploy.OUT
    prep = root / 'publishing/ReleasePrep_20261106'
    art = prep / 'art'
    selection_path = art / 'selection.json'
    if selection_path.exists():
        raise RuntimeError('Selection already recorded; inspect instead of applying again')
    deploy.stopped()
    val_path = root / 'tests/results/offline-validation.json'
    val = read(val_path)
    current = read(out / 'current-test-version.json')
    source_before = deploy.tree(deploy.SOURCE)
    if source_before != current['runtime_sha256'] or source_before != deploy.tree(deploy.TARGET):
        raise RuntimeError('Source, current receipt or isolated runtime differ')
    if val['result'] != 'PASS' or source_before != {'42/' + k: v for k, v in val['runtime_sha256'].items()}:
        raise RuntimeError('Source differs from validated candidate')
    if deploy.sha(Path(r'D:\steam\steamapps\common\ProjectZomboid\projectzomboid.jar')) != val['game_jar_sha256']:
        raise RuntimeError('Game changed after functional validation')
    old_state = read(deploy.STATE)
    saved = deploy.tree(Path(old_state['test_save']))
    formal = deploy.protected()
    foundation = deploy.foundation()
    exports = read(art / 'exports.json')
    selected = art / 'exports/C-1024.png'
    master = art / 'masters/C.png'
    if deploy.sha(selected) != exports['exports']['art/exports/C-1024.png']['sha256']:
        raise RuntimeError('Selected export changed')
    if deploy.sha(master) != exports['masters_sha256']['C']:
        raise RuntimeError('Selected original changed')
    with Image.open(selected) as image:
        if image.format != 'PNG' or image.size != (1024, 1024):
            raise RuntimeError('Selected export has unexpected format/dimensions')
        image.verify()
    now = datetime.now(timezone(timedelta(hours=8)))
    folder = out / ('ArtFinal_C_' + now.strftime('%Y%m%d_%H%M%S'))
    folder.mkdir()
    for path, name in ((deploy.SOURCE / '42/poster.png', 'previous-poster.png'),
                       (val_path, 'previous-offline-validation.json'),
                       (out / 'current-test-version.json', 'previous-current-test-version.json')):
        shutil.copy2(path, folder / name)
        if deploy.sha(path) != deploy.sha(folder / name):
            raise RuntimeError('Recovery copy differs')
    final = art / 'final'
    final.mkdir(exist_ok=True)
    for name in ('poster.png', 'cover.png'):
        if (final / name).exists():
            raise RuntimeError('Final artwork already exists')
        shutil.copy2(selected, final / name)
    selection = dict(selected_variant='C', name='雨夜归途', user_selection='C', selected_at=now.isoformat(),
        source_master='art/masters/C.png', source_master_sha256=deploy.sha(master),
        selected_cover='art/final/cover.png', selected_cover_sha256=deploy.sha(final / 'cover.png'),
        selected_poster='art/final/poster.png', selected_poster_sha256=deploy.sha(final / 'poster.png'),
        operation='Byte-identical copy of the existing user-selected image; no regeneration or creative edits',
        icon_changed=False, published=False)
    deploy.stopped()
    for target in (deploy.SOURCE / '42/poster.png', deploy.TARGET / '42/poster.png'):
        if not target.resolve().is_relative_to(target.parent.parent.resolve()) or target.is_symlink():
            raise RuntimeError('Redirected artwork destination')
        shutil.copy2(final / 'poster.png', target)
    source_after = deploy.tree(deploy.SOURCE)
    changes = [k for k in set(source_before) | set(source_after) if source_before.get(k) != source_after.get(k)]
    if changes != ['42/poster.png'] or source_after != deploy.tree(deploy.TARGET):
        raise RuntimeError('Unexpected runtime change')
    if saved != deploy.tree(Path(old_state['test_save'])) or formal != deploy.protected() or foundation != deploy.foundation():
        raise RuntimeError('Save, protected configuration or foundation changed')
    write(selection_path, selection)
    # Retain the original test evidence and explicitly derive only the PNG hash.
    val['runtime_sha256']['poster.png'] = source_after['42/poster.png']
    val['artwork_only_update'] = dict(at=now.isoformat(), selected_variant='C', changed_files=['poster.png'],
        previous_validation=str(folder / 'previous-offline-validation.json'),
        previous_validation_sha256=deploy.sha(folder / 'previous-offline-validation.json'),
        functional_checks_reused_without_rerun=True, executable_files_unchanged=True,
        png_format='PNG', dimensions=[1024, 1024], image_decode_verified=True)
    write(val_path, val)
    receipt = dict(at=now.isoformat(), version=current['version'], selected_variant='C', changes=changes,
        runtime_before=source_before, runtime_after=source_after, selection_record=str(selection_path),
        old_poster=str(folder / 'previous-poster.png'), old_poster_sha256=deploy.sha(folder / 'previous-poster.png'),
        test_save_files=len(saved), test_save_sha256_unchanged=True, formal_protected_unchanged=True,
        foundation_unchanged=True, icon_changed=False, code_changed=False, game_started=False, published=False)
    write(folder / 'artwork-deployment-receipt.json', receipt)
    current.update(runtime_sha256=source_after, artwork_receipt=str(folder / 'artwork-deployment-receipt.json'),
        artwork_updated_at=now.isoformat(), selected_cover='C')
    write(out / 'current-test-version.json', current)
    provenance = read(art / 'provenance.json')
    provenance['selection_status'] = 'User selected C (雨夜归途); applied to local poster and publishing cover; not published'
    provenance['selected_variant'] = 'C'
    provenance['selection_record'] = 'art/selection.json'
    write(art / 'provenance.json', provenance)
    gallery = prep / '封面候选.html'
    text = gallery.read_text(encoding='utf-8')
    text = text.replace('请看图后在对话中回复 A／B／C／D；当前没有选定稿，也没有发布。',
        '用户已选定 C「雨夜归途」；封面及poster已更新，尚未发布。其余候选保留备查。')
    gallery.write_text(text, encoding='utf-8')
    print(json.dumps(dict(selected='C', changed_files=changes, receipt=str(folder / 'artwork-deployment-receipt.json'),
        test_save_files=len(saved), game_started=False, published=False), ensure_ascii=False))


if __name__ == '__main__':
    main()
