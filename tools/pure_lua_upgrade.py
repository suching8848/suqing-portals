"""Snapshot/deploy the pure-Lua portal runtime without touching personal saves."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timedelta, timezone
import argparse
from upgrade_isolated import protected

ROOT = Path(__file__).resolve().parents[1]
GAME = Path(r'D:\steam\steamapps\common\ProjectZomboid')
OUT = GAME / 'CodexAssets/SuQingPortals_20261106'
ISO = OUT / 'IsolatedTest'
DATA = ISO / 'data'
STATE = ROOT / 'publishing/pure-lua-upgrade-state.json'
VERSION = '0.1.2-lua-test.1'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def verify_world(archive, save):
    prefix = save.relative_to(ISO).as_posix() + '/'
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read('snapshot-manifest.json'))
    members = {rel: item for rel, item in manifest.items() if rel.startswith(prefix)}
    current = {p.relative_to(ISO).as_posix(): p for p in save.rglob('*') if p.is_file()}
    if not members or set(members) != set(current):
        return None
    if not all(sha(current[rel]) == item['sha256'] for rel, item in members.items()):
        return None
    return members


def foundation():
    """Read back the actual retained PZO/Viewpoint/language foundation."""
    baseline = json.loads((ISO / 'launch-baseline.json').read_text(encoding='utf-8-sig'))
    for path, expected in baseline.items():
        if sha(Path(path)) != expected:
            raise RuntimeError('Installed PZO/game foundation changed: ' + path)
    files = [ISO / p for p in ('Launch-Isolated.ps1', 'Start-Portal-Test.cmd', 'launch-baseline.json',
        'data/mods/default.txt', 'data/mods/reset-mods-42_00.txt', 'data/options.ini',
        'data/latestSave.ini', 'data/pzopt/options.ini')]
    files += list((ISO / 'bootstrap').rglob('*'))
    for name in ('ZombieBuddy', 'Viewpoint', 'B42ModTrans_CN', 'B42Trans_CN'):
        folder = DATA / 'mods' / name
        if not folder.is_dir():
            raise RuntimeError('Missing retained foundation mod: ' + name)
        files += list(folder.rglob('*'))
    return {str(p): sha(p) for p in files if p.is_file()}


def snapshot():
    if STATE.exists():
        raise RuntimeError('Pure-Lua upgrade snapshot already exists; inspect instead of replacing')
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
    folder = OUT / ('Upgrade_0.1.2_lua_' + stamp)
    folder.mkdir()
    lines = (DATA / 'latestSave.ini').read_text(encoding='utf-8-sig').splitlines()
    save = DATA / 'Saves' / lines[1] / lines[0]
    save.resolve().relative_to(DATA.resolve())
    old = json.loads((ROOT / 'publishing/current-upgrade.json').read_text(encoding='utf-8'))
    world_archive = Path(old['archive'])
    members = verify_world(world_archive, save)
    reused = members is not None and sha(world_archive) == old['archive_sha256']
    if not reused:
        world_archive = folder / 'current-isolated-world.zip'
        worlds = [p for p in save.rglob('*') if p.is_file()]
        members = {p.relative_to(ISO).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in worlds}
        with zipfile.ZipFile(world_archive, 'w', zipfile.ZIP_DEFLATED) as z:
            for p in worlds: z.write(p, p.relative_to(ISO).as_posix())
            z.writestr('snapshot-manifest.json', json.dumps(members, ensure_ascii=False, indent=2))
        with zipfile.ZipFile(world_archive) as z:
            if z.testzip() is not None: raise RuntimeError('World snapshot CRC failure')
            for rel, item in members.items():
                if hashlib.sha256(z.read(rel)).hexdigest() != item['sha256']: raise RuntimeError('World snapshot readback differs')
        if verify_world(world_archive, save) is None: raise RuntimeError('World changed during snapshot')
    files = [p for p in (DATA / 'mods/SuQingPortals').rglob('*') if p.is_file()]
    files += [ISO / p for p in ('Launch-Isolated.ps1', 'Start-Portal-Test.cmd', 'launch-baseline.json',
        'data/mods/default.txt', 'data/mods/reset-mods-42_00.txt', 'data/latestSave.ini')]
    manifest = {p.relative_to(ISO).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in files}
    runtime_archive = folder / 'previous-0.1.1-runtime-and-entry.zip'
    with zipfile.ZipFile(runtime_archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in files: z.write(p, p.relative_to(ISO).as_posix())
        z.writestr('snapshot-manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(runtime_archive) as z:
        if z.testzip() is not None: raise RuntimeError('Runtime snapshot CRC failure')
        for rel, item in manifest.items():
            if hashlib.sha256(z.read(rel)).hexdigest() != item['sha256'] or sha(ISO / rel) != item['sha256']:
                raise RuntimeError('Runtime snapshot/source readback differs')
    state = dict(version=VERSION, folder=str(folder), test_save=str(save), world_archive=str(world_archive),
        world_archive_sha256=sha(world_archive), reused_verified_world_snapshot=reused, world_files=len(members),
        previous_runtime_archive=str(runtime_archive), previous_runtime_sha256=sha(runtime_archive),
        previous_runtime_manifest=manifest, formal_before=protected(), game_started=False)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    (folder / 'recovery-receipt.json').write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: state[k] for k in ('folder', 'world_files', 'reused_verified_world_snapshot', 'previous_runtime_archive')}, ensure_ascii=False))


def deploy():
    state = json.loads(STATE.read_text(encoding='utf-8'))
    validation = json.loads((ROOT / 'tests/results/offline-validation.json').read_text(encoding='utf-8'))
    source = ROOT / 'mods/SuQingPortals'
    runtime = source / '42'
    files = {p.relative_to(runtime).as_posix(): sha(p) for p in runtime.rglob('*') if p.is_file()}
    if validation.get('result') != 'PASS' or validation.get('version') != VERSION or files != validation.get('runtime_sha256'):
        raise RuntimeError('Pure-Lua runtime does not match successful offline checks')
    if any(p.suffix.lower() in ('.jar', '.class') for p in source.rglob('*') if p.is_file()):
        raise RuntimeError('Java artifacts remain inside the pure-Lua runtime')
    if sha(GAME / 'projectzomboid.jar') != validation.get('game_jar_sha256'):
        raise RuntimeError('Game changed after offline validation')
    if sha(Path(state['world_archive'])) != state['world_archive_sha256']:
        raise RuntimeError('Recovery world archive changed')
    if verify_world(Path(state['world_archive']), Path(state['test_save'])) is None:
        raise RuntimeError('Test world changed after snapshot; inspect before deployment')
    foundation_before = foundation()
    target = DATA / 'mods/SuQingPortals'
    target.resolve().relative_to(DATA.resolve())
    if target.resolve() != target.absolute(): raise RuntimeError('Refusing redirected test-mod path')
    current = {p.relative_to(ISO).as_posix(): sha(p) for p in target.rglob('*') if p.is_file()}
    previous = {p: info['sha256'] for p, info in state['previous_runtime_manifest'].items()
                if p.startswith('data/mods/SuQingPortals/')}
    if current != previous:
        raise RuntimeError('Deployed portal changed after recovery snapshot; inspect before overwrite')
    frozen = Path(state['folder']) / 'frozen-candidate/SuQingPortals'
    shutil.copytree(source, frozen)
    obsolete = target / '42/media/java/SuQingPortals.jar'
    if obsolete.exists():
        rel = obsolete.relative_to(ISO).as_posix()
        if sha(obsolete) != state['previous_runtime_manifest'][rel]['sha256']:
            raise RuntimeError('Old test JAR changed after recovery snapshot')
        obsolete.resolve().relative_to(target.resolve())
        obsolete.unlink()  # Explicitly retired owned component, verified in recovery ZIP.
    shutil.copytree(frozen, target, dirs_exist_ok=True)
    expected = {p.relative_to(source).as_posix(): sha(p) for p in source.rglob('*') if p.is_file()}
    actual = {p.relative_to(target).as_posix(): sha(p) for p in target.rglob('*') if p.is_file()}
    if expected != actual: raise RuntimeError('Pure-Lua deployment tree differs')
    if verify_world(Path(state['world_archive']), Path(state['test_save'])) is None:
        raise RuntimeError('Test save changed during deployment; preserve it and inspect')
    if foundation() != foundation_before:
        raise RuntimeError('Retained isolation foundation differs; preserve it and inspect')
    now = protected()
    changes = {p: {'before': value, 'observed': now.get(p)} for p, value in state['formal_before'].items() if now.get(p) != value}
    receipt = dict(version=VERSION, profile=str(DATA), deployed_files=len(expected), runtime_sha256=expected,
        portal_java_artifacts=0, pzo_retained=True, viewpoint_retained=True,
        isolation_foundation_sha256=foundation_before, foundation_unchanged=True,
        test_save_sha256_unchanged=True, formal_save_written=False, test_save_written=False,
        formal_observed_differences=changes, formal_protected_unchanged=not changes,
        recovery=state, offline_validation=str(ROOT / 'tests/results/offline-validation.json'),
        gameplay_acceptance='pending_user', game_started=False)
    (Path(state['folder']) / 'deployment-receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / 'current-test-version.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: receipt[k] for k in ('version', 'deployed_files', 'portal_java_artifacts', 'test_save_sha256_unchanged', 'formal_protected_unchanged')}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('snapshot', 'deploy'))
    args = parser.parse_args()
    snapshot() if args.action == 'snapshot' else deploy()
