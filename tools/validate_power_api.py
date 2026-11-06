"""Read current bytecode and optional ISA sources; never initializes a game or writes files."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

GAME = Path(r'D:\steam\steamapps\common\ProjectZomboid')
ISA = Path(r'D:\steam\steamapps\workshop\content\108600\3781944805\mods\ImmersiveSolarArrays\42')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def javap_tool():
    candidates = [shutil.which('javap')]
    if os.environ.get('JAVA_HOME'):
        candidates.append(str(Path(os.environ['JAVA_HOME']) / 'bin/javap.exe'))
    candidates.extend((
        r'E:\code\java-1.8.0-openjdk-1.8.0.392-1.b08.redhat.windows.x86_64\bin\javap.exe',
        r'E:\code\HBuilderX\plugins\amazon-corretto\bin\javap.exe',
    ))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError('No javap executable available for read-only native API verification')


def main():
    jar = GAME / 'projectzomboid.jar'
    executable = javap_tool()
    cache = {}
    checks = []

    def bytecode(name):
        if name not in cache:
            result = subprocess.run([executable, '-constants', '-c', '-p', '-classpath', str(jar), name],
                                    capture_output=True, encoding='utf-8', errors='replace', timeout=30)
            if result.returncode:
                raise RuntimeError('javap failed for ' + name + ': ' + result.stderr[-800:])
            cache[name] = result.stdout
        return cache[name]

    def method(name, signature):
        content = bytecode(name)
        header = re.search(r'^  ' + re.escape(signature) + r'\s*$', content, re.M)
        if not header:
            raise RuntimeError('Required native signature missing: ' + name + '.' + signature)
        tail = content[header.end():]
        following = re.search(r'^  [^ \r\n][^\r\n]*;\s*$', tail, re.M)
        return tail[:following.start()] if following else tail

    def expect(label, value):
        if not value:
            raise RuntimeError('Native power assumption no longer holds: ' + label)
        checks.append(label)

    generator = 'zombie.iso.objects.IsoGenerator'
    for signature in (
        'public static boolean isPoweringSquare(int, int, int, int, int, int);',
        'public float getFuel();', 'public void setFuel(float);', 'public float getMaxFuel();',
        'public boolean isActivated();', 'public boolean isConnected();',
        'public int getCondition();', 'public void setActivated(boolean);',
        'public float getTotalPowerUsing();',
    ):
        method(generator, signature)
        checks.append(signature)
    method('zombie.iso.IsoCell', 'public java.util.ArrayList<zombie.iso.IsoObject> getProcessIsoObjects();')
    checks.append('loaded process-IsoObject enumeration')
    method('zombie.iso.IsoChunk', 'public boolean isGeneratorPoweringSquare(int, int, int);')
    checks.append('native chunk generator coverage')
    method('zombie.iso.IsoGridSquare', 'public boolean haveElectricity();')
    method('zombie.iso.IsoGridSquare', 'public boolean hasGridPower();')
    checks.append('local and grid electricity predicates')
    expect('native charger fuel load is 0.05 L/hour before sandbox multiplier',
           'public static final float BatteryChargerPowerConsumption = 0.05f;' in bytecode(generator))
    charger = 'zombie.iso.objects.IsoCarBatteryCharger'
    constructor = method(charger, 'public zombie.iso.objects.IsoCarBatteryCharger(zombie.iso.IsoCell);')
    expect('native charger defaults to one full-battery equivalent per six game hours',
           'float 0.16666667f' in constructor and 'Field chargeRate:F' in constructor)
    consumption = method(charger, 'public float getGeneratorPowerConsumption();')
    expect('native charger has 0.05 active load and zero inactive load',
           'Method isActivated:()Z' in consumption and 'float 0.05f' in consumption and 'fconst_0' in consumption)
    fuel = method(generator, 'public float getFuel();')
    limit = method(generator, 'public float getMaxFuel();')
    setter = method(generator, 'public void setFuel(float);')
    percentage = method(generator, 'public float getFuelPercentage();')
    expect('fuel getter uses the raw float tank amount, not percentage', 'Field fuel:F' in fuel)
    expect('fuel tank maximum is 10 litres', 'float 10.0f' in limit)
    expect('setFuel clamps to the same 0..10 raw fuel range',
           'float 10.0f' in setter and 'java/lang/Math.min:(FF)F' in setter and
           'java/lang/Math.max:(FF)F' in setter and 'Field fuel:F' in setter)
    expect('fuel-percentage getter converts raw tank amount with /10 *100',
           'float 10.0f' in percentage and 'fdiv' in percentage and 'float 100.0f' in percentage and 'fmul' in percentage)
    expect('setFuel does not itself switch the generator off', 'Method setActivated:' not in setter)
    update = method(generator, 'public void update();')
    expect('native fuel debit applies GeneratorFuelConsumption once to hourly raw load',
           'Field totalPowerUsing:F' in update and 'generatorFuelConsumption:' in update and
           'dmul' in update and 'fsub' in update and 'Field fuel:F' in update)
    total = method(generator, 'public float getTotalPowerUsing();')
    expect('display getter total is already multiplied by GeneratorFuelConsumption',
           'Field totalPowerUsing:F' in total and 'generatorFuelConsumption:' in total and 'dmul' in total)
    method(generator, 'private void addPoweredItem(zombie.iso.IsoObject, float);')
    checks.append('addPoweredItem is private; the Lua adapter must not pretend to register native devices')

    upstream = dict(installed=ISA.is_dir(), hashes={})
    if ISA.is_dir():
        info = (ISA / 'mod.info').read_text(encoding='utf-8-sig')
        upstream['version'] = re.search(r'^modversion=(.+)$', info, re.M)[1].strip()
        upstream['mod_id'] = re.search(r'^id=(.+)$', info, re.M)[1].strip()
        for relative in ('mod.info',
                         'media/lua/server/ImmersiveSolarArrays/PowerBank/PowerBankObject_Server.lua',
                         'media/lua/server/ImmersiveSolarArrays/PowerBank/PowerBankSystem_Server.lua',
                         'media/lua/server/ImmersiveSolarArrays/PowerBank/SolarScan.lua'):
            path = ISA / relative
            if path.is_file():
                upstream['hashes'][relative] = sha(path)
        upstream['hashes_are_observed_snapshot_not_permanent_version_gate'] = True
    print(json.dumps(dict(result='PASS', checks=len(checks), scope='Read-only javap bytecode and optional upstream source hashes; no game initialization',
        game_jar_sha256=sha(jar), native_charger=dict(load_litres_per_hour=0.05,
        full_battery_equivalents_per_game_hour=1/6, litres_per_full_battery_equivalent=0.3,
        fuel_capacity_litres=10, sandbox_fuel_multiplier_applied_by_bridge=True),
        isa=upstream, game_started=False, files_written=False), ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps(dict(result='FAIL', error=str(error)), ensure_ascii=False))
        sys.exit(1)
