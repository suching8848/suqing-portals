"""Install/enable only SuQingPortals in the latest personal save after verified backup."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import argparse
import hashlib
import json
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PERSONAL = Path(r'C:\Users\15792\Zomboid')
BACKUPS = Path(r'D:\GameBackups\ProjectZomboid')
GAME = Path(r'D:\steam\steamapps\common\ProjectZomboid')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def tree(path):
    return {p.relative_to(path).as_posix(): sha(p) for p in path.rglob('*') if p.is_file()}


def stopped():
    script = "$p=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^ProjectZomboid' -or ($_.Name -match '^javaw?\\.exe$' -and $_.CommandLine -match 'zombie\\.gameStates\\.MainScreenState|-cachedir=') }); $p.Count"
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', script], check=True, capture_output=True, text=True)
    if result.stdout.strip() != '0': raise RuntimeError('A game process is running; normal exit is required')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', type=Path, required=True)
    args = parser.parse_args()
    backup = args.backup.resolve()
    if backup.parent != BACKUPS.resolve(): raise RuntimeError('Unexpected backup directory')
    receipt = json.loads((backup / 'backup-receipt.json').read_text(encoding='utf-8'))
    if receipt['status'] != 'VERIFIED_COMPLETE' or not receipt.get('every_member_size_sha256_crc_verified') or not receipt.get('source_start_end_content_equal'):
        raise RuntimeError('Complete verified backup is required')
    if sha(Path(receipt['archive'])) != receipt['archive_sha256']: raise RuntimeError('Recovery archive changed')
    stopped()
    latest = PERSONAL / 'latestSave.ini'
    rows = latest.read_text(encoding='utf-8-sig').splitlines()
    save = PERSONAL / 'Saves' / rows[1] / rows[0]
    if save.resolve() != Path(receipt['source']).resolve(): raise RuntimeError('Latest personal save changed')
    config = receipt['configuration_sha256']
    default = PERSONAL / 'mods/default.txt'
    enabled = save / 'mods.txt'
    if sha(default) != config['default.txt'] or sha(latest) != config['latestSave.ini'] or sha(enabled) != config['save/mods.txt']:
        raise RuntimeError('Enable lists or latest-save pointer changed after backup')
    prepared = json.loads((ROOT / 'publishing/Release_0.1.4/latest-frozen.json').read_text(encoding='utf-8'))
    release = json.loads(Path(prepared['release_json']).read_text(encoding='utf-8'))
    frozen = Path(release['content_path']) / 'mods/SuQingPortals'
    source = ROOT / 'mods/SuQingPortals'
    expected = tree(frozen)
    if tree(source) != expected or release['existing_item_id'] != '3834693880' or release['mod_versions'] != {'SuQingPortals': '0.1.4'}:
        raise RuntimeError('Frozen/source release identity mismatch')
    target = PERSONAL / 'mods/SuQingPortals'
    if target.exists() or target.resolve() != target.absolute(): raise RuntimeError('Personal destination already exists or is redirected')
    original = enabled.read_bytes()
    text = original.decode('utf-8-sig')
    old_order = re.findall(r'^\s*mod\s*=\s*([^,\r\n]+),', text, re.M)
    if 'SuQingPortals' in old_order: raise RuntimeError('Already enabled; inspect rather than append twice')
    block = re.search(r'(?ms)(^mods[ \t\r\n]*\{)(.*?)(^[ \t]*\})', text)
    if not block: raise RuntimeError('Unsupported native mod-list structure')
    newline = '\r\n' if '\r\n' in text else '\n'
    updated = text[:block.start(3)] + '    mod = SuQingPortals,' + newline + text[block.start(3):]
    after_bytes = updated.encode('utf-8')
    if original.startswith(b'\xef\xbb\xbf'): after_bytes = b'\xef\xbb\xbf' + after_bytes
    outputs = GAME / 'CodexAssets/SuQingPortals_20261106'
    state_path = outputs / 'personal-installation.json'
    state = dict(status='INCOMPLETE', version='0.1.4', backup=str(backup), save=str(save), target=str(target),
        original_order=old_order, source_runtime_sha256=expected, source_list_sha256=sha(enabled),
        global_default_sha256=sha(default), latest_save_sha256=sha(latest), game_started=False)
    def persist(): state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    persist()
    stopped()
    shutil.copytree(frozen, target)
    if tree(target) != expected: raise RuntimeError('Personal deployment readback differs')
    stopped()
    if enabled.read_bytes() != original: raise RuntimeError('Save list changed concurrently; installed mod not enabled')
    enabled.write_bytes(after_bytes)
    if enabled.read_bytes() != after_bytes: raise RuntimeError('Save enable-list write/readback failed')
    new_order = re.findall(r'^\s*mod\s*=\s*([^,\r\n]+),', enabled.read_text(encoding='utf-8-sig'), re.M)
    if new_order != old_order + ['SuQingPortals'] or sha(default) != config['default.txt'] or sha(latest) != config['latestSave.ini']:
        raise RuntimeError('Unrelated enable order or pointer changed')
    from prepare_isa_test_environment import native_reader
    native_folder = outputs / ('PersonalEnableReadback_' + datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S'))
    native_folder.mkdir()
    try:
        reader = native_reader(native_folder)
        reader(enabled, new_order, 'native-personal-save-mods.log')
    except Exception:
        stopped()
        if enabled.read_bytes() == after_bytes: enabled.write_bytes(original)
        state.update(status='ENABLEMENT_ROLLED_BACK_NATIVE_READ_FAILED', native_log=str(native_folder))
        persist()
        raise
    state.update(status='DEPLOYED_AND_ENABLED_OFFLINE', installed_at_bjt=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        installed_files=len(expected), new_order=new_order, new_list_sha256=sha(enabled), relative_order_preserved=True,
        global_default_unchanged=True, latest_save_unchanged=True, world_data_files_written=False,
        native_mod_list_readback='PASS', native_readback_directory=str(native_folder),
        note='Only the target save mods.txt was edited; actual personal-world loading remains user-operated')
    persist()
    print(json.dumps({k:state[k] for k in ('status','version','save','installed_files','global_default_unchanged','relative_order_preserved')}, ensure_ascii=False))


if __name__ == '__main__': main()
