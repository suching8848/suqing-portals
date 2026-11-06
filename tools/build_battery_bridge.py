"""Rebuild the archived 0.1.1 bridge only; never place it in the Lua runtime."""
from pathlib import Path
import hashlib
import json
import subprocess
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
JAVAC = Path(r'E:\code\java-1.8.0-openjdk-1.8.0.392-1.b08.redhat.windows.x86_64\bin\javac.exe')
BUILD = ROOT / 'tests/results/battery-bridge-classes'
JAR = ROOT / 'publishing/legacy-java/0.1.1-test.1/SuQingPortals.jar'


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    sources = sorted((ROOT / 'java/suqing/portals').glob('*.java'))
    subprocess.run([str(JAVAC), '-J-Xms16m', '-J-Xmx128m', '-J-XX:+UseSerialGC', '-J-XX:ReservedCodeCacheSize=32m',
                    '-encoding', 'UTF-8', '-source', '8', '-target', '8',
                    '-d', str(BUILD), *map(str, sources)], check=True)
    JAR.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(JAR, 'w', compression=ZIP_DEFLATED) as jar:
        manifest = ZipInfo('META-INF/MANIFEST.MF', (2026, 11, 6, 0, 0, 0))
        jar.writestr(manifest, 'Manifest-Version: 1.0\r\nImplementation-Version: 0.1.1-test.1\r\n\r\n')
        for path in sorted((BUILD / 'suqing/portals').glob('*.class')):
            info = ZipInfo(path.relative_to(BUILD).as_posix(), (2026, 11, 6, 0, 0, 0))
            jar.writestr(info, path.read_bytes(), compress_type=ZIP_DEFLATED)
    print(json.dumps({'jar': str(JAR), 'sha256': hashlib.sha256(JAR.read_bytes()).hexdigest(),
                      'game_started': False, 'dependencies_bundled': False}))


if __name__ == '__main__':
    main()
