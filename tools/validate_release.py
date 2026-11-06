"""Offline checks only. Never starts the game's main class or a world."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
GAME = Path(r'D:\steam\steamapps\common\ProjectZomboid')
JAVA = GAME / 'jre64/bin/java.exe'
JAVAC = Path(r'E:\code\java-1.8.0-openjdk-1.8.0.392-1.b08.redhat.windows.x86_64\bin\javac.exe')
MOD = ROOT / 'mods/SuQingPortals/42'
RESULTS = ROOT / 'tests/results'
RESULTS.mkdir(parents=True, exist_ok=True)
HOME = RESULTS / 'native-home'
HOME.mkdir(exist_ok=True)
report = {'scope': 'Standalone Kahlua, script/resource parsers and copy/archive checks. No game main/world/UI executed.', 'checks': {}}


def run(name, args, cwd=ROOT):
    args = list(args)
    if Path(args[0]) == JAVA:
        args[1:1] = ['-Dstdout.encoding=UTF-8', '-Dstderr.encoding=UTF-8']
    if Path(args[0]) == JAVAC:
        args[1:1] = ['-J-Xms16m', '-J-Xmx64m', '-J-XX:+UseSerialGC']
    result = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, encoding='utf-8', errors='replace')
    output = result.stdout + result.stderr
    (RESULTS / (name + '.log')).write_text(output, encoding='utf-8')
    report['checks'][name] = dict(exit_code=result.returncode, log=str(RESULTS / (name + '.log')))
    if result.returncode:
        print(output[-5000:])
        raise RuntimeError(name + ' failed')
    print(name + ': PASS')


def interpreter(*files, compile_only=False):
    return [JAVA, '-Xint', '-Xms16m', '-Xmx128m', '-XX:+UseSerialGC', '-XX:ReservedCodeCacheSize=32m', '-Duser.home=' + str(HOME), '-cp', str(ROOT / 'tests') + ';' + str(GAME / 'projectzomboid.jar'),
            'PortalKahluaAudit'] + (['--compile'] if compile_only else []) + list(files)


def translations():
    languages = {}
    game_keys = {}
    for lang in ('CN', 'EN'):
        values = {}
        usable = set()
        for file in (MOD / 'media/lua/shared/Translate' / lang).glob('*.json'):
            data = json.loads(file.read_text(encoding='utf-8-sig'))
            for key, value in data.items():
                if not isinstance(value, str):
                    raise RuntimeError('Non-text localization: ' + str(file) + ':' + key)
                values[file.stem + ':' + key] = value
                if key.startswith(('IGUI_', 'Tooltip_', 'Sandbox_', 'Recipe_', 'UI_')):
                    usable.add(key)
        for file in (MOD / 'media/lua/shared/Translate' / lang).glob('*.txt'):
            for match in re.finditer(r'^\s*([A-Za-z0-9_]+)\s*=\s*"((?:\\.|[^"\\])*)"\s*,?\s*$', file.read_text(encoding='utf-8-sig'), re.M):
                scoped = file.stem.rsplit('_', 1)[0] + ':' + match[1]
                if scoped in values:
                    raise RuntimeError('Duplicate localization key: ' + lang + ':' + match[1])
                values[scoped] = match[2]
                usable.add(match[1])
        languages[lang] = values
        game_keys[lang] = usable
    if not languages['EN'] or set(languages['EN']) != set(languages['CN']):
        raise RuntimeError('CN/EN keys differ: ' + repr(set(languages['EN']) ^ set(languages['CN'])))
    for key in languages['EN']:
        placeholders = lambda s: sorted(re.findall(r'%[1-9]', s.replace('%%', '')))
        if any(re.search(r'%[1-9]\$[sdif]', languages[lang][key]) for lang in ('CN', 'EN')):
            raise RuntimeError('Preformatted Java token in JSON source (native loader formats it again): ' + key)
        if placeholders(languages['CN'][key]) != placeholders(languages['EN'][key]):
            raise RuntimeError('Placeholder mismatch: ' + key)
    literal = set()
    source = ''
    for file in (MOD / 'media/lua').rglob('*.lua'):
        content = file.read_text(encoding='utf-8-sig')
        source += content + '\n'
        literal.update(re.findall(r'getText\(\s*"((?:IGUI|Tooltip|Sandbox|Recipe|UI)_[A-Za-z0-9_]+)"\s*[,)]', content))
        if file.name == 'UI.lua':
            literal.update('IGUI_SQP_' + x for x in re.findall(r'\btext\(\s*"([A-Za-z0-9_]+)"\s*[,)]', content))
            if 'text("PowerSource_"..source)' in content:
                literal.update('IGUI_SQP_PowerSource_' + suffix
                               for suffix in ('grid', 'generator', 'grid_generator', 'grid_area', 'area'))
    missing = literal - game_keys['EN']
    if missing:
        raise RuntimeError('Untranslated UI literals: ' + repr(sorted(missing)))
    for file in (MOD / 'media/scripts').glob('*.txt'):
        for key in re.findall(r'\b(?:DisplayName|BuildDescription|Tooltip|Tags)\s*=\s*((?:IGUI|Tooltip)_[A-Za-z0-9_]+)', file.read_text(encoding='utf-8')):
            if key not in game_keys['EN']:
                raise RuntimeError('Untranslated script reference: ' + key)
    report['checks']['localization'] = dict(keys_per_language=len(languages['EN']), literal_references=len(literal), result='PASS')
    print('localization: PASS keys=' + str(len(languages['EN'])))


def pure_lua_runtime():
    forbidden_files = [p.relative_to(MOD).as_posix() for p in MOD.rglob('*')
                       if p.is_file() and p.suffix.lower() in ('.jar', '.class', '.dll', '.so', '.dylib')]
    if forbidden_files:
        raise RuntimeError('Non-Lua runtime binaries: ' + repr(forbidden_files))
    info = (MOD / 'mod.info').read_text(encoding='utf-8')
    if re.search(r'^(?:javaJarFile|javaPkgName|javaPreload)\s*=', info, re.M):
        raise RuntimeError('Portal Java loader declarations remain')
    if re.search(r'^require\s*=.*ZombieBuddy', info, re.M):
        raise RuntimeError('Portal still requires the Java framework')
    for file in (MOD / 'media/lua').rglob('*.lua'):
        content = file.read_text(encoding='utf-8-sig')
        if re.search(r'SuQingPortalCodec|PortalBatteryCodec|luajava|java\.lang\.reflect|Class\.forName|ZombieBuddy\.(?:reflect|invoke)|PZOpt\.(?:reflect|invoke)', content, re.I):
            raise RuntimeError('Java bridge/reflection reference in product Lua: ' + str(file))
    report['checks']['pure_lua_runtime'] = dict(result='PASS', portal_java_binaries=0,
        portal_java_loader_declarations=0, requires_zombiebuddy=False,
        storage='Original items in native ItemContainer; Lua-only four-slot interface and guards')
    print('pure_lua_runtime: PASS no portal JAR/class/native binary or bridge')


def main():
    global report
    if '--text-only' in sys.argv:
        report = json.loads((RESULTS / 'offline-validation.json').read_text(encoding='utf-8'))
        current = {str(p.relative_to(MOD)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in MOD.rglob('*') if p.is_file()}
        changed = [p for p in set(current) | set(report['runtime_sha256'])
                   if current.get(p) != report['runtime_sha256'].get(p)]
        if not all(p.startswith('media/lua/shared/Translate/') and p.endswith('.json') for p in changed):
            raise RuntimeError('Text-only refresh cannot cover changed logic/resources: ' + repr(changed))
        translations()
        run('native_building_localization', [JAVA, '-Xint', '-Xms16m', '-Xmx128m', '-XX:+UseSerialGC',
            '-XX:ReservedCodeCacheSize=32m', '-Duser.home=' + str(HOME), '-cp',
            str(ROOT / 'tools') + ';' + str(GAME / 'projectzomboid.jar'), 'PortalBuildingAudit', MOD], cwd=GAME)
        report['runtime_sha256'] = current
        report['text_only_refresh'] = changed
        (RESULTS / 'offline-validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print('TEXT-ONLY NATIVE CHECKS PASS; other validated runtime files unchanged')
        return
    pure_lua_runtime()
    run('compile_helper', [JAVAC, '-encoding', 'UTF-8', ROOT / 'tests/PortalKahluaAudit.java'])
    lua = sorted((MOD / 'media/lua').rglob('*.lua'))
    translated = sorted((MOD / 'media/lua/shared/Translate').rglob('*.txt'))
    run('kahlua_compile', interpreter(*(lua + translated), compile_only=True), cwd=GAME)
    translations()
    shared_slots = MOD / 'media/lua/shared/SuQingPortals/BatterySlots.lua'
    shared_storage = [shared_slots] if shared_slots.exists() else []
    slots_bootstrap = [ROOT / 'tests/slots_bootstrap.lua'] if (ROOT / 'tests/slots_bootstrap.lua').exists() else []
    run('core_world', interpreter(ROOT / 'tests/core_world_bootstrap.lua', *slots_bootstrap,
        MOD / 'media/lua/shared/SuQingPortals/Core.lua',
        *shared_storage,
        MOD / 'media/lua/server/SuQingPortals/World.lua', ROOT / 'tests/core_world_spec.lua'), cwd=GAME)
    if (ROOT / 'tests/client_bootstrap.lua').exists():
        run('client_transfer', interpreter(ROOT / 'tests/core_world_bootstrap.lua', *slots_bootstrap,
            MOD / 'media/lua/shared/SuQingPortals/Core.lua',
            *shared_storage,
            MOD / 'media/lua/server/SuQingPortals/World.lua',
            ROOT / 'tests/client_bootstrap.lua',
            MOD / 'media/lua/client/SuQingPortals/Build.lua',
            MOD / 'media/lua/client/SuQingPortals/Transfer.lua',
            MOD / 'media/lua/client/SuQingPortals/Actions.lua',
            MOD / 'media/lua/client/SuQingPortals/UI.lua',
            MOD / 'media/lua/client/SuQingPortals/VisualData.lua',
            MOD / 'media/lua/client/SuQingPortals/Viewpoint.lua',
            MOD / 'media/lua/client/SuQingPortals/Client.lua', ROOT / 'tests/client_spec.lua'), cwd=GAME)
    if (ROOT / 'tests/inventory_guard_spec.lua').exists():
        run('inventory_native_source', [sys.executable, ROOT / 'tools/prepare_inventory_guard_fixture.py'])
        run('inventory_guard', interpreter(ROOT / 'tests/core_world_bootstrap.lua',
            MOD / 'media/lua/shared/SuQingPortals/Core.lua', *shared_storage,
            MOD / 'media/lua/server/SuQingPortals/World.lua',
            ROOT / 'tests/inventory_guard_bootstrap.lua', ROOT / 'tests/inventory_guard_native.lua',
            MOD / 'media/lua/client/SuQingPortals/InventoryGuard.lua', ROOT / 'tests/inventory_guard_spec.lua'), cwd=GAME)
    run('model_resources', [sys.executable, ROOT / 'tools/validate_portal_assets.py'])
    fixture_classes = RESULTS / 'native-internal-storage-classes'
    fixture_classes.mkdir(exist_ok=True)
    run('internal_storage_audit_compile', [JAVAC, '-encoding', 'UTF-8', '-d', fixture_classes,
        ROOT / 'tests/NativeInternalStorageAudit.java'])
    java_flags = [JAVA, '-Xint', '-Xms16m', '-Xmx128m', '-XX:+UseSerialGC', '-XX:ReservedCodeCacheSize=32m',
        '--enable-native-access=ALL-UNNAMED', '-Duser.home=' + str(HOME)]
    picker_classes = RESULTS / 'picker-interop-classes'
    picker_classes.mkdir(exist_ok=True)
    run('picker_interop_compile', [JAVAC, '-encoding', 'UTF-8', '-d', picker_classes,
        ROOT / 'tests/PortalPickerInteropAudit.java'])
    picker_stock_cp = ';'.join(map(str, [picker_classes, GAME / 'projectzomboid.jar']))
    picker_pzo_cp = ';'.join(map(str, [picker_classes, GAME / 'pzopt/aot/pzopt.jar', GAME / 'projectzomboid.jar']))
    run('native_picker_interop_stock', java_flags + ['-cp', picker_stock_cp, 'PortalPickerInteropAudit', MOD, HOME / 'picker-stock'], cwd=GAME)
    run('native_picker_interop_pzo', java_flags + ['-cp', picker_pzo_cp, 'PortalPickerInteropAudit', MOD, HOME / 'picker-pzo'], cwd=GAME)
    translation_classes = RESULTS / 'translation-interop-classes'
    translation_classes.mkdir(exist_ok=True)
    run('translation_interop_compile', [JAVAC, '-encoding', 'UTF-8', '-d', translation_classes,
        ROOT / 'tests/PortalTranslationInteropAudit.java'])
    translation_stock_cp = ';'.join(map(str, [translation_classes, GAME / 'projectzomboid.jar']))
    translation_pzo_cp = ';'.join(map(str, [translation_classes, GAME / 'pzopt/aot/pzopt.jar', GAME / 'projectzomboid.jar']))
    run('native_translation_interop_stock', java_flags + ['-Djava.awt.headless=true', '-cp', translation_stock_cp,
        'PortalTranslationInteropAudit', MOD, HOME / 'translation-stock'], cwd=GAME)
    run('native_translation_interop_pzo', java_flags + ['-Djava.awt.headless=true', '-cp', translation_pzo_cp,
        'PortalTranslationInteropAudit', MOD, HOME / 'translation-pzo'], cwd=GAME)
    stock_cp = ';'.join(map(str, [fixture_classes, GAME / 'projectzomboid.jar']))
    actual_cp = ';'.join(map(str, [fixture_classes, GAME / 'pzopt/aot/pzopt.jar', GAME / 'projectzomboid.jar']))
    run('native_internal_storage_stock', java_flags + ['-cp', stock_cp, 'NativeInternalStorageAudit', HOME / 'internal-stock'], cwd=GAME)
    run('native_internal_storage_pzo', java_flags + ['-cp', actual_cp, 'NativeInternalStorageAudit', HOME / 'internal-pzo'], cwd=GAME)
    run('model_native_compile', [JAVAC, '-encoding', 'UTF-8', ROOT / 'tests/PortalAssetsNativeReadback.java'])
    vp_jar = GAME / 'CodexAssets/SuQingPortals_20261106/IsolatedTest/data/mods/Viewpoint/42/media/java/client/Viewpoint.jar'
    run('model_native_readback', java_flags + ['-cp', ';'.join(map(str, [ROOT / 'tests', GAME / 'projectzomboid.jar', vp_jar])),
        'PortalAssetsNativeReadback', MOD / 'media'], cwd=GAME)
    run('building_helper_compile', [JAVAC, '-encoding', 'UTF-8', ROOT / 'tools/PortalBuildingAudit.java'])
    run('native_building_localization', [JAVA, '-Xint', '-Xms16m', '-Xmx128m', '-XX:+UseSerialGC', '-XX:ReservedCodeCacheSize=32m', '-Duser.home=' + str(HOME), '-cp',
        str(ROOT / 'tools') + ';' + str(GAME / 'projectzomboid.jar'), 'PortalBuildingAudit', MOD], cwd=GAME)
    preset = GAME / 'CodexAssets/SuQingPortals_20261106/IsolatedTest/data/Sandbox Presets/SuQingPortals_Test.cfg'
    if preset.exists():
        run('isolation_helper_compile', [JAVAC, '-encoding', 'UTF-8', ROOT / 'tools/PortalIsolationAudit.java'])
        run('isolated_native_preset', [JAVA, '-Xint', '-Xms16m', '-Xmx128m', '-XX:+UseSerialGC', '-XX:ReservedCodeCacheSize=32m', '-Duser.home=' + str(HOME), '-cp',
            str(ROOT / 'tools') + ';' + str(GAME / 'projectzomboid.jar'), 'PortalIsolationAudit', preset], cwd=GAME)
    core_version = re.search(r'Core.VERSION\s*=\s*"([^"]+)"', (MOD / 'media/lua/shared/SuQingPortals/Core.lua').read_text(encoding='utf-8'))[1]
    info = (MOD / 'mod.info').read_text(encoding='utf-8')
    info_version = re.search(r'^modversion=(.+)$', info, re.M)[1].strip()
    if core_version != info_version:
        raise RuntimeError('Version mismatch: ' + core_version + ' / ' + info_version)
    report['version'] = core_version
    report['game_jar_sha256'] = hashlib.sha256((GAME / 'projectzomboid.jar').read_bytes()).hexdigest()
    report['runtime_sha256'] = {str(p.relative_to(MOD)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(MOD.rglob('*')) if p.is_file()}
    report['result'] = 'PASS'
    (RESULTS / 'offline-validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('OFFLINE RELEASE CHECKS PASS')


if __name__ == '__main__':
    main()
