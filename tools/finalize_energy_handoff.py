"""Freeze and document the isolated energy candidate without publishing or starting a game."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import hashlib
import json
import shutil
import zipfile
import deploy_energy_upgrade as energy

d = energy.deployment


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    d.stopped()
    state = read(d.STATE)
    validation = read(d.ROOT / 'tests/results/offline-validation.json')
    current = read(d.OUT / 'current-test-version.json')
    package = read(d.ROOT / 'publishing/test-package-receipt.json')
    environment = read(d.OUT / 'current-isa-test-environment.json')
    template = read(d.OUT / 'current-energy-template.json')
    source = d.tree(d.SOURCE)
    if validation['result'] != 'PASS' or validation['version'] != d.VERSION or package['version'] != d.VERSION:
        raise RuntimeError('Final candidate/validation versions differ')
    if source != {'42/' + k: h for k, h in validation['runtime_sha256'].items()} or source != d.tree(d.TARGET) or source != current['runtime_sha256']:
        raise RuntimeError('Source/isolated/validation/current receipt differ')
    if d.tree(Path(state['test_save'])) != state['test_save_before'] or d.protected() != state['formal_before']:
        raise RuntimeError('Original test world or protected personal files changed')
    before, after = state['foundation_before'], d.foundation()
    allowed = str(d.DATA / 'mods/default.txt')
    if {k: v for k, v in before.items() if k != allowed} != {k: v for k, v in after.items() if k != allowed}:
        raise RuntimeError('Original launcher/options/foundation changed')
    if environment['status'] != 'READY_FOR_USER_TEST' or d.sha(d.DATA / 'mods/default.txt') != environment['default_after_sha256']:
        raise RuntimeError('ISA isolated list readback differs')
    for rel, record in environment['destination_manifest'].items():
        if d.sha(Path(environment['destination']) / rel) != record['sha256']:
            raise RuntimeError('Isolated ISA changed: ' + rel)
    archive = d.OUT / Path(package['archive']).name
    if d.sha(archive) != package['archive_sha256']:
        raise RuntimeError('Delivery archive differs')
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read('manifest.json'))
        if z.testzip() is not None:
            raise RuntimeError('Archive CRC failed')
        for name, record in manifest.items():
            if hashlib.sha256(z.read(name)).hexdigest() != record['sha256']:
                raise RuntimeError('Archive member differs: ' + name)
        for rel, value in source.items():
            if hashlib.sha256(z.read('mods/SuQingPortals/' + rel)).hexdigest() != value:
                raise RuntimeError('Packaged runtime differs')
    prep = d.ROOT / 'publishing/EnergyCompat_20261106'
    if prep.exists():
        raise RuntimeError('Frozen energy preparation already exists; inspect instead of overwriting')
    stage = prep / 'staging/content/mods/SuQingPortals'
    shutil.copytree(d.SOURCE, stage)
    if d.tree(stage) != source:
        raise RuntimeError('Staging readback differs')
    shutil.copy2(d.SOURCE / '42/poster.png', prep / 'preview.png')
    shutil.copy2(d.ROOT / 'docs/供电兼容说明.md', d.OUT / '供电兼容说明.md')
    shutil.copy2(d.ROOT / 'docs/用户测试步骤.md', d.OUT / '用户测试步骤.md')
    identity = read(d.ROOT / 'publishing/workshop-item.json')
    now = datetime.now(timezone(timedelta(hours=8))).isoformat()
    receipt = dict(version=d.VERSION, verified_at=now, status='ISOLATED_TEST_READY_GAMEPLAY_PENDING',
        source=str(d.SOURCE), isolated_runtime=str(d.TARGET), staging=str(stage), runtime_files=len(source),
        source_isolated_staging_package_hash_equal=True, validation=validation,
        original_test_save=state['test_save'], original_test_save_files=len(state['test_save_before']), original_test_save_unchanged=True,
        enabled=environment['expected_enabled'], isa_copy_sha256_verified=True, isa_version='1.2.15',
        isa_environment_receipt=str(d.OUT / 'current-isa-test-environment.json'),
        template=template, current_workshop_item=identity['publishedfileid'], existing_workshop_state=identity['state'],
        this_candidate_uploaded=False, git_commit_created=False, git_pushed=False, game_started=False,
        gameplay_acceptance='pending_user', selected_cover='C', recover_runtime=state['archive'],
        recover_default=environment['original_default'], archive=str(archive), archive_sha256=package['archive_sha256'])
    write(prep / 'candidate.json', receipt)
    write(d.OUT / 'handoff-verification.json', receipt)
    write(Path(state['folder']) / 'final-energy-handoff.json', receipt)
    report = f'''# 蘇清的传送门：供电兼容与停电模板交付

时间：{now}（北京时间）。当前隔离候选 **{d.VERSION}**；完整离线检查通过，游戏内验收由用户完成。

本轮新增按实际成功充入量独立结算燃油或ISA储能、单一覆盖来源选择、发电机面板额外负载/合计和太阳能来源提示。无电池、满电、损坏、锁定、卸载或充电失败不收取本门额外消费。实际能源不足时限量充电；失败回滚未能确认时暂停该门操作并保留日志。

原生汽车电池充电器等价成本为每满电等量0.3升，再乘GeneratorFuelConsumption。默认倍率0.1、门速率0.5时，额外0.015升/游戏小时，不含原生发电机自身及其他电器消耗。ISA仅支持当前1.2.15/3781944805，未知版本或ISA-Fix冲突安全拒绝太阳能充电；两种DrainCalc都按实际储能结算，未重复加入原生total或ISA drain。面板包装不是Java原生设备注册；BGI剩余时间估算不包含独立消费。

原配方、0.5～4传送耗电设置、schema3四槽存储、C「雨夜归途」和原入口保留。隔离名单为{', '.join(environment['expected_enabled'])}；只追加ISA，原五项相对顺序保持。TargetSquareOnLoad对本轮供电测试不是必需，未加入。

## 用户测试入口

继续用桌面「传送门隔离测试」，或 `{d.ISO / 'Start-Portal-Test.cmd'}`。在加载存档菜单选择新Energy_Template世界，精确目录和断电核验见 `{d.OUT / 'current-energy-template.json'}`。模板从原隔离世界派生，继承其已有角色、物品和地图，不是空白新世界；没有启动游戏、创建作弊角色或预摆发电机/太阳能设备。原隔离档{len(state['test_save_before'])}文件SHA-256不变。

测试按同目录《用户测试步骤.md》：先确认无市电；空/满电池免扣；接普通发电机比较门电量、真实燃油升数与时间；再单独开启ISA储能系统比较门电量和银行储能；最后检查关闭、耗尽、重叠来源和保存重进。实际加载ISA仍需用户首次启动后日志确认，离线启用名单不能代替加载证据。

## 离线验证与产物

完整记录：`{d.ROOT / 'tests/results/offline-validation.json'}`。新增原生API、充电结算、面板、ISA模拟及真实ISA上游互操作检查均通过，旧配方、翻译、模型、拾取和原电池持久化回归也通过。模板及ISA环境另有独立原生格式/名单校验收据，均未执行游戏主程序或世界。

源码、隔离目录、staging和ZIP的{len(source)}个运行文件逐SHA-256相同。测试包 `{archive}`，SHA-256 `{package['archive_sha256']}`。本地新候选资料 `{prep}`。

正式档与配置未写入。已有私有工坊条目{identity['publishedfileid']}及旧冻结包保留，本轮0.1.4未上传；没有提交或推送Git。

## 恢复范围

上一版运行包和交付资料：`{state['archive']}`，SHA-256 `{state['archive_sha256']}`。只恢复隔离模组运行文件会回到0.1.3；不回滚世界。隔离默认名单原始字节副本：`{environment['original_default']}`，是否恢复由用户决定；原测试世界未修改。不要用旧整档脚本覆盖正式世界或现有进度。

## English

The {d.VERSION} isolated candidate passed offline regression, including actual installed ISA power-bank methods. Fuel or solar energy is settled only for successfully stored portal charge; no native load-total or ISA-drain double billing is introduced. The existing isolated world is preserved, and a separate power-off template plus ISA test environment are prepared for user-operated acceptance. Default additional gas cost is 0.015 L/game hour at charge rate0.5 and fuel multiplier0.1. Vehicles/multiplayer remain unsupported. Current ISA support is1.2.15; unsupported versions fail closed. Existing private Workshop identity and frozen release remain unchanged; this new candidate was not uploaded and no Git commit/push or game startup occurred.
'''
    (d.OUT / '交付说明.md').write_text(report, encoding='utf-8')
    (prep / '交付说明.md').write_text(report, encoding='utf-8')
    print(json.dumps(dict(version=d.VERSION, runtime_files=len(source), template=template.get('destination'),
        enabled=environment['expected_enabled'], report=str(d.OUT / '交付说明.md'), uploaded=False), ensure_ascii=False))


if __name__ == '__main__':
    main()
