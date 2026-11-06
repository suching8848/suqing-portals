"""Write the final combined recipe/cost/localization delivery from readback receipts."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import json
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(r'D:\steam\steamapps\common\ProjectZomboid\CodexAssets\SuQingPortals_20261106')
state = json.loads((ROOT / 'publishing/recipe-upgrade-state.json').read_text(encoding='utf-8'))
text_state = json.loads((ROOT / 'publishing/text-hotfix-state.json').read_text(encoding='utf-8'))
folder = Path(state['folder'])
deploy = json.loads((folder / 'deployment-receipt.json').read_text(encoding='utf-8'))
validation = json.loads((ROOT / 'tests/results/offline-validation.json').read_text(encoding='utf-8'))
package = json.loads((ROOT / 'publishing/test-package-receipt.json').read_text(encoding='utf-8'))
if not (deploy['version'] == validation['version'] == package['version'] == '0.1.3-lua-test.1'):
    raise RuntimeError('Final delivery versions differ')
if validation['result'] != 'PASS' or not package['every_member_sha256_verified'] or not deploy['foundation_unchanged']:
    raise RuntimeError('Missing successful checks')


def count(name, pattern=r'checks=(\d+) failures=0'):
    return int(re.search(pattern, (ROOT / 'tests/results' / (name + '.log')).read_text(encoding='utf-8'))[1])


counts = dict(backend=count('core_world', r'assertions passed: (\d+)'), client=count('client_transfer'),
    guard=count('inventory_guard'), building=count('native_building_localization'),
    translation_stock=count('native_translation_interop_stock'), translation_pzo=count('native_translation_interop_pzo'),
    picker_stock=count('native_picker_interop_stock'), storage_stock=count('native_internal_storage_stock'),
    localization=validation['checks']['localization']['keys_per_language'])
report = f'''# 蘇清的传送门 {deploy['version']} 隔离测试交付

时间：{datetime.now(timezone(timedelta(hours=8))).isoformat()}。原桌面「传送门隔离测试」入口继续使用，可续原隔离档`2026-11-06_15-46-59`。

用户已反馈上一版基本正常，并指出菜单占位符残留；本版新配方、设置和文字显示仍待用户游戏内验收。

## 本轮完成

**新配方，每座门：**小金属板8、金属管4、电线8、电子零件16、高端相机1、手持对讲机1。要求电工4级、焊接3级。螺丝刀、焊枪、焊接面罩保留；本版不额外扣焊枪燃料或焊条。接受原版`Base.WalkieTalkie1..5`及`Base.WalkieTalkieMakeShift`，不把收音机或HAM电台当对讲机。沿用原生工具标签的正常替代物。汽车电池仍在建好后安装，最多四块。

沿用原生建造配方、技能条件与扣料机制，没有Lua再次扣料，原实体／配方ID不变。已有门不补扣材料，位置、配对和原电池数据保持。实际技能门槛、取消建造和扣料由用户验收。

**三个沙盒设置：**单次传送耗电0.5～4，默认2；整门每游戏小时充电0.05～4，默认0.5；隔离测试工具默认关闭，既有测试预设开启。耗电全部由出发端提供；接收端无需电池或当地供电。四块满电在耗电0.5时可传送8次、2时2次、4时1次。界面、禁用原因和实际扣费使用同一实际耗电；进行中的交易始终按原票据结算与退款，不因后来设置变更重算。旧档没有新设置时回退默认2，本轮不修改存档沙盒值。

**文字显示修复：**原生JSON加载会将源`%1`转成格式化占位符；旧资源预先写成`%1$s`，被再转换后残留`$s`。CN/EN源文件统一回到原生`%1`格式，字面百分号保留`%%`；实测夹具覆盖门名、槽号、电量、耐久、次数及含中文、百分号和字面`$s`的名字。修正了旧离线检查用`Function.identity`跳过预处理的缺口。没有更换字体或损坏存档编码。

**新版测试材料包：**右键地面主动领取两门材料、三件共用工具和八块满电电池，共87件。内容版本为2，领取过旧包的角色可主动领取新版一次；重复领取被拒，中断后仅补剩余。默认DebugTools门禁保留，出生／读档不自动发物品，也不改变技能。技能不足请由你在隔离原版调试菜单自行设置电工4、焊接3，或正常练级。

传送门继续采用纯Lua，运行目录无自有JAR／class。PZO、Viewpoint及其必要框架、两项汉化、加载顺序与入口均保留。模型／锚点沿用此前修正版，无新增美术改动。充电额外油耗仍未加入原生发电机，车辆和联机暂不支持。

## 离线检查与保护

统一检查通过：CN/EN各{counts['localization']}键；后端{counts['backend']}项、客户端／动作／界面／测试包{counts['client']}项、容器入口{counts['guard']}项；原生配方／技能／材料／保留工具／沙盒定义及Translator检查{counts['building']}项。真实JSON预处理＋Lua全局翻译在原版与PZO环境各{counts['translation_stock']}项通过；真实拾取对象交互各{counts['picker_stock']}项、原生电池保存／正常对象重载各{counts['storage_stock']}项通过。Lua编译、模型资源及Viewpoint原生解析通过。

仅执行独立解释器、原生解析和最小对象夹具；未启动游戏主程序、世界、渲染器或操作已打开的游戏。离线通过不代表本轮新玩法已实测。

部署{deploy['deployed_files']}文件与验证过的冻结候选全树SHA-256一致。当前隔离档{deploy['test_save_files']}文件在部署前后逐SHA-256一致；正式档未写入，所选保护文件与本轮基线一致。PZO／游戏原件、隔离基础模组、配置与名单均保持一致。未上传工坊或推送Git。

发行包：`{OUT / Path(package['archive']).name}`，{package['members']}个文件成员逐SHA-256读回通过；ZIP SHA-256：`{package['archive_sha256']}`。

## 用户优先验收

1. 正常退出后，从桌面原入口重启并继续隔离档；右键门框或底座，确认管理菜单无`$s`残留，四槽百分号和名称正常。
2. 主动领取新版材料包一次；检查新配方材料及电工4／焊接3条件，再由你设置技能或练级。取消一次建造，再完成一门，核对只扣六种材料，三种工具保留、汽车电池未入配方。
3. 旧门继续使用；检查配对、装卸及默认起点扣电2。新建隔离沙盒可分别设耗电0.5和4，核对四满电显示8次和1次，并检查实际起点扣电、接收端不扣电及失败退款。
4. 保存退出重进；在普通视角和Viewpoint中验收外观、菜单和传送。详细步骤见同目录《用户测试步骤.md》。

## 恢复资料

配方更新前代码及交付资料：`{state['archive']}`。

SHA-256：`{state['archive_sha256']}`。恢复此运行快照会回到已包含文字／成本修正、尚未改变配方的中间候选；不需要恢复世界。

本轮文字和耗电改动前的完整旧运行包：`{text_state['archive']}`。

SHA-256：`{text_state['archive_sha256']}`。它对应上一版`0.1.2-lua-test.2`。两者均已逐成员读回，仅为运行文件和交付资料备份，不是新的世界备份。当前存档schema3不变，本轮未写世界，因此没有重复制作大型世界备份。

若回退，先正常退出，再按目标版本仅恢复ZIP中的`mods/SuQingPortals`到隔离`data/mods/SuQingPortals`；不要覆盖正式档，也不要执行旧整档回滚脚本。本轮未执行回退。

完整本轮收据、冻结候选、原生翻译及配方验证日志：`{folder}`。当前机器记录：`{OUT / 'current-test-version.json'}`。源码：`{ROOT}`。

## English

The approved recipe, configurable trip energy and CN/EN formatting fixes are deployed as {deploy['version']} to the existing isolated profile. Each new gate consumes 8 small metal sheets, 4 pipes, 8 wires, 16 electronics scraps, 1 premium camera and 1 handheld walkie-talkie; Electrical 4 and Welding 3 are required. The screwdriver, blowtorch and welding mask are retained without additional fuel use. Car batteries remain separate, four-slot installations. Native building handles requirements and materials; existing gates are preserved.

Trip cost is configurable from 0.5 to 4, default 2, paid entirely at departure. Total charging rate and explicit test tools remain available. In-flight settlement uses its original receipt. Native JSON formatting now receives source %1 tokens correctly, with real loader-plus-Lua regressions. The explicit revised 87-item test kit can be claimed once by old-kit recipients; it never grants automatically or changes skills.

Offline checks passed and the {deploy['test_save_files']}-file current test world, selected personal protection files, PZO/Viewpoint foundation and enable order are unchanged. No portal Java binary, game startup/control, Workshop upload or Git push occurred. Actual building, cancellation, skill gating, new settings and save/reload acceptance remain with the user. The recovery archives above contain code and delivery materials, not new world backups.
'''
(OUT / '交付说明.md').write_text(report, encoding='utf-8')
(folder / '新配方与耗电设置交付.md').write_text(report, encoding='utf-8')
shutil.copy2(ROOT / 'tests/results/offline-validation.json', folder / 'offline-validation.json')
for log in ('core_world', 'client_transfer', 'native_building_localization', 'native_translation_interop_stock', 'native_translation_interop_pzo'):
    shutil.copy2(ROOT / 'tests/results' / (log + '.log'), folder / (log + '.log'))
(folder / 'scope-addendum.json').write_text(json.dumps(dict(final_scope=deploy['scope'],
    includes_previous_text_and_cost_stage=True, recipe_approved_by_user=True, tests=counts, game_started=False,
    gameplay_acceptance='pending_user'), ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(dict(report=str(OUT / '交付说明.md'), checks=counts, version=deploy['version']), ensure_ascii=False))
