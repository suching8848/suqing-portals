"""Freeze only this project's own runtime and verify every archived member."""
from pathlib import Path
import hashlib
import json
import zipfile
from datetime import datetime, timedelta, timezone
import argparse
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--artifact-suffix', default='', help='Unique local artifact revision; does not change gameplay version')
args = parser.parse_args()
if args.artifact_suffix and not re.fullmatch(r'[A-Za-z0-9_-]+', args.artifact_suffix):
    raise RuntimeError('Artifact suffix must contain only letters, digits, underscores or hyphens')

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(r'D:\steam\steamapps\common\ProjectZomboid\CodexAssets\SuQingPortals_20261106')
MOD = ROOT / 'mods/SuQingPortals/42'
sha = lambda b: hashlib.sha256(b).hexdigest()
validation = json.loads((ROOT / 'tests/results/offline-validation.json').read_text(encoding='utf-8'))
current = {str(p.relative_to(MOD)).replace('\\', '/'): sha(p.read_bytes()) for p in sorted(MOD.rglob('*')) if p.is_file()}
if validation['result'] != 'PASS' or validation['runtime_sha256'] != current:
    raise RuntimeError('Runtime changed after the successful offline checks; verify that change first.')
sources = [(p, 'mods/SuQingPortals/' + p.relative_to(ROOT / 'mods/SuQingPortals').as_posix())
           for p in sorted((ROOT / 'mods/SuQingPortals').rglob('*')) if p.is_file()]
sources += [(ROOT / 'README.md', 'README.md'), (ROOT / 'README.en.md', 'README.en.md')]
sources += [(p, p.relative_to(ROOT).as_posix()) for p in sorted((ROOT / 'docs').glob('*.md'))]
manifest = {name: dict(bytes=p.stat().st_size, sha256=sha(p.read_bytes())) for p, name in sources}
name = 'SuQingPortals_' + validation['version'] + ('_' + args.artifact_suffix if args.artifact_suffix else '') + '_test-candidate.zip'
archive = ROOT / 'publishing' / name
if archive.exists():
    raise RuntimeError('Frozen archive already exists; use a new candidate version.')
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
    for p, member in sources:
        z.write(p, member)
    z.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
with zipfile.ZipFile(archive) as z:
    if z.testzip() is not None:
        raise RuntimeError('Archive CRC verification failed')
    for member, record in manifest.items():
        data = z.read(member)
        if sha(data) != record['sha256'] or len(data) != record['bytes']:
            raise RuntimeError('Archive readback differs: ' + member)
receipt = dict(version=validation['version'], time=datetime.now(timezone(timedelta(hours=8))).isoformat(),
    source=str(ROOT), archive=str(archive), archive_bytes=archive.stat().st_size,
    archive_sha256=sha(archive.read_bytes()), members=len(sources),
    every_member_sha256_verified=True, game_started=False, gameplay_acceptance='pending_user',
    workshop_uploaded=False, git_remote_changed=False, manifest=manifest)
(ROOT / 'publishing/test-package-receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
OUT.mkdir(parents=True, exist_ok=True)
import shutil
shutil.copy2(archive, OUT / name)
shutil.copy2(ROOT / 'publishing/test-package-receipt.json', OUT / 'test-package-receipt.json')
shutil.copy2(ROOT / 'docs/用户测试步骤.md', OUT / '用户测试步骤.md')
print(json.dumps({k: receipt[k] for k in ('archive', 'members', 'archive_bytes', 'every_member_sha256_verified')}, ensure_ascii=False))
