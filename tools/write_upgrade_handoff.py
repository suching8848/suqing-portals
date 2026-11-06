"""Write a reviewable handoff from verified receipts; no game actions."""
from pathlib import Path
import json
import shutil
import hashlib

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(r'D:\steam\steamapps\common\ProjectZomboid\CodexAssets\SuQingPortals_20261106')
state = json.loads((ROOT / 'publishing/current-upgrade.json').read_text(encoding='utf-8'))
folder = Path(state['folder'])
deploy = json.loads((folder / 'deployment-receipt.json').read_text(encoding='utf-8'))
validation = json.loads((ROOT / 'tests/results/offline-validation.json').read_text(encoding='utf-8'))
package = json.loads((ROOT / 'publishing/test-package-receipt.json').read_text(encoding='utf-8'))
assert deploy['version'] == validation['version'] == package['version'] == '0.1.1-test.1'
assert deploy['test_save_sha256_unchanged'] and validation['result'] == 'PASS'
assert hashlib.sha256(Path(state['archive']).read_bytes()).hexdigest() == state['archive_sha256']
assert hashlib.sha256((OUT / Path(package['archive']).name).read_bytes()).hexdigest() == package['archive_sha256']
for name in ('offline-validation.json', 'core_world.log', 'client_transfer.log', 'native_battery_codec.log',
             'native_bridge_loader.log', 'native_building_localization.log', 'model_native_readback.log'):
    shutil.copy2(ROOT / 'tests/results' / name, folder / name)
shutil.copy2(ROOT / 'art/model-source/anchor_alignment.png', folder / 'anchor_alignment.png')
shutil.copy2(ROOT / 'art/model-source/anchor_four_facings.png', folder / 'anchor_four_facings.png')
current = OUT / '交付说明.md'
if current.exists():
    shutil.copy2(current, folder / 'previous-handoff.md')
text = f'''# 蘇清的传送门 0.1.1-test.1 隔离测试交付

本轮按用户2026-11-06实测反馈修正，更新的是原隔离实例。桌面「传送门隔离测试」和原入口保持：

`{OUT / 'IsolatedTest/Start-Portal-Test.cmd'}`

隔离档、PZO和其独立用户选项、Viewpoint与基础汉化保留。五项启用名单顺序未改，正式存档未在本轮写入范围内。部署前后当前隔离测试档1151个文件逐SHA-256保持一致；迁移在用户下次加载时由新版执行。

## 本轮变化

- 标准128×256门体图片，统一原生地面锚点，移除旧图顶部多余透明区，保持比例及门坐标。底座、电池仓、门框在离线共同锚点叠加图中完整；四朝向一致。提供16种实际槽位组合、64方向绑定和Viewpoint模型。
- 四个真正专用汽车电池槽，正常新门／迁移成功旧门不挂普通ItemContainer，不出现普通容器栏。原电池身份、耐久、电量、名称和自定义数据经原生完整编码保存。
- 可见门体右键管理及直接装卸；普通视角提供精确alpha命中，透明门洞不扩大为实心点击区。装卸执行邻接可达和定时动作检查。
- 管理窗口包含四槽卡片、耐久和电量条、总电量、可传送次数、当地供电与整门充电速率、配对及禁用原因；底部传送按钮固定。修复中英文本百分号格式异常。
- 旧门保留ID、坐标、名称和配对。迁移使用持久恢复记录，异常时保留原件；原来的出发端2.00等量耗电、目标无需供电、加载且当地有电充电规则保持。

## 已完成的离线检查

统一检查通过：11份Lua编译；CN/EN各145条文本与格式覆盖；后端迁移／存储96项，客户端动作／UI逻辑／点击／传送187项，退休容器钩子8项，原生完整电池保存／容器API17项，现场ZombieBuddy暴露接口4项，原生建造和真实Translator参数350项。模型二进制、几何、mask、alpha、16模型及64绑定原生读回通过，结构检查数不计作玩法断言。

发行ZIP共{package['members']}个成员逐SHA-256读回通过；部署{deploy['deployed_files']}个文件与冻结源全树一致。未启动／操作游戏，也未推送Git或上传工坊。

## 用户优先验收

1. 正常退出当前游戏，从原隔离入口重新启动。若ZombieBuddy首次询问新的`SuQingPortals.jar`组件许可，请在框架对话框中允许；本轮没有替用户修改许可策略。
2. 继续隔离档`2026-11-06_15-46-59`，检查原有门的完整外观、点击和电池迁移；再新建一门检查预览绿框位于底座。
3. 右键门框／底座／电池仓，检查四槽装卸、实际位置外观、百分比和配对；保存重进及往返传送。

真实FBO遮挡、Viewpoint第一／第三人称位置、缩放及点击、保存重进和远区加载仍待用户实测。此版充电尚未计入原生发电机额外油耗。

完整测试步骤：同目录《用户测试步骤.md》。

## 恢复与保护范围

完整隔离档及旧模组快照：`{state['archive']}`。

快照SHA-256：`{state['archive_sha256']}`。包含当前测试世界全部1151文件、旧门运行资源及必要隔离入口配置；每个成员均校验。恢复会退回快照后的测试进度，世界和模组须配套；恢复前另保留当前测试进度，不应用于正式档。

本轮保护核对发现正常用户目录`options.ini`在任务期间与开工基线不同，已按现状保留并单列回执，不归因、不覆盖或回滚。正式档关键文件及其余保护文件匹配开工基线。源游戏、PZO JAR及启动JSON未被本轮修改。

当前版本机器记录：`current-test-version.json`；本轮完整结果与回退收据：`{folder}`。
'''
(folder / '升级交付说明.md').write_text(text, encoding='utf-8')
current.write_text(text, encoding='utf-8')
shutil.copy2(ROOT / 'docs/用户测试步骤.md', OUT / '用户测试步骤.md')
print(json.dumps(dict(version=deploy['version'], handoff=str(current), recovery=str(folder),
    test_save_unchanged=True, game_started=False), ensure_ascii=False))
