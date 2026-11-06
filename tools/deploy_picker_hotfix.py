"""Snapshot and deploy the right-click code fix only; never writes a save."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import argparse
import hashlib
import json
import shutil
import subprocess
import zipfile
from pure_lua_upgrade import foundation
from upgrade_isolated import protected

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(r'D:\steam\steamapps\common\ProjectZomboid\CodexAssets\SuQingPortals_20261106')
ISO = OUT / 'IsolatedTest'
DATA = ISO / 'data'
SOURCE = ROOT / 'mods/SuQingPortals'
TARGET = DATA / 'mods/SuQingPortals'
STATE = ROOT / 'publishing/picker-hotfix-state.json'
VERSION = '0.1.2-lua-test.2'
FROM = '0.1.2-lua-test.1'
LABEL = 'RightClick'
SCOPE = 'Client picker fix plus version markers only; no battery/save schema change'
ALLOWED = {'42/mod.info', '42/media/lua/shared/SuQingPortals/Core.lua', '42/media/lua/client/SuQingPortals/Client.lua'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree(folder):
    return {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}


def stopped():
    # The launcher uses an explicit cache argument; inspect the full command line.
    needle = ('-cachedir=' + str(DATA)).replace("'", "''")
    command = "$p=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(java|javaw|ProjectZomboid).*' -and $_.CommandLine -like '*" + needle + "*' }); $p.Count"
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command], capture_output=True, text=True, check=True)
    if result.stdout.strip() != '0':
        raise RuntimeError('Isolated game is still running; normal user exit is required')


def snapshot():
    if STATE.exists():
        raise RuntimeError('Hotfix snapshot exists; inspect it rather than replacing')
    stopped()
    receipt = json.loads((OUT / 'current-test-version.json').read_text(encoding='utf-8'))
    before = tree(TARGET)
    if receipt['version'] != FROM or before != receipt['runtime_sha256']:
        raise RuntimeError('Deployed version differs from its last receipt; inspect user changes')
    lines = (DATA / 'latestSave.ini').read_text(encoding='utf-8-sig').splitlines()
    save = DATA / 'Saves' / lines[1] / lines[0]
    save.resolve().relative_to(DATA.resolve())
    if not save.is_dir():
        raise RuntimeError('Current test save does not exist')
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
    folder = OUT / ('Hotfix_' + LABEL + '_' + stamp)
    folder.mkdir()
    inputs = [(p, 'mods/SuQingPortals/' + p.relative_to(TARGET).as_posix())
              for p in sorted(TARGET.rglob('*')) if p.is_file()]
    inputs += [(OUT / name, name) for name in ('current-test-version.json', '交付说明.md', '用户测试步骤.md', 'test-package-receipt.json')]
    manifest = {name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p, name in inputs}
    archive = folder / ('previous-' + FROM + '-runtime.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for p, name in inputs:
            z.write(p, name)
        z.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise RuntimeError('Runtime recovery archive CRC failed')
        for p, name in inputs:
            if hashlib.sha256(z.read(name)).hexdigest() != manifest[name]['sha256'] or sha(p) != manifest[name]['sha256']:
                raise RuntimeError('Runtime recovery/source changed during readback')
    shutil.copy2(DATA / 'console.txt', folder / 'reported-error-console.txt')
    state = dict(version=VERSION, previous_version=FROM, folder=str(folder), archive=str(archive),
        archive_sha256=sha(archive), archive_members=len(manifest), runtime_before=before,
        test_save=str(save), test_save_before=tree(save), formal_before=protected(), foundation_before=foundation(),
        scope=SCOPE,
        world_backup_created=False, game_started=False)
    stopped()
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    (folder / 'snapshot-receipt.json').write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(folder=str(folder), save_files=len(state['test_save_before']),
        runtime_backup_sha256=state['archive_sha256']), ensure_ascii=False))


def deploy():
    stopped()
    state = json.loads(STATE.read_text(encoding='utf-8'))
    validation = json.loads((ROOT / 'tests/results/offline-validation.json').read_text(encoding='utf-8'))
    expected = tree(SOURCE)
    checked = {'42/' + p: digest for p, digest in validation['runtime_sha256'].items()}
    if validation['result'] != 'PASS' or validation['version'] != VERSION or expected != checked:
        raise RuntimeError('Candidate does not match successful offline validation')
    if tree(TARGET) != state['runtime_before'] or tree(Path(state['test_save'])) != state['test_save_before']:
        raise RuntimeError('Runtime or test progress changed after snapshot; inspect before overwrite')
    if foundation() != state['foundation_before'] or sha(Path(state['archive'])) != state['archive_sha256']:
        raise RuntimeError('Foundation or recovery archive changed')
    TARGET.resolve().relative_to(DATA.resolve())
    if TARGET.resolve() != TARGET.absolute():
        raise RuntimeError('Refusing redirected test-mod path')
    changes = {p for p in set(expected) | set(state['runtime_before']) if expected.get(p) != state['runtime_before'].get(p)}
    allow_added = globals().get('ALLOW_ADDED_FILES', False)
    old_paths, new_paths = set(state['runtime_before']), set(expected)
    if changes != ALLOWED or not old_paths.issubset(new_paths) or (not allow_added and new_paths != old_paths):
        raise RuntimeError('Unexpected hotfix scope: ' + repr(changes))
    if any(Path(p).suffix.lower() in ('.jar', '.class', '.dll') for p in expected):
        raise RuntimeError('Non-Lua product binary found')
    frozen = Path(state['folder']) / 'frozen-candidate/SuQingPortals'
    shutil.copytree(SOURCE, frozen)
    for rel in sorted(changes):
        shutil.copy2(frozen / rel, TARGET / rel)
    if tree(TARGET) != expected or tree(Path(state['test_save'])) != state['test_save_before']:
        raise RuntimeError('Deployment readback or save preservation failed')
    if foundation() != state['foundation_before']:
        raise RuntimeError('Foundation preservation failed')
    now = protected()
    differences = {p: dict(before=value, observed=now.get(p)) for p, value in state['formal_before'].items() if value != now.get(p)}
    result = dict(version=VERSION, deployed_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        runtime_sha256=expected, deployed_files=len(expected), changed_files=sorted(changes), scope=SCOPE,
        test_save_sha256_unchanged=True, test_save_files=len(state['test_save_before']), formal_observed_differences=differences,
        formal_protected_unchanged=not differences, formal_save_written=False, test_save_written=False,
        foundation_unchanged=True, pzo_retained=True, viewpoint_retained=True, portal_java_artifacts=0,
        snapshot=str(Path(state['folder']) / 'snapshot-receipt.json'), recovery_archive=state['archive'],
        offline_validation=str(ROOT / 'tests/results/offline-validation.json'), gameplay_acceptance='pending_user', game_started=False)
    (Path(state['folder']) / 'deployment-receipt.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / 'current-test-version.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('version', 'changed_files', 'test_save_files', 'test_save_sha256_unchanged', 'formal_protected_unchanged')}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('snapshot', 'deploy'))
    args = parser.parse_args()
    snapshot() if args.action == 'snapshot' else deploy()
