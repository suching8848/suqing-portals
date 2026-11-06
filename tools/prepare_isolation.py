"""Prepare, never launch, a local-only single-player test profile."""
from pathlib import Path
import hashlib
import json
import shutil
from datetime import datetime, timezone, timedelta
from prepare_resource_view import main as prepare_resources

ROOT = Path(__file__).resolve().parents[1]
GAME = Path(r'D:\steam\steamapps\common\ProjectZomboid')
PERSONAL = Path(r'C:\Users\15792\Zomboid')
OUT = GAME / 'CodexAssets' / 'SuQingPortals_20261106'
PROFILE = OUT / 'IsolatedTest' / 'data'
WORKSHOP = Path(r'D:\steam\steamapps\workshop\content\108600')
RETAIN_PZO = True  # User approved keeping the matching installed PZO runtime.
SELECTED = [
    ('ZombieBuddy', WORKSHOP / '3619862853/mods/ZombieBuddy'),
    ('Viewpoint', WORKSHOP / '3809306528/mods/Viewpoint'),
    ('SuQingPortals', ROOT / 'mods/SuQingPortals'),
    ('B42ModTrans_CN', WORKSHOP / '3556540080/mods/B42ModTrans_CN_As1'),
    ('B42Trans_CN', WORKSHOP / '3556544454/mods/B42Trans_CN_As1'),
]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def protected():
    files = [PERSONAL / 'options.ini', PERSONAL / 'mods/default.txt',
             PERSONAL / 'latestSave.ini', GAME / 'ProjectZomboid64.json',
             PERSONAL / 'viewpoint.properties', PERSONAL / 'pzopt/options.ini']
    latest = PERSONAL / 'latestSave.ini'
    if latest.exists():
        rows = latest.read_text(encoding='utf-8-sig').splitlines()
        if len(rows) >= 2:
            save = PERSONAL / 'Saves' / rows[1] / rows[0]
            files += [save / 'mods.txt', save / 'map_sand.bin']
    return {str(p): sha(p) for p in files if p.is_file()}


def main():
    before = protected()
    OUT.mkdir(parents=True, exist_ok=True)
    prior_receipt = OUT / 'protected-before.json'
    if not prior_receipt.exists():
        prior_receipt.write_text(json.dumps(before, ensure_ascii=False, indent=2), encoding='utf-8')
    for sub in ('mods', 'Sandbox Presets', 'Saves', 'Logs'):
        (PROFILE / sub).mkdir(parents=True, exist_ok=True)
    iso = PROFILE.parent
    for sub in ('home', 'tmp', 'bootstrap', 'zombie-buddy-config'):
        (iso / sub).mkdir(exist_ok=True)
    inventory = []
    for mod_id, source in SELECTED:
        if not source.is_dir():
            raise RuntimeError('Missing source: ' + str(source))
        target = PROFILE / 'mods' / mod_id
        shutil.copytree(source, target, dirs_exist_ok=True)
        count = size = 0
        for f in source.rglob('*'):
            if f.is_file():
                deployed = target / f.relative_to(source)
                if sha(f) != sha(deployed):
                    raise RuntimeError('Copy differs: ' + str(f))
                count += 1
                size += f.stat().st_size
        inventory.append(dict(id=mod_id, source=str(source), destination=str(target), files=count, bytes=size))
    options = PROFILE / 'options.ini'
    if not options.exists():
        src_options = (PERSONAL / 'options.ini').read_text(encoding='utf-8-sig')
        # Same display/input choices in a separate file; force the already-used CN locale.
        lines = ['language=CN' if line.startswith('language=') else line for line in src_options.splitlines()]
        options.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    enabled = 'VERSION = 1,\n\nmods\n{\n' + ''.join('    mod = ' + x[0] + ',\n' for x in SELECTED) + '}\n\nmaps\n{\n}\n'
    # Current B42.21 resets the default active list once for release "42_00".
    # A new test cache must already have this marker before loading our list.
    marker = PROFILE / 'mods/reset-mods-42_00.txt'
    if not marker.exists():
        marker.write_text('If this file does not exist, default.txt will be reset to empty (no mods active).\n', encoding='utf-8')
    (PROFILE / 'mods/default.txt').write_text(enabled, encoding='utf-8')
    # Native user presets are ConfigFile text in cache/'Sandbox Presets', not Lua.
    preset = '''Version=6
Zombies=6
Distribution=1
DayLength=3
StartYear=1
StartMonth=7
StartDay=9
StartTime=2
WaterShut=8
ElecShut=8
SuQingPortals.ChargePerHour=0.5
'''
    (PROFILE / 'Sandbox Presets/SuQingPortals_Test.cfg').write_text(preset, encoding='utf-8')
    agent_src = WORKSHOP / '3619862853/mods/ZombieBuddy/libs/ZombieBuddy.jar'
    agent = iso / 'bootstrap/ZombieBuddy.jar'
    shutil.copy2(agent_src, agent)
    if sha(agent_src) != sha(agent):
        raise RuntimeError('Agent copy differs')
    if RETAIN_PZO:
        pzo_jar = GAME / 'pzopt/aot/pzopt.jar'
        if not pzo_jar.is_file():
            raise RuntimeError('The installed matching PZO runtime is missing')
        classpath = str(pzo_jar) + ';' + str(GAME / 'projectzomboid.jar')
        working_dir = GAME
        pzo_options = PERSONAL / 'pzopt/options.ini'
        if pzo_options.exists():
            for target in (PROFILE / 'pzopt/options.ini', iso / 'home/Zomboid/pzopt/options.ini'):
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    shutil.copy2(pzo_options, target)
        baseline = {str(p): sha(p) for p in (pzo_jar, GAME / 'projectzomboid.jar')}
    else:
        prepare_resources()
        classpath = str(GAME / 'projectzomboid.jar')
        working_dir = iso / 'engine'
        baseline = {str(GAME / 'projectzomboid.jar'): sha(GAME / 'projectzomboid.jar')}
    (iso / 'launch-baseline.json').write_text(json.dumps(baseline, indent=2), encoding='utf-8')
    # Separate agent/config/home/cache. Retained PZO Java matches its installed Lua.
    # PATH supplies the JRE DLL dependencies needed by Windows' instrument.dll.
    launch_ps = r'''$ErrorActionPreference = 'Stop'
$game = '__GAME__'
$iso = $PSScriptRoot
$data = Join-Path $iso 'data'
$engine = '__WORKING_DIR__'
$java = Join-Path $game 'jre64\bin\java.exe'
$baseline = Get-Content -LiteralPath (Join-Path $iso 'launch-baseline.json') -Raw | ConvertFrom-Json
foreach ($entry in $baseline.PSObject.Properties) { if ((Get-FileHash -LiteralPath $entry.Name -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value) { throw 'The installed game/PZO changed. Refresh this test entry before testing.' } }
foreach ($n in @('JAVA_TOOL_OPTIONS','_JAVA_OPTIONS','JDK_JAVA_OPTIONS','CLASSPATH','ZB_POLICY','ZB_CONFIG_DIR','ZB_VERBOSITY')) { Remove-Item -LiteralPath "Env:$n" -ErrorAction SilentlyContinue }
$env:PATH = $game + ';' + (Join-Path $game 'jre64\bin') + ';' + $env:PATH
$argsForGame = @(
    '--enable-native-access=ALL-UNNAMED',
    '--add-exports=java.base/jdk.internal.misc=ALL-UNNAMED',
    '-Xms2g','-Xmx8g','-XX:+UseG1GC','-XX:-CreateCoredumpOnCrash',
    ('-XX:ErrorFile=' + (Join-Path $iso 'tmp\hs_err_pid%p.log')),
    ('-Duser.home=' + (Join-Path $iso 'home')),
    ('-Djava.io.tmpdir=' + (Join-Path $iso 'tmp')),
    ('-Djava.library.path=' + $game + ';' + (Join-Path $game 'win64')),
    '-Dzomboid.steam=0',
    ('-javaagent:' + (Join-Path $iso 'bootstrap\ZombieBuddy.jar') + '=config_dir=' + (Join-Path $iso 'zombie-buddy-config')),
    '-cp','__CLASSPATH__',
    'zombie.gameStates.MainScreenState',
    ('-cachedir=' + $data),'-modfolders','mods','-nosteam','-debug'
)
Set-Location -LiteralPath $engine
& $java @argsForGame
if ($LASTEXITCODE -ne 0) { Write-Host ('Exit code: ' + $LASTEXITCODE); Read-Host 'Press Enter to close' }
'''.replace('__GAME__', str(GAME)).replace('__WORKING_DIR__', str(working_dir)).replace('__CLASSPATH__', classpath)
    (iso / 'Launch-Isolated.ps1').write_text(launch_ps, encoding='utf-8-sig')
    launch_cmd = '@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Launch-Isolated.ps1"\r\n'
    (iso / '启动传送门隔离测试.cmd').write_bytes(launch_cmd.encode('ascii'))
    # ASCII companion permits dependable links and shortcuts on every Windows code page.
    (iso / 'Start-Portal-Test.cmd').write_bytes(launch_cmd.encode('ascii'))
    after = protected()
    if before != after:
        raise RuntimeError('Protected files changed concurrently; inspect before any further operation')
    receipt = dict(time=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        source=str(ROOT), profile=str(PROFILE), mods=inventory,
        classpath=classpath, pzo_retained=RETAIN_PZO, agent=str(agent), agent_sha256=sha(agent),
        resource_working_directory=str(working_dir), first_release_reset_marker=str(marker),
        game_started=False, personal_files_unchanged=True, protected=after,
        note='Copied selected installed originals into local-only profile; no subscription or normal enabled-list changes.')
    (OUT / 'isolation-receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(profile=str(PROFILE), launcher=str(iso / 'Start-Portal-Test.cmd'), enabled=[x[0] for x in SELECTED], files=sum(x['files'] for x in inventory)), ensure_ascii=False))


if __name__ == '__main__':
    main()
