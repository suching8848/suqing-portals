"""Report the verified right-click hotfix without claiming gameplay acceptance."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import json
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(r'D:\steam\steamapps\common\ProjectZomboid\CodexAssets\SuQingPortals_20261106')
state = json.loads((ROOT / 'publishing/picker-hotfix-state.json').read_text(encoding='utf-8'))
folder = Path(state['folder'])
deploy = json.loads((folder / 'deployment-receipt.json').read_text(encoding='utf-8'))
validation = json.loads((ROOT / 'tests/results/offline-validation.json').read_text(encoding='utf-8'))
package = json.loads((ROOT / 'publishing/test-package-receipt.json').read_text(encoding='utf-8'))
if not (deploy['version'] == validation['version'] == package['version'] == '0.1.2-lua-test.2'):
    raise RuntimeError('Delivery versions differ')
if validation['result'] != 'PASS' or not deploy['foundation_unchanged'] or not package['every_member_sha256_verified']:
    raise RuntimeError('Missing successful validation/deployment check')


def checks(name, pattern=r'checks=(\d+) failures=0'):
    text = (ROOT / 'tests/results' / (name + '.log')).read_text(encoding='utf-8')
    return int(re.search(pattern, text)[1])


counts = dict(backend=checks('core_world', r'assertions passed: (\d+)'), client=checks('client_transfer'),
    guard=checks('inventory_guard'), picker_stock=checks('native_picker_interop_stock'),
    picker_pzo=checks('native_picker_interop_pzo'))
text = f'''# 蘇清的传送门 {deploy['version']} 右键修复

时间：{datetime.now(timezone(timedelta(hours=8))).isoformat()}。

已更新原隔离实例，继续使用桌面「传送门隔离测试」。

## 原因与修改

用户日志确认`Client.lua:87`报`attempted index: tile of non-table: zombie.iso.IsoObjectPicker$ClickObject`。原代码将`ContextPick()`返回的Java对象当作Lua表读取`.tile`；普通Lua表测试替身没能捕获这一接口差异。

现改用当前原版Lua已采用的`PickThumpable(x,y)`，直接返回门的`IsoObject`；不读取未暴露字段，不臆造getter，也不通过捕获异常跳过错误。保持原屏幕坐标、透明门洞过滤、普通视角精确alpha命中及Viewpoint原生命中路径。

仅改了{len(deploy['changed_files'])}个运行文件：Client.lua、Core版本标记及mod.info。电池保存格式仍为schema3，四槽、绑定、起点单次2.00等量耗电及充电规则不变。传送门仍是纯Lua，没有新增产品JAR／Java许可；PZO、Viewpoint及汉化保留。

## 验证与当前状态

统一离线检查通过：后端{counts['backend']}项、客户端{counts['client']}项、普通容器入口{counts['guard']}项；真实Kahlua／Java对象交互在原版类路径{counts['picker_stock']}项、PZO类路径{counts['picker_pzo']}项通过。交互夹具复现旧字段访问错误，并运行修正后的产品源码检查直接对象返回；不测真实屏幕拾取、渲染或世界。完整编译、双语、模型解析及原生电池保存检查亦通过。

已部署{deploy['deployed_files']}文件与冻结候选全树SHA-256一致。当前测试档{deploy['test_save_files']}个文件在本轮部署前后逐SHA-256一致；正式存档未写入，选定保护文件核对结果：{deploy['formal_protected_unchanged']}。隔离入口、PZO、Viewpoint、汉化和启用名单均保持一致。未启动／操作游戏，未上传工坊或推送Git。游戏内右键菜单及Viewpoint效果仍待用户验收。

发行包：`{OUT / Path(package['archive']).name}`，{package['members']}个文件成员逐SHA-256读回通过；ZIP SHA-256：`{package['archive_sha256']}`。

## 用户验收

1. 正常退出游戏后，从桌面原入口重启，继续`2026-11-06_15-46-59`测试档。
2. 右键门框、底座及电池仓，确认出现管理／装卸菜单且不再弹出该异常。再检查普通地面及其他物件右键正常。
3. 打开管理界面检查四槽和配对，并分别在普通视角与Viewpoint检查右键命中。

无需重建世界或传送门。完整步骤：同目录《用户测试步骤.md》。

## 恢复

本轮代码及交付资料备份：`{state['archive']}`。

SHA-256：`{state['archive_sha256']}`，{state['archive_members']}个文件成员逐SHA-256读回通过。它仅包含上一版运行文件及交付资料，不是世界备份。本轮不写存档、不改保存格式，未重复制作大型世界备份；现有完整世界历史快照继续保留。

如需回退，正常退出隔离游戏后，仅将ZIP的`mods/SuQingPortals`恢复到隔离`data/mods/SuQingPortals`，无需恢复世界。当前进度采用同一schema3。不要运行旧版整档回滚或覆盖正式档。本轮未执行回退。

当前机器记录：`{OUT / 'current-test-version.json'}`；错误原始日志、存档校验清单、代码快照、离线检查与部署回执：`{folder}`。

## English

The right-click fix is deployed to the existing isolated profile. `ContextPick()` returned an opaque Java `ClickObject`; indexing its `.tile` field as a Lua table caused the reported exception. The patch uses the native `PickThumpable(x,y)` method to obtain an `IsoObject` directly. Real Kahlua/Java interop fixtures reproduce the old failure and validate the corrected product Lua; they do not run the screen picker, renderer, world or game.

Only the picker code and two version markers changed. Battery schema3 and gameplay are unchanged. PZO, Viewpoint, translations, enable order and current progress are preserved, with no portal Java binary. Restart the desktop isolated entry and right-click an existing gate to verify the menu in both normal and Viewpoint views. Gameplay acceptance remains pending. The recovery ZIP above contains the previous code and delivery materials, not a world backup; a code-only rollback does not require restoring the world.
'''
(OUT / '交付说明.md').write_text(text, encoding='utf-8')
(folder / '右键修复结果.md').write_text(text, encoding='utf-8')
shutil.copy2(ROOT / 'tests/results/offline-validation.json', folder / 'offline-validation.json')
for name in ('client_transfer', 'native_picker_interop_stock', 'native_picker_interop_pzo'):
    shutil.copy2(ROOT / 'tests/results' / (name + '.log'), folder / (name + '.log'))
print(json.dumps(dict(report=str(OUT / '交付说明.md'), counts=counts, game_started=False), ensure_ascii=False))
