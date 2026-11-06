"""Append the installed ISA fork to the existing isolated profile; never starts a game.

Run only after the portal deployment and its foundation checks are complete.
TargetSquareOnLoad is optional in installed ISA 1.2.15 and is not copied.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys

from pure_lua_upgrade import foundation
from upgrade_isolated import protected

ROOT = Path(__file__).resolve().parents[1]
GAME = Path(r'D:\steam\steamapps\common\ProjectZomboid')
OUT = GAME / 'CodexAssets/SuQingPortals_20261106'
DATA = OUT / 'IsolatedTest/data'
SOURCE = Path(r'D:\steam\steamapps\workshop\content\108600\3781944805\mods\ImmersiveSolarArrays')
TARGET = DATA / 'mods/ISA'
DEFAULT = DATA / 'mods/default.txt'
ORIGINAL = ['ZombieBuddy', 'Viewpoint', 'SuQingPortals', 'B42ModTrans_CN', 'B42Trans_CN']
JAVAC = Path(r'E:\code\java-1.8.0-openjdk-1.8.0.392-1.b08.redhat.windows.x86_64\bin\javac.exe')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def tree(folder):
    result = {}
    for file in sorted(folder.rglob('*')):
        if file.is_symlink() or (hasattr(file, 'is_junction') and file.is_junction()):
            raise RuntimeError('Refusing linked source or target: ' + str(file))
        if file.is_file():
            result[file.relative_to(folder).as_posix()] = {'bytes': file.stat().st_size, 'sha256': sha(file)}
    return result


def stopped():
    script = r"$p=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^ProjectZomboid' -or ($_.Name -match '^javaw?\.exe$' -and $_.CommandLine -match 'zombie\.gameStates\.MainScreenState|-cachedir=') }); $p.Count"
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', script], capture_output=True, text=True, check=True)
    if result.stdout.strip() != '0':
        raise RuntimeError('A game process is running; normal exit is required before modifying isolated mods')


def native_reader(folder):
    source = folder / 'NativeModsReadback.java'
    source.write_text('''import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
public final class NativeModsReadback {
  public static void main(String[] a) throws Exception {
    Class<?> fs = Class.forName("zombie.ZomboidFileSystem");
    fs.getMethod("setCacheDir", String.class).invoke(fs.getField("instance").get(null), a[1]);
    Class<?> active = Class.forName("zombie.modding.ActiveMods");
    Object mods = active.getMethod("getById", String.class).invoke(null, "portal-isa-readback");
    Class<?> file = Class.forName("zombie.modding.ActiveModsFile");
    if (!Boolean.TRUE.equals(file.getMethod("read", String.class, active).invoke(file.newInstance(), a[0], mods)))
      throw new AssertionError("Native mod-list read failed");
    Object actual = active.getMethod("getMods").invoke(mods);
    List<String> expected = Arrays.asList(Arrays.copyOfRange(a, 2, a.length));
    if (!expected.equals(actual)) throw new AssertionError("Order mismatch: " + actual);
    System.out.println("ISA_NATIVE_MOD_ORDER PASS " + actual);
  }
}
''', encoding='utf-8')
    command = [str(JAVAC), '-J-Xms16m', '-J-Xmx64m', '-encoding', 'UTF-8', '-d', str(folder), str(source)]
    result = subprocess.run(command, cwd=GAME, capture_output=True, encoding='utf-8', errors='replace')
    (folder / 'native-reader-compile.log').write_text(result.stdout + result.stderr, encoding='utf-8')
    if result.returncode:
        raise RuntimeError('Native mod-order helper did not compile')
    for name in ('native-home', 'native-cache', 'native-tmp'):
        (folder / name).mkdir()
    def read_list(path, ids, name):
        command = [str(GAME / 'jre64/bin/java.exe'), '-Xint', '-Xms16m', '-Xmx64m', '-XX:+UseSerialGC',
            '-Duser.home=' + str(folder / 'native-home'), '-Djava.io.tmpdir=' + str(folder / 'native-tmp'),
            '-cp', str(folder) + ';' + str(GAME / 'projectzomboid.jar'), 'NativeModsReadback',
            str(path), str(folder / 'native-cache')] + ids
        result = subprocess.run(command, cwd=GAME, capture_output=True, encoding='utf-8', errors='replace')
        (folder / name).write_text(result.stdout + result.stderr, encoding='utf-8')
        if result.returncode:
            raise RuntimeError('Native mod-order readback failed; see ' + name)
    return read_list


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true', help='Read-only plan; do not copy or compile')
    args = parser.parse_args()
    stopped()
    info = (SOURCE / '42/mod.info').read_text(encoding='utf-8-sig')
    if not re.search(r'^id=ISA\s*$', info, re.M) or not re.search(r'^modversion=1\.2\.15\s*$', info, re.M):
        raise RuntimeError('Installed ISA identity/version changed; review before copying')
    if re.search(r'^require=', info, re.M):
        raise RuntimeError('ISA now declares dependencies; review before changing test environment')
    if not (SOURCE / 'common').is_dir():
        raise RuntimeError('The complete installed ISA common/42 pair is required')
    if TARGET.resolve() != TARGET.absolute() or TARGET.parent.resolve() != TARGET.parent.absolute():
        raise RuntimeError('Isolated mod destination is redirected')
    before_bytes = DEFAULT.read_bytes()
    before_text = before_bytes.decode('utf-8-sig')
    ids = re.findall(r'^\s*mod\s*=\s*([^,\r\n]+),', before_text, re.M)
    if [value for value in ids if value in ORIGINAL] != ORIGINAL or len(ids) != len(set(ids)) or 'ISA-Fix' in ids:
        raise RuntimeError('Unexpected isolated base order, duplicates or conflicting ISA-Fix')
    if not (DATA / 'mods/reset-mods-42_00.txt').is_file():
        raise RuntimeError('Existing isolated first-run reset marker is missing; inspect rather than rewriting it')
    expected = ids if 'ISA' in ids else ids + ['ISA']
    if args.check_only:
        print(json.dumps(dict(status='PLAN_ONLY', source=str(SOURCE), target=str(TARGET), before=ids,
            after=expected, required_dependencies=[], optional_dependency_not_added='TargetSquareOnLoad', writes=False), ensure_ascii=False))
        return
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
    folder = OUT / ('ISA_TestEnvironment_' + stamp)
    folder.mkdir()
    recovery = folder / 'default.before.bin'
    recovery.write_bytes(before_bytes)
    reader = native_reader(folder)
    reader(DEFAULT, ids, 'native-default-before.log')
    source_before = tree(SOURCE)
    if not source_before:
        raise RuntimeError('ISA source is empty')
    base = foundation()
    formal = protected()
    rows = (DATA / 'latestSave.ini').read_text(encoding='utf-8-sig').splitlines()
    old_save = DATA / 'Saves' / rows[1] / rows[0]
    old_save.resolve().relative_to((DATA / 'Saves').resolve())
    if not old_save.is_dir():
        raise RuntimeError('Current isolated save is missing; inspect latestSave.ini before proceeding')
    old_save_before = tree(old_save)
    receipt = dict(status='INCOMPLETE', time=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        source=str(SOURCE), destination=str(TARGET), mod_id='ISA', isa_version='1.2.15',
        original_enabled=ids, expected_enabled=expected, original_default=str(recovery),
        original_default_sha256=sha(recovery), source_manifest=source_before,
        target_created_by_this_operation=not TARGET.exists(), dependencies_added=[],
        target_square_optional=True, target_square_not_added=True, old_save=str(old_save),
        old_save_files=len(old_save_before), game_started=False, formal_environment_written=False,
        old_save_written=False, latest_save_written=False, options_written=False)
    path = folder / 'environment-receipt.json'
    def write_receipt():
        path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write_receipt()
    written_bytes = None
    try:
        stopped()
        if TARGET.exists():
            if tree(TARGET) != source_before:
                raise RuntimeError('Existing isolated ISA differs; refusing to overwrite it')
        else:
            shutil.copytree(SOURCE, TARGET)
        if tree(TARGET) != source_before or tree(SOURCE) != source_before:
            raise RuntimeError('ISA copy readback failed or Steam changed source during copying')
        if DEFAULT.read_bytes() != before_bytes:
            raise RuntimeError('Isolated mod list changed concurrently')
        stopped()
        if 'ISA' not in ids:
            block = re.search(r'(?ms)(^mods[ \t\r\n]*\{)(.*?)(^[ \t]*\})', before_text)
            if not block:
                raise RuntimeError('Cannot find the existing mods block safely')
            newline = '\r\n' if '\r\n' in before_text else '\n'
            updated = before_text[:block.start(3)] + '    mod = ISA,' + newline + before_text[block.start(3):]
            data = updated.encode('utf-8')
            if before_bytes.startswith(b'\xef\xbb\xbf'):
                data = b'\xef\xbb\xbf' + data
            DEFAULT.write_bytes(data)
            written_bytes = data
        reader(DEFAULT, expected, 'native-default-after.log')
        after = foundation()
        allowed = str(DEFAULT)
        if {k: v for k, v in base.items() if k != allowed} != {k: v for k, v in after.items() if k != allowed}:
            raise RuntimeError('Retained launcher/config/base mods changed')
        if protected() != formal or tree(old_save) != old_save_before:
            raise RuntimeError('Protected personal files or original isolated save changed')
        if tree(TARGET) != source_before:
            raise RuntimeError('Isolated ISA changed after enable/readback')
        receipt.update(status='READY_FOR_USER_TEST', default_after_sha256=sha(DEFAULT),
            destination_manifest=source_before, every_member_sha256_verified=True,
            native_enabled_list_readback='PASS', retained_base_relative_order_unchanged=True,
            retained_foundation_except_default_unchanged=True, formal_protected_unchanged=True,
            old_save_sha256_unchanged=True, mods_from=str(DEFAULT))
        write_receipt()
        (OUT / 'current-isa-test-environment.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(dict(status=receipt['status'], copied_files=len(source_before), enabled=expected,
            mods_from=str(DEFAULT), receipt=str(path), old_save_unchanged=True, game_started=False), ensure_ascii=False))
    except Exception as error:
        receipt['error'] = str(error)
        # Exact list restoration is safe; newly copied ISA files are retained, disabled.
        observed_default = DEFAULT.read_bytes()
        if written_bytes is not None and observed_default == written_bytes and observed_default != before_bytes:
            stopped()
            DEFAULT.write_bytes(before_bytes)
            receipt['original_default_restored_exactly'] = DEFAULT.read_bytes() == before_bytes
        elif observed_default != before_bytes:
            receipt['default_restore_skipped'] = 'Concurrent change preserved; exact original bytes remain in recovery file'
        write_receipt()
        raise


if __name__ == '__main__':
    main()
