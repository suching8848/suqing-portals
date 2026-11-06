"""Create one verified complete personal-save backup before authorized release/deployment."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import zipfile
import argparse
from concurrent.futures import ThreadPoolExecutor
from collections import deque

PERSONAL = Path(r'C:\Users\15792\Zomboid')
BACKUPS = Path(r'D:\GameBackups\ProjectZomboid')
EXPECTED = PERSONAL / 'Saves/Sandbox/2026-10-09_18-19-22'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def emit(**value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def stopped():
    command = r"$p=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^ProjectZomboid' -or ($_.Name -match '^javaw?\.exe$' -and $_.CommandLine -match 'zombie\.gameStates\.MainScreenState|zombie\.network\.GameServer') }); $p | Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress; if($p.Count -gt 0){exit 2}"
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command], capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError('A game process is running; normal exit is required: ' + result.stdout)
    return {'running_game_processes': [], 'query_returncode': result.returncode}


def enumerate_files(folder):
    if folder.resolve() != folder.absolute() or folder.is_symlink() or (hasattr(folder, 'is_junction') and folder.is_junction()):
        raise RuntimeError('Refusing a redirected source: ' + str(folder))
    result = {}
    for path in sorted(folder.rglob('*')):
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            raise RuntimeError('Refusing linked save/mod contents: ' + str(path))
        if path.is_file():
            stat = path.stat()
            result[path.relative_to(folder).as_posix()] = (path, stat.st_size, stat.st_mtime_ns)
    return result


def enabled(path):
    text = path.read_text(encoding='utf-8-sig')
    return re.findall(r'^\s*mod\s*=\s*([^,\r\n]+),', text, re.M)


def bounded_map(pool, function, records, buffer=64):
    iterator, pending = iter(records), deque()
    for _ in range(buffer):
        try:
            pending.append(pool.submit(function, next(iterator)))
        except StopIteration:
            break
    while pending:
        yield pending.popleft().result()
        try:
            pending.append(pool.submit(function, next(iterator)))
        except StopIteration:
            pass


def payload(record):
    name, path = record
    before = path.stat()
    with path.open('rb') as stream:
        data = stream.read()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or len(data) != before.st_size:
        raise RuntimeError('Source changed while reading: ' + str(path))
    return name, path, data, hashlib.sha256(data).hexdigest(), after.st_mtime_ns


def verified_source(record):
    name, path, entry = record
    if path.stat().st_size != entry['bytes'] or sha(path) != entry['sha256']:
        raise RuntimeError('Source contents changed during backup: ' + str(path))
    return name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume-folder', type=Path)
    parser.add_argument('--workers', type=int, default=16)
    args = parser.parse_args()
    if not 1 <= args.workers <= 16:
        raise RuntimeError('Use between 1 and 16 bounded I/O workers')
    process_before = stopped()
    latest = PERSONAL / 'latestSave.ini'
    latest_bytes = latest.read_bytes()
    rows = latest_bytes.decode('utf-8-sig').splitlines()
    source = PERSONAL / 'Saves' / rows[1] / rows[0]
    if source.resolve() != EXPECTED.resolve() or not source.is_dir():
        raise RuntimeError('Latest personal save differs from the authorized target: ' + str(source))
    log = PERSONAL / 'console.txt'
    log_stat = (log.stat().st_size, log.stat().st_mtime_ns)
    if 'GameThread exited.' not in log.read_text(encoding='utf-8', errors='replace')[-20000:]:
        raise RuntimeError('Personal console does not record a normal exit')
    save = enumerate_files(source)
    if not save or 'mods.txt' not in save or 'map_sand.bin' not in save:
        raise RuntimeError('Target save is empty or lacks required files')
    save_bytes = sum(record[1] for record in save.values())
    if shutil.disk_usage(BACKUPS).free < save_bytes + 256 * 1024 * 1024:
        raise RuntimeError('Insufficient backup-disk free space for an uncompressed-size archive')
    mod = PERSONAL / 'mods/SuQingPortals'
    local_mod = enumerate_files(mod) if mod.exists() else {}
    inputs = [('save/' + name, path) for name, (path, _, _) in save.items()]
    inputs += [('configuration/default.txt', PERSONAL / 'mods/default.txt'), ('configuration/latestSave.ini', latest)]
    inputs += [('local-mod/SuQingPortals/' + name, path) for name, (path, _, _) in local_mod.items()]
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
    folder = args.resume_folder if args.resume_folder else BACKUPS / ('SuQingPortals_Release_' + stamp)
    if folder.resolve().parent != BACKUPS.resolve():
        raise RuntimeError('Backup target is outside the intended backup root')
    if args.resume_folder:
        old_receipt = json.loads((folder / 'backup-receipt.json').read_text(encoding='utf-8'))
        if old_receipt['status'] != 'INCOMPLETE_NOT_RESTORABLE' or old_receipt['source'] != str(source) or not (folder / 'personal-save-and-enablement.INCOMPLETE.zip').is_file():
            raise RuntimeError('Resume requires this exact known incomplete backup and preserved partial archive')
    else:
        folder.mkdir()
    archive = folder / 'personal-save-and-enablement.zip'
    receipt_path = folder / 'backup-receipt.json'
    receipt = dict(status='INCOMPLETE_NOT_RESTORABLE', source=str(source), created_at_bjt=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        archive=str(archive), full_save=True, save_files=len(save), save_bytes=save_bytes,
        local_portal_mod_existed=mod.exists(), local_portal_mod_files=len(local_mod),
        source_files_modified=False, process_before=process_before, hidden_files_included=True,
        io_workers=args.workers, maximum_prefetched_members=64,
        superseded_incomplete_archive=str(folder / 'personal-save-and-enablement.INCOMPLETE.zip') if args.resume_folder else None)
    def record():
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    record()
    emit(phase='COPYING_ARCHIVE', folder=str(folder), save_files=len(save), save_bytes=save_bytes, total_members=len(inputs))
    manifest = {}
    try:
        stopped()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as z:
                for index, (name, path, data, digest, modified) in enumerate(bounded_map(pool, payload, inputs), 1):
                    if name.startswith('save/'):
                        initial = save[name[len('save/'):]]
                        if (len(data), modified) != (initial[1], initial[2]):
                            raise RuntimeError('Source changed after initial enumeration: ' + str(path))
                    z.writestr(name, data)
                    manifest[name] = dict(bytes=len(data), sha256=digest, source=str(path), mtime_ns=modified)
                    if index % 5000 == 0:
                        emit(phase='COPYING_ARCHIVE', completed=index, total=len(inputs))
                z.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8'))
        emit(phase='VERIFYING_ARCHIVE_MEMBERS', members=len(manifest), archive_bytes=archive.stat().st_size)
        with zipfile.ZipFile(archive) as z:
            if set(z.namelist()) != set(manifest) | {'manifest.json'}:
                raise RuntimeError('Archive member set differs')
            if json.loads(z.read('manifest.json')) != manifest:
                raise RuntimeError('Archived manifest readback differs')
            for index, (name, entry) in enumerate(manifest.items(), 1):
                digest, size = hashlib.sha256(), 0
                with z.open(name) as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(block); size += len(block)
                if size != entry['bytes'] or digest.hexdigest() != entry['sha256']:
                    raise RuntimeError('Archived member readback differs: ' + name)
                if index % 5000 == 0:
                    emit(phase='VERIFYING_ARCHIVE_MEMBERS', completed=index, total=len(manifest))
            # Reading every member to EOF above also checks each CRC through ZipExtFile.
        emit(phase='VERIFYING_SOURCE_UNCHANGED', files=len(inputs))
        current_save = enumerate_files(source)
        if set(current_save) != set(save):
            raise RuntimeError('Save membership changed during backup')
        current_mod = enumerate_files(mod) if mod.exists() else {}
        if set(current_mod) != set(local_mod):
            raise RuntimeError('Local mod membership changed during backup')
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            records = ((name, path, manifest[name]) for name, path in inputs)
            for index, _ in enumerate(bounded_map(pool, verified_source, records), 1):
                if index % 5000 == 0:
                    emit(phase='VERIFYING_SOURCE_UNCHANGED', completed=index, total=len(inputs))
        if latest.read_bytes() != latest_bytes or (log.stat().st_size, log.stat().st_mtime_ns) != log_stat:
            raise RuntimeError('Latest-save pointer or console changed during backup')
        process_after = stopped()
        global_mods, saved_mods = enabled(PERSONAL / 'mods/default.txt'), enabled(source / 'mods.txt')
        receipt.update(status='VERIFIED_COMPLETE', completed_at_bjt=datetime.now(timezone(timedelta(hours=8))).isoformat(),
            archive_bytes=archive.stat().st_size, archive_sha256=sha(archive), members=len(manifest),
            every_member_size_sha256_crc_verified=True, source_start_end_content_equal=True, process_after=process_after,
            configuration_sha256={'default.txt':sha(PERSONAL / 'mods/default.txt'),'latestSave.ini':sha(latest),'save/mods.txt':sha(source / 'mods.txt')},
            global_mod_order=global_mods, saved_mod_order=saved_mods,
            only_global=[v for v in global_mods if v not in saved_mods], only_saved=[v for v in saved_mods if v not in global_mods],
            manifest=str(folder / 'manifest.json'))
        (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        record()
        (folder / '恢复说明.md').write_text('# 传送门发布前完整备份\n\n'+
            f'状态：完整，全部成员大小／SHA-256／CRC读回通过，首尾源内容一致。\n\n原存档：`{source}`。\n\n归档：`{archive}`。\n\nSHA-256：`{receipt["archive_sha256"]}`。\n\n'+
            '恢复世界会回退到备份时的进度。先正常退出游戏，保留当前进度，再在独立位置解压并核对manifest，随后仅将save/内容恢复到上述原存档。configuration/default.txt与latestSave.ini仅供精确配置恢复，不能无条件整份覆盖之后的手动设置。local-mod/仅在本次原本存在时收录；本次不存在则收据明确记录absent。不要运行旧整档回滚脚本。\n',encoding='utf-8')
        emit(status=receipt['status'], folder=str(folder), save_files=len(save), save_bytes=save_bytes,
            archive_sha256=receipt['archive_sha256'], global_count=len(global_mods), saved_count=len(saved_mods),
            only_global=receipt['only_global'], only_saved=receipt['only_saved'], local_mod_existed=receipt['local_portal_mod_existed'])
    except Exception as error:
        receipt['error'] = str(error); record(); raise


if __name__ == '__main__':
    main()
