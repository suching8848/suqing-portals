"""Write the current pure-Lua delivery receipt from verified offline results."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(r'D:\steam\steamapps\common\ProjectZomboid\CodexAssets\SuQingPortals_20261106')
state = json.loads((ROOT / 'publishing/pure-lua-upgrade-state.json').read_text(encoding='utf-8'))
folder = Path(state['folder'])
deploy = json.loads((folder / 'deployment-receipt.json').read_text(encoding='utf-8'))
validation = json.loads((ROOT / 'tests/results/offline-validation.json').read_text(encoding='utf-8'))
package = json.loads((ROOT / 'publishing/test-package-receipt.json').read_text(encoding='utf-8'))
if not (deploy['version'] == validation['version'] == package['version'] == '0.1.2-lua-test.1'):
    raise RuntimeError('Delivery versions differ')
if validation['result'] != 'PASS' or not package['every_member_sha256_verified'] or not deploy['foundation_unchanged']:
    raise RuntimeError('Missing successful delivery check')

def count(log, pattern):
    text = (ROOT / 'tests/results' / (log + '.log')).read_text(encoding='utf-8')
    return int(re.search(pattern, text)[1])

counts = dict(
    lua_files=count('kahlua_compile', r'COMPILE PASS files=(\d+)'),
    backend=count('core_world', r'assertions passed: (\d+)'),
    client=count('client_transfer', r'checks=(\d+) failures=0'),
    guard=count('inventory_guard', r'checks=(\d+) failures=0'),
    native_stock=count('native_internal_storage_stock', r'checks=(\d+) failures=0'),
    native_pzo=count('native_internal_storage_pzo', r'checks=(\d+) failures=0'),
    native_building=count('native_building_localization', r'checks=(\d+) failures=0'),
    localization=validation['checks']['localization']['keys_per_language'])
handoff = OUT / '交付说明.md'
previous = folder / 'previous-delivery-0.1.1.md'
if handoff.exists() and not previous.exists():
    shutil.copy2(handoff, previous)

report = f'''# 蘇清的传送门 {deploy['version']} 隔离测试交付

更新时间：{datetime.now(timezone(timedelta(hours=8))).isoformat()}。

纯Lua版已更新到原隔离实例。继续使用桌面「传送门隔离测试」，入口仍为：

`{OUT / 'IsolatedTest/Start-Portal-Test.cmd'}`

传送门自带JAR已经移出部署目录，Mod ID仍为`SuQingPortals`，不再有传送门Java加载声明或新增传送门组件许可步骤。PZO、Viewpoint及其框架、两项汉化、原启用顺序与隔离入口均保留。这里的纯Lua指传送门功能；Viewpoint和PZO原有Java组件仍保留。

## 当前功能

- 四个专用汽车电池槽，右键可见门体进行管理、装卸、命名及配对；界面显示每槽耐久和电量、总电量、可传送次数、充电及禁用原因。
- 原电池留在门的原生内部存储中，由游戏原有存档机制完整保存；Lua隐藏普通容器按钮、排除附近制作取材，并在原生转移动作校验与最终执行处阻止绕过。专属四槽操作移动原件，不按类型重建电池。任意第三方直接扫描世界物品不属于这些原生界面拦截范围。
- 保存重进后重新绑定内部仓拒绝普通插入的函数；旧版未完成传送的原容器继续保持转移锁。异常时保护原件并显示原因。
- 保留上一轮修正的128×256门体图片、地面锚点、16种实际槽位状态、64方向绑定及Viewpoint模型。外观和点击尚待用户游戏内验收。
- 每次仅由出发端扣除2.00块满电等量；到达端无电池、无供电仍可接收。仅加载且当地通电时充电，默认整门每游戏小时0.5等量；不追补卸载／离线时间。充电尚未增加原生发电机额外油耗。

## 离线检查

统一检查全部通过：{counts['lua_files']}份Lua编译，CN/EN各{counts['localization']}键；后端{counts['backend']}项、客户端动作／界面／命中／传送{counts['client']}项、提取当前原版方法后的容器入口回归{counts['guard']}项。原生内部仓与正常IsoObject保存／重载在原版类路径及保留PZO的类路径下各{counts['native_stock']}项通过，确认四原电池ID、类型、电量、耐久、中文自定义名和嵌套数据完整。原生建造和真实Translator参数{counts['native_building']}项通过，模型／pack／Viewpoint原生解析通过。

上述测试只运行独立解释器、原生序列化与资源解析夹具，未启动游戏主程序、世界或渲染器，也未操作游戏。

部署{deploy['deployed_files']}个文件与冻结候选全树SHA-256一致，传送门JAR／class数量为0。发行ZIP共{package['members']}个文件成员逐SHA-256读回一致：

`{OUT / Path(package['archive']).name}`

ZIP SHA-256：`{package['archive_sha256']}`。

## 用户优先验收

1. 正常退出当前游戏，再从原隔离入口启动，继续测试档`2026-11-06_15-46-59`。只读审计确认该档仍是0.1.0格式，含4门、无未完成传送；无需重建世界。迁移在你下次读档时发生。
2. 检查旧门完整贴地，新建绿框位于底座；右键门框、底座和电池仓应打开菜单，普通附近容器栏不显示门。
3. 通过专属界面装卸第2、4槽，核对原件、电量和外观；普通箱子转移正常，普通拖放、全部转移和制作不应取到门内电池。
4. 保存退出重进，再检查四槽、名称、配对和电量；测试起点扣2.00、空门接收、远区加载及受阻退款。切换普通视角和Viewpoint检查四朝向。

详细步骤：同目录《用户测试步骤.md》。实际外观、Viewpoint点击、远距加载、保存重进及玩法验收统一由用户完成，离线通过不代表这些项目已实测。

若另有0.1.1 Java版已装电池的存档，纯Lua版会保留其不透明数据并拒绝解码，需先在对应旧版中取回原电池后保存；不会清空或仿造电池。当前目标档不属于此情况。

## 保护及恢复

部署前后当前隔离测试档全部{state['world_files']}个文件SHA-256一致，模组迁移尚未写入存档。正式档未写入；本轮选定保护文件与开始时一致。四项基础模组、PZO用户配置、启动入口、默认名单及重置标记逐文件校验保持一致；游戏、PZO原件未改。未上传工坊、推送Git或启动游戏。

完整隔离世界及0.1.0运行资源备份：

`{state['world_archive']}`

SHA-256：`{state['world_archive_sha256']}`。此次与当前世界全部文件重新比对一致，复用该已校验完整快照，没有重复制作大型世界备份。

升级前0.1.1运行文件及入口另存：

`{state['previous_runtime_archive']}`

SHA-256：`{state['previous_runtime_sha256']}`。自带JAR仅保存在此恢复ZIP及源码的`publishing/legacy-java/0.1.1-test.1`历史目录，不在运行包中。

回退会丢失快照之后的测试进度；先保留当前进度，再将世界和对应运行版本一起恢复到隔离目录。不要把旧模组单独覆盖到已升级schema3的新进度，也不要覆盖正式档。这里没有执行回退。

本轮完整收据：`{folder}`。机器记录：`{OUT / 'current-test-version.json'}`。源码及验证日志：`{ROOT}`及其`tests/results`。

## English

Pure-Lua portal {deploy['version']} is deployed to the existing isolated test profile. It adds no portal Java binary or reflection bridge. PZO, Viewpoint, their existing framework, both translations, enable order and launcher remain intact. Original car batteries persist in native internal storage; Lua hides ordinary inventory/crafting access and reserves installation/removal for the four-slot management window. Corrected models, pairing, source-only 2.00 energy cost and loaded/local-power charging remain.

All offline checks above passed; the {state['world_files']}-file test world and selected personal protection files are unchanged. The existing schema1 test world can be continued. Nonempty Java-test schema2 records remain protected and require export through the corresponding old version. No game was launched or controlled; visual, Viewpoint, distant travel and save/reload acceptance remain the user's responsibility. Recovery archives and hashes above apply only to the isolated profile.
'''
handoff.write_text(report, encoding='utf-8')
(folder / '纯Lua更新结果.md').write_text(report, encoding='utf-8')
shutil.copy2(ROOT / 'tests/results/offline-validation.json', folder / 'offline-validation.json')
shutil.copy2(ROOT / 'tests/results/pure_lua_save_audit.json', folder / 'pure_lua_save_audit.json')
(folder / 'acceptance-status.json').write_text(json.dumps(dict(
    counts=counts, version=deploy['version'], offline_pass=True, game_started=False,
    gameplay_acceptance='pending_user', report_sha256=hashlib.sha256(handoff.read_bytes()).hexdigest()),
    ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(dict(report=str(handoff), checks=counts, game_started=False), ensure_ascii=False))
