"""Snapshot/deploy this test instance only. Never starts the game."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
GAME = Path(r'D:\steam\steamapps\common\ProjectZomboid')
PERSONAL = Path(r'C:\Users\15792\Zomboid')
OUT = GAME / 'CodexAssets/SuQingPortals_20261106'
ISO = OUT / 'IsolatedTest'
DATA = ISO / 'data'
STATE = ROOT / 'publishing/current-upgrade.json'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def protected():
    files = [PERSONAL / p for p in ('options.ini', 'mods/default.txt', 'latestSave.ini', 'viewpoint.properties', 'pzopt/options.ini')]
    files += [GAME / p for p in ('ProjectZomboid64.json', 'projectzomboid.jar', 'pzopt/aot/pzopt.jar', 'AGENTS.md')]
    lines = (PERSONAL / 'latestSave.ini').read_text(encoding='utf-8-sig').splitlines()
    save = PERSONAL / 'Saves' / lines[1] / lines[0]
    files += [save / p for p in ('mods.txt', 'map_sand.bin')]
    return {str(p): sha(p) for p in files if p.is_file()}


def snapshot():
    if STATE.exists():
        raise RuntimeError('Upgrade state already exists; inspect before creating a new snapshot')
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
    folder = OUT / ('Upgrade_0.1.1_' + stamp)
    folder.mkdir()
    formal = protected()
    lines = (DATA / 'latestSave.ini').read_text(encoding='utf-8-sig').splitlines()
    save = DATA / 'Saves' / lines[1] / lines[0]
    save.resolve().relative_to(DATA.resolve())
    if not save.is_dir():
        raise RuntimeError('No current test save found')
    files = [p for p in save.rglob('*') if p.is_file()]
    save_files = len(files)
    files += [p for p in (DATA / 'mods/SuQingPortals').rglob('*') if p.is_file()]
    files += [ISO / p for p in ('Launch-Isolated.ps1', 'Start-Portal-Test.cmd', 'launch-baseline.json', 'data/mods/default.txt',
        'data/mods/reset-mods-42_00.txt', 'data/options.ini', 'data/latestSave.ini', 'data/pzopt/options.ini') if (ISO / p).is_file()]
    manifest = {p.relative_to(ISO).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in files}
    archive = folder / 'isolated-save-and-portal-before.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, p.relative_to(ISO).as_posix())
        z.writestr('snapshot-manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise RuntimeError('Snapshot CRC failed')
        for rel, item in manifest.items():
            if hashlib.sha256(z.read(rel)).hexdigest() != item['sha256'] or sha(ISO / rel) != item['sha256']:
                raise RuntimeError('Snapshot/source changed: ' + rel)
    state = dict(folder=str(folder), archive=str(archive), archive_sha256=sha(archive),
        test_save=str(save), full_test_save_files=save_files, snapshot_files=len(manifest),
        verified_every_member=True, formal_protected_before=formal, game_started=False)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    (folder / 'recovery-receipt.json').write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: state[k] for k in ('folder', 'archive', 'full_test_save_files', 'verified_every_member')}, ensure_ascii=False))


def deploy():
    state = json.loads(STATE.read_text(encoding='utf-8'))
    validation = json.loads((ROOT / 'tests/results/offline-validation.json').read_text(encoding='utf-8'))
    source = ROOT / 'mods/SuQingPortals'
    if sha(GAME / 'projectzomboid.jar') != validation.get('game_jar_sha256'):
        raise RuntimeError('Installed game changed after offline validation')
    current = {p.relative_to(source / '42').as_posix(): sha(p) for p in (source / '42').rglob('*') if p.is_file()}
    if validation.get('result') != 'PASS' or current != validation.get('runtime_sha256'):
        raise RuntimeError('Runtime does not match successful offline checks')
    folder = Path(state['folder'])
    staging = folder / 'frozen-candidate/SuQingPortals'
    shutil.copytree(source, staging)
    target = DATA / 'mods/SuQingPortals'
    target.resolve().relative_to(DATA.resolve())
    if target.resolve() != target.absolute():
        raise RuntimeError('Refusing a deployed-mod link or redirected test path')
    # The previous full test save and old runtime were verified before this write.
    shutil.copytree(staging, target, dirs_exist_ok=True)
    expected = {p.relative_to(source).as_posix(): sha(p) for p in source.rglob('*') if p.is_file()}
    actual = {p.relative_to(target).as_posix(): sha(p) for p in target.rglob('*') if p.is_file()}
    if expected != actual:
        raise RuntimeError('Deployed runtime tree differs; preserve recovery archive and inspect')
    with zipfile.ZipFile(state['archive']) as z:
        snapshot = json.loads(z.read('snapshot-manifest.json'))
    world_members = {rel: item for rel, item in snapshot.items() if rel.startswith('data/Saves/')}
    test_save_unchanged = all((ISO / rel).is_file() and sha(ISO / rel) == item['sha256'] for rel, item in world_members.items())
    if not test_save_unchanged:
        raise RuntimeError('Test save changed during deployment; inspect and preserve current progress')
    formal_now = protected()
    changes = {p: {'before': value, 'observed': formal_now.get(p)} for p, value in state['formal_protected_before'].items()
               if formal_now.get(p) != value}
    receipt = dict(version=validation['version'], profile=str(DATA), source=str(ROOT), deployed_files=len(expected),
        runtime_sha256=expected, recovery_archive=state['archive'],
        recovery_archive_sha256=state['archive_sha256'], pzo_retained=True,
        formal_protected_unchanged=not changes, formal_observed_differences=changes,
        formal_save_written=False, test_save_written=False, test_save_sha256_unchanged=test_save_unchanged,
        game_started=False, gameplay_acceptance='pending_user')
    (folder / 'deployment-receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / 'current-test-version.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: receipt[k] for k in ('version', 'deployed_files', 'formal_protected_unchanged', 'recovery_archive')}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('snapshot', 'deploy'))
    args = parser.parse_args()
    snapshot() if args.action == 'snapshot' else deploy()
