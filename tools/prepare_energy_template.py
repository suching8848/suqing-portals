"""Prepare an independent outage template copied from the existing isolated save.

No game is launched. Without --apply this performs read-only preflight plus
compilation of the standalone parser helper. The original save and latestSave
are never edited. Failed copies remain explicitly named .partial.
"""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
GAME = Path(r'D:\steam\steamapps\common\ProjectZomboid')
ISO = GAME / 'CodexAssets/SuQingPortals_20261106/IsolatedTest'
SAVES = ISO / 'data/Saves/Sandbox'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def inventory(path):
    entries={}
    for file in sorted(path.rglob('*')):
        if file.is_symlink() or (hasattr(file,'is_junction') and file.is_junction()):
            raise RuntimeError('Linked save contents are refused: '+str(file))
        if file.is_file():entries[file.relative_to(path).as_posix()]={'bytes':file.stat().st_size,'sha256':sha(file)}
    if not entries:raise RuntimeError('Empty source world')
    return entries


def run(arguments,cwd=ROOT):
    done=subprocess.run([str(x) for x in arguments],cwd=cwd,capture_output=True,encoding='utf-8',errors='replace',timeout=60)
    if done.returncode:raise RuntimeError('Command failed: '+done.stderr[-1800:]+done.stdout[-1800:])
    return done.stdout


def stopped():
    result=run(['powershell.exe','-NoProfile','-Command',
        "$p=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^(java|javaw|ProjectZomboid)' -and $_.CommandLine -like '*-cachedir="+str(ISO/'data')+"*'});$p.Count"])
    if result.strip()!='0':raise RuntimeError('Isolated game is running; normal exit is required')


def native_evidence():
    from validate_power_api import javap_tool
    def code(name):return run([javap_tool(),'-c','-p','-classpath',GAME/'projectzomboid.jar',name])
    sandbox,world,time=code('zombie.SandboxOptions'),code('zombie.iso.IsoWorld'),code('zombie.GameTime')
    for needle in ('String ElecShutModifier','iconst_m1','int 2147483647','doesPowerGridExist(int)','Method getElecShutModifier:()I'):
        if needle not in sandbox:raise RuntimeError('Native shutdown semantics changed: '+needle)
    if not re.search(r'String ElecShutModifier[\s\S]{0,700}iconst_m1[\s\S]{0,700}int 2147483647',sandbox):
        raise RuntimeError('Cannot verify native shutdown integer bounds')
    start=sandbox.index('public boolean doesPowerGridExist(int);'); predicate=sandbox[start:start+1400]
    for needle in ('getWorldAgeDays:()F','getElecShutModifier:()I','iadd','fcmpg','ifgt'):
        if needle not in predicate:raise RuntimeError('Native grid comparison changed: '+needle)
    if not re.search(r'Method zombie/SandboxOptions.doesPowerGridExist:\(\)Z[\s\S]{0,180}Field hydroPowerOn:Z',world):
        raise RuntimeError('Cannot verify native initial hydroPowerOn assignment')
    if 'public double getWorldAgeDaysSinceBegin();' not in time or 'public double getWorldAgeHours();' not in time:
        raise RuntimeError('Saved time formula requires review')
    return dict(game_jar_sha256=sha(GAME/'projectzomboid.jar'),predicate='worldAgeDays <= ElecShutModifier (+ offset 0)',
        hydro_initialization='IsoWorld init assigns SandboxOptions.doesPowerGridExist()',
        value=-1,native_integer_bounds=[-1,2147483647],map_t_modified=False,
        limit='Bytecode/native-parser evidence only; no game or world was started')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=SAVES/'2026-11-06_15-46-59')
    parser.add_argument('--destination',type=Path,default=SAVES/'2026-11-06_Energy_Template')
    parser.add_argument('--mods-from',type=Path,default=ISO/'data/mods/default.txt')
    parser.add_argument('--apply',action='store_true',help='Create the new verified world copy; never edits source/latestSave')
    args=parser.parse_args()
    source,destination,mods=args.source.resolve(),args.destination.resolve(),args.mods_from.resolve()
    if source.parent!=SAVES.resolve() or destination.parent!=SAVES.resolve() or source==destination:
        raise RuntimeError('Source and destination must be distinct direct children of the isolated Sandbox saves directory')
    if not source.is_dir() or source.is_symlink() or (hasattr(source,'is_junction') and source.is_junction()):raise RuntimeError('Source is absent or redirected')
    if destination.exists():raise RuntimeError('Destination already exists; refusing to overwrite '+str(destination))
    if not mods.is_file() or not mods.is_relative_to((ISO/'data').resolve()):raise RuntimeError('Mod-list source must be inside this isolated profile')
    partial=destination.with_name(destination.name+'.partial')
    if partial.parent!=SAVES.resolve() or partial.exists():raise RuntimeError('Partial destination already exists or escaped isolation')
    stopped()
    evidence=native_evidence()
    before=inventory(source)
    for required in ('map_sand.bin','map_t.bin','mods.txt'):
        if required not in before:raise RuntimeError('Source world lacks '+required)
    pointers=[ISO/'data/latestSave.ini',ISO/'data/mods/default.txt',source/'mods.txt',source/'map_sand.bin']
    protected={str(p):sha(p) for p in pointers if p.is_file()}
    classes=ROOT/'tests/results/energy-template-classes';classes.mkdir(parents=True,exist_ok=True)
    javac=Path(r'E:\code\java-1.8.0-openjdk-1.8.0.392-1.b08.redhat.windows.x86_64\bin\javac.exe')
    run([javac,'-encoding','UTF-8','-d',classes,ROOT/'tools/PortalEnergySandboxTool.java'])
    java=[GAME/'jre64/bin/java.exe','-Xint','-Xms16m','-Xmx128m','-XX:+UseSerialGC',
        '-Duser.home='+str(ROOT/'tests/results/native-home'),'-cp',str(classes)+';'+str(GAME/'projectzomboid.jar'),'PortalEnergySandboxTool']
    def helper(action,sand,time,modfile,output=None):
        stdout=run(java+[action,sand,time,modfile]+([output] if output else []),cwd=GAME)
        lines=[line[len('ENERGY_SANDBOX_JSON:'):] for line in stdout.splitlines() if line.startswith('ENERGY_SANDBOX_JSON:')]
        if len(lines)!=1:raise RuntimeError('Native helper did not return exactly one receipt: '+stdout[-1200:])
        return json.loads(lines[0])
    original=helper('inspect',source/'map_sand.bin',source/'map_t.bin',source/'mods.txt')
    enabled=helper('inspect',source/'map_sand.bin',source/'map_t.bin',mods)
    old_order,new_order=original['native_mod_order'],enabled['native_mod_order']
    if len(set(new_order))!=len(new_order) or [x for x in new_order if x in old_order]!=old_order:
        raise RuntimeError('Requested template mod order removes or reorders existing enabled mods')
    if 'SuQingPortals' not in new_order or 'ISA' not in new_order or 'ISA-Fix' in new_order:
        raise RuntimeError('Template must contain SuQingPortals plus supported ISA, without ISA-Fix')
    if not args.apply:
        print(json.dumps(dict(status='PREFLIGHT_PASS_NO_SAVE_WRITES',source=str(source),destination=str(destination),
            source_files=len(before),native=enabled,evidence=evidence),ensure_ascii=False));return
    total=sum(item['bytes'] for item in before.values())
    if shutil.disk_usage(SAVES).free<total+32*1024*1024:raise RuntimeError('Insufficient free space for a complete isolated world copy')
    stopped()
    shutil.copytree(source,partial,copy_function=shutil.copy2)
    if inventory(partial)!=before or inventory(source)!=before:raise RuntimeError('Full source/copy readback failed; .partial is not a usable template')
    changed=helper('rewrite',partial/'map_sand.bin',partial/'map_t.bin',mods,partial/'map_sand.bin')
    shutil.copy2(mods,partial/'mods.txt')
    after=inventory(partial)
    differences=[name for name in set(before)|set(after) if before.get(name)!=after.get(name)]
    if set(before)!=set(after) or set(differences)-{'map_sand.bin','mods.txt'} or 'map_sand.bin' not in differences:
        raise RuntimeError('Unexpected template change; .partial preserved for diagnosis')
    if inventory(source)!=before or any(sha(Path(p))!=h for p,h in protected.items()):
        raise RuntimeError('Source or isolated pointers changed during preparation')
    stopped()
    partial.rename(destination)
    if inventory(destination)!=after:raise RuntimeError('Final template readback failed')
    now=datetime.now(timezone(timedelta(hours=8))).isoformat()
    receipt=dict(status='VERIFIED_DERIVED_OUTAGE_TEMPLATE',created_at=now,source=str(source),destination=str(destination),
        new_save=str(destination),original_save_unchanged=True,elec_shut_modifier=-1,electricity_off=True,native_validation=changed,
        source_files=len(before),total_bytes=total,source_manifest=before,template_manifest=after,
        changed_files=sorted(differences),all_other_members_sha256_identical=True,source_unchanged=True,
        protected_pointers_unchanged=protected,mods_from=str(mods),mod_order=new_order,native=changed,evidence=evidence,
        blank_world=False,created_in_game=False,game_started=False,world_instantiated=False,latest_save_changed=False,
        newly_placed_objects_or_granted_supplies=False,recovery='Original source world is unchanged. Select the original source to return; no automatic deletion or rollback was performed.')
    record=destination.parent/(destination.name+'-preparation.json')
    record.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    current=ISO.parent/'current-energy-template.json'
    current.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    notes=destination.parent/(destination.name+'-说明.md')
    notes.write_text('# 已停电能源测试模板\n\n'+f'准备时间：{now}。\n\n模板：`{destination}`。\n\n来源：`{source}`。本模板是原隔离档的完整复制，保留其人物、建筑和进度，并非空白世界或游戏内新建世界；没有预放新门、太阳能设备或物资。\n\n'+
        '仅在新副本将 ElecShutModifier 设为 -1，并按隔离名单追加 ISA 及前置。原生配置与字符串解析、SAND/GMTM格式和当前字节码证明再次加载时市电判定为关闭；没有启动游戏，实际玩法仍由用户验收。map_t.bin和其他世界文件逐SHA-256保持原样。\n\n'+
        '从原桌面隔离入口启动，在“载入”中选择本模板；不要点继续后误入原档。原latestSave.ini未修改。原隔离档完整保留，需要回到原进度时选择原档即可。没有自动删除模板或覆盖回滚。\n\n'+f'完整收据：`{record}`。\n',encoding='utf-8')
    print(json.dumps(dict(status=receipt['status'],destination=str(destination),source_files=len(before),changed_files=sorted(differences),
        modifier=-1,world_age_days=changed['world_age_days'],hydro_power_on_after_load=False,receipt=str(record),game_started=False),ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps(dict(status='FAIL',error=str(error)),ensure_ascii=False));sys.exit(1)
