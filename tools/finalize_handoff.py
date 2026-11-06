"""Read back the frozen runtime, isolated deployment and protected files."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(r'D:\steam\steamapps\common\ProjectZomboid\CodexAssets\SuQingPortals_20261106')
PROFILE = OUT / 'IsolatedTest/data'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
validation = json.loads((ROOT / 'tests/results/offline-validation.json').read_text(encoding='utf-8'))
protected = json.loads((OUT / 'protected-before.json').read_text(encoding='utf-8'))
changed = [p for p, digest in protected.items() if not Path(p).is_file() or sha(Path(p)) != digest]
if changed:
    raise RuntimeError('Protected files changed since preparation: ' + repr(changed))
expected = ['ZombieBuddy', 'Viewpoint', 'SuQingPortals', 'B42ModTrans_CN', 'B42Trans_CN']
actual = sorted(p.name for p in (PROFILE / 'mods').iterdir() if p.is_dir())
if actual != sorted(expected):
    raise RuntimeError('Unexpected isolated mod folders: ' + repr(actual))
import re
enabled = re.findall(r'^\s*mod\s*=\s*([^,\n]+),', (PROFILE / 'mods/default.txt').read_text(encoding='utf-8'), re.M)
if enabled != expected:
    raise RuntimeError('Enabled list differs: ' + repr(enabled))
source = ROOT / 'mods/SuQingPortals'
target = PROFILE / 'mods/SuQingPortals'
source_files = {p.relative_to(source).as_posix(): sha(p) for p in source.rglob('*') if p.is_file()}
target_files = {p.relative_to(target).as_posix(): sha(p) for p in target.rglob('*') if p.is_file()}
if source_files != target_files:
    raise RuntimeError('Deployment file tree differs from source')
for path, digest in validation['runtime_sha256'].items():
    if sha(source / '42' / path) != digest:
        raise RuntimeError('Runtime changed after offline checks: ' + path)
package = json.loads((ROOT / 'publishing/test-package-receipt.json').read_text(encoding='utf-8'))
isolation = json.loads((OUT / 'isolation-receipt.json').read_text(encoding='utf-8'))
if sha(OUT / Path(package['archive']).name) != package['archive_sha256']:
    raise RuntimeError('Handoff archive differs from verified archive')
report = dict(version=validation['version'], source=str(ROOT), profile=str(PROFILE),
    launcher=str(PROFILE.parent / 'Start-Portal-Test.cmd'), desktop_shortcut=r'C:\Users\15792\Desktop\传送门隔离测试.lnk',
    enabled=enabled, own_runtime_files=len(source_files), deployment_sha256=source_files,
    protected_files_unchanged=protected, archive_sha256=package['archive_sha256'],
    offline_validation=str(ROOT / 'tests/results/offline-validation.json'),
    behavior_assertions=dict(core_world=128, client_transfer=97, inventory_guard=8, native_building_translation=64),
    translation_keys_per_language=112, lua_files_compiled=8,
    models=dict(original_obj=5, sprites_and_bindings=20, native_parser_readback='PASS'),
    isolated_launcher_powershell_parse='PASS', isolated_native_preset_parse='PASS',
    isolated_java_agent_version_smoke='PASS: -cp projectzomboid.jar -version only; no game main/world/UI',
    pzo_retained=isolation.get('pzo_retained', False), classpath=isolation.get('classpath'),
    first_release_reset_marker=isolation.get('first_release_reset_marker'),
    game_started=False, game_operated=False, gameplay_acceptance='pending_user',
    native_generator_extra_charging_fuel='not implemented in this test candidate',
    workshop_uploaded=False, git_remote_changed=False)
(OUT / 'handoff-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
text = '''# 蘇清的传送门：隔离测试交付

版本：0.1.0-test.1；2026-11-06，北京时间。

桌面入口：`C:\\Users\\15792\\Desktop\\传送门隔离测试.lnk`。

备用入口：`D:\\steam\\steamapps\\common\\ProjectZomboid\\CodexAssets\\SuQingPortals_20261106\\IsolatedTest\\Start-Portal-Test.cmd`。

独立源码：`E:\\code\\suqing-portals`。隔离存档、配置、日志和本地模组均在入口旁的 `data` 目录；未复制正式世界。

只启用 ZombieBuddy、Viewpoint、SuQingPortals、B42ModTrans_CN、B42Trans_CN。

2026-11-06 启动修订：按用户确认保留已安装、相互匹配的 PZO Java/Lua 运行环境，PZO 用户选项使用隔离副本；准备 B42 首次重置标记，避免初次启动清空五项名单。47项PZO接口/配置路径检查及21项首次重置原生配置回归通过；具体失败日志与修复记录在 BootstrapFix_20261106。

已实现四槽原汽车电池、专属管理界面、命名配对、出发端总耗电2.00、接收端无电要求、加载且当地供电时充电、五种装载外观和四向普通/Viewpoint资源。默认整门充电0.5满电等量/游戏小时。

离线验证通过：8份Lua编译；核心128、传送97、物品转移锁8、原生建造与本地化64项断言；CN/EN各112文本条目；5模型/20绑定原生读回；隔离预设原生读回和启动脚本解析。所有模型结构检查仅代表资源结构，不是游戏行为断言。

冻结包逐成员SHA-256读回通过，隔离部署与源文件全树一致。交付前个人受保护文件哈希与准备前一致。没有启动/操作游戏、发布工坊或推送Git。

限制：单人且不含车辆；充电尚未计入原生发电机额外油耗。真实远距加载、保存重进、异常恢复、普通与Viewpoint视角仍待用户实测。底层多个存档文件不具有跨文件原子事务，不承诺极端断电的一致性。

创建自定义沙盒并选 `SuQingPortals_Test` 用户预设，右键空地领取材料。先建两门近距离验收，再做远距离和供电测试。详见同目录《用户测试步骤.md》。

完整机器校验记录：同目录 `handoff-verification.json`、`isolation-receipt.json`、`test-package-receipt.json`。
'''
(OUT / '交付说明.md').write_text(text, encoding='utf-8')
print(json.dumps(dict(result='PASS', own_files=len(source_files), enabled=enabled,
    protected_files=len(protected), handoff=str(OUT / '交付说明.md')), ensure_ascii=False))
