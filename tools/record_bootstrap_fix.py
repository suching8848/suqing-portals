"""Record bootstrap repair, preserving and reporting unrelated state changes."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
GAME = Path(r'D:\steam\steamapps\common\ProjectZomboid')
OUT = GAME / 'CodexAssets/SuQingPortals_20261106'
ISO = OUT / 'IsolatedTest'
FIX = OUT / 'BootstrapFix_20261106'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
old = json.loads((OUT / 'protected-before.json').read_text(encoding='utf-8'))
observed = {p: sha(Path(p)) if Path(p).is_file() else None for p in old}
different = {p: {'initial_delivery_sha256': digest, 'observed_sha256': observed[p]}
             for p, digest in old.items() if observed[p] != digest}
isolation = json.loads((OUT / 'isolation-receipt.json').read_text(encoding='utf-8'))
assert isolation['pzo_retained'] is True
assert (ISO / 'data/mods/reset-mods-42_00.txt').exists()
ids = re.findall(r'^\s*mod\s*=\s*([^,\n]+),', (ISO / 'data/mods/default.txt').read_text(encoding='utf-8'), re.M)
assert ids == ['ZombieBuddy', 'Viewpoint', 'SuQingPortals', 'B42ModTrans_CN', 'B42Trans_CN']
launcher = (ISO / 'Launch-Isolated.ps1').read_text(encoding='utf-8-sig')
assert 'pzopt\\aot\\pzopt.jar;' in launcher
assert '-cachedir=' in launcher and "'-modfolders','mods'" in launcher
assert (ISO / 'data/pzopt/options.ini').exists()
receipt = dict(status='offline_bootstrap_checks_passed',
    retained_pzo=True, enabled=ids, classpath=isolation['classpath'],
    launcher=str(ISO / 'Start-Portal-Test.cmd'), first_run_reset_checks=21,
    pzo_interface_and_config_checks=47, game_started_by_agent=False,
    user_previous_launch='failed before mod loading; log recorded 0 mods',
    repaired_user_launch='pending', agents_rules=str(GAME / 'AGENTS.md'),
    files_written_scope=['isolated profile/launcher and private PZO options', 'project tools/docs', 'AGENTS.md'],
    formal_save_files_written_by_this_repair=False,
    differences_from_initial_delivery_baseline=different,
    baseline_difference_action='Preserved current files. No attribution or rollback.',
    other_protected_files_match_initial_baseline=[p for p in old if p not in different])
(FIX / 'repair-receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
import shutil
shutil.copy2(ROOT / 'docs/bootstrap-fix-20261106.md', FIX / '修复说明.md')
print(json.dumps(dict(pzo_retained=True, mods=len(ids), offline_checks='PASS',
    old_baseline_differences=len(different), rules_updated=True, receipt=str(FIX / 'repair-receipt.json')), ensure_ascii=False))
