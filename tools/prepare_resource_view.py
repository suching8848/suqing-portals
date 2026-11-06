"""Build a filtered resource view without editing the installed game.

The top-level media directory is real; only its unmodified large children are
junctions. Lua/shaders and small top-level resources are independent copies.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess

GAME = Path(r'D:\steam\steamapps\common\ProjectZomboid')
OUT = GAME / 'CodexAssets/SuQingPortals_20261106'
ENGINE = OUT / 'IsolatedTest/engine'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def excluded(rel, owned):
    text = rel.as_posix()
    return text in owned or 'pzopt' in rel.parts or rel.name.startswith('pzopt_')


def junction(target, source):
    if os.path.lexists(target):
        if target.resolve() != source.resolve():
            raise RuntimeError('Existing resource view differs: ' + str(target))
        return
    # Use one shell and literal arguments. This creates links only, never moves
    # or deletes a target. Paths are fixed to this task's IsolatedTest directory.
    command = '$ErrorActionPreference="Stop"; New-Item -ItemType Junction -Path ' + "'" + str(target).replace("'", "''") + "' -Target '" + str(source).replace("'", "''") + "' | Out-Null"
    subprocess.run(['powershell.exe', '-NoProfile', '-Command', command], check=True, capture_output=True)
    if target.resolve() != source.resolve():
        raise RuntimeError('Junction verification failed: ' + str(target))


def main():
    owned_file = GAME / 'pzopt-files.txt'
    owned = set(owned_file.read_text(encoding='utf-8-sig').splitlines())
    original_lua = {p.relative_to(GAME).as_posix(): digest(p)
                    for p in (GAME / 'media/lua').rglob('*') if p.is_file()}
    ENGINE.mkdir(parents=True, exist_ok=True)
    media = ENGINE / 'media'
    media.mkdir(exist_ok=True)
    if media.resolve() != media.absolute():
        raise RuntimeError('engine/media must be a real directory, never a junction to the original game')
    copied, skipped, links = {}, [], {}
    for source in sorted((GAME / 'media').iterdir()):
        target = media / source.name
        if source.is_dir() and source.name not in ('lua', 'shaders', 'ui'):
            junction(target, source)
            links[target.relative_to(ENGINE).as_posix()] = str(source)
        elif source.is_dir():
            target.mkdir(exist_ok=True)
            for file in sorted(source.rglob('*')):
                if not file.is_file():
                    continue
                rel = file.relative_to(GAME)
                if excluded(rel, owned):
                    skipped.append(rel.as_posix())
                    continue
                dest = ENGINE / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                # These are task-owned ordinary files, never links to originals.
                if dest.exists() and dest.resolve() != dest.absolute():
                    raise RuntimeError('Refusing to overwrite a resource link: ' + str(dest))
                shutil.copy2(file, dest)
                if digest(file) != digest(dest):
                    raise RuntimeError('Resource copy verification failed: ' + str(file))
                copied[rel.as_posix()] = digest(dest)
        elif source.is_file():
            rel = source.relative_to(GAME)
            if excluded(rel, owned):
                skipped.append(rel.as_posix())
                continue
            shutil.copy2(source, target)
            copied[rel.as_posix()] = digest(target)
    for name in ('stdlib.lua', 'stdlib.lbc', 'steam_appid.txt'):
        source = GAME / name
        if source.exists():
            shutil.copy2(source, ENGINE / name)
            copied[name] = digest(ENGINE / name)
    # Every known PZO media addition must be absent, not merely unreferenced.
    for rel in owned:
        if rel.startswith('media/') and (ENGINE / rel).exists():
            raise RuntimeError('PZO media resource leaked into isolated view: ' + rel)
    after_lua = {p.relative_to(GAME).as_posix(): digest(p)
                 for p in (GAME / 'media/lua').rglob('*') if p.is_file()}
    if original_lua != after_lua:
        raise RuntimeError('Installed game Lua changed concurrently during resource-view preparation')
    receipt = dict(engine_root=str(ENGINE), media_root=str(media),
        game_jar=str(GAME / 'projectzomboid.jar'), game_jar_sha256=digest(GAME / 'projectzomboid.jar'),
        copied_files=len(copied), copied_bytes=sum((ENGINE / x).stat().st_size for x in copied),
        excluded=skipped, shared_read_resources=links, copied_sha256=copied,
        original_lua_sha256=original_lua, original_lua_unchanged=True,
        game_started=False, note='Independent Lua/shader copies exclude PZO-owned additions. Large stock resources shared through directory junctions.')
    (ENGINE / 'resource-view.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: receipt[k] for k in ('engine_root', 'copied_files', 'copied_bytes', 'original_lua_unchanged')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
