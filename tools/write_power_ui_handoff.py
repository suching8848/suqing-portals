"""Verify and document the completed local power/UI candidate; never starts a game."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
import shutil
import zipfile

from deploy_power_ui_upgrade import deployment as deploy


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root, out = deploy.ROOT, deploy.OUT
    prep = root / "publishing/ReleasePrep_20261106"
    state = read(deploy.STATE)
    folder = Path(state["folder"])
    deployed = read(out / "current-test-version.json")
    validation_path = root / "tests/results/offline-validation.json"
    validation = read(validation_path)
    package = read(root / "publishing/test-package-receipt.json")
    release = read(prep / "release-candidate.json")
    version = deploy.VERSION
    if any(x["version"] != version for x in (state, deployed, validation, package, release)):
        raise RuntimeError("Delivery versions differ")
    deploy.stopped()
    source = deploy.tree(deploy.SOURCE)
    staged = prep / "staging/content/mods/SuQingPortals"
    if source != deploy.tree(deploy.TARGET) or source != deploy.tree(staged):
        raise RuntimeError("Source, isolated deployment or staging differ")
    if source != {"42/" + k: v for k, v in validation["runtime_sha256"].items()}:
        raise RuntimeError("Runtime differs from the successful recorded validation")
    if validation["result"] != "PASS" or not package["every_member_sha256_verified"]:
        raise RuntimeError("Successful checks are missing")
    if any(c.get("exit_code", 0) != 0 or c.get("result", "PASS") != "PASS"
           for c in validation["checks"].values()):
        raise RuntimeError("Unsuccessful check in validation record")
    if deploy.protected() != state["formal_before"] or deploy.foundation() != state["foundation_before"]:
        raise RuntimeError("Protected files or retained foundation changed")
    if deploy.tree(Path(state["test_save"])) != state["test_save_before"]:
        raise RuntimeError("Test-world progress changed")
    archive = out / Path(package["archive"]).name
    if digest(archive) != package["archive_sha256"]:
        raise RuntimeError("Delivery archive differs")
    with zipfile.ZipFile(archive) as bundle:
        manifest = json.loads(bundle.read("manifest.json"))
        if bundle.testzip() is not None or set(bundle.namelist()) != set(manifest) | {"manifest.json"}:
            raise RuntimeError("Archive member set or CRC differs")
        for name, record in manifest.items():
            data = bundle.read(name)
            if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
                raise RuntimeError("Archive member differs: " + name)
        for rel, expected in source.items():
            if hashlib.sha256(bundle.read("mods/SuQingPortals/" + rel)).hexdigest() != expected:
                raise RuntimeError("Packaged runtime differs: " + rel)
    exports = read(prep / "art/exports.json")
    for name, record in exports["exports"].items():
        if digest(prep / name) != record["sha256"]:
            raise RuntimeError("Art export differs: " + name)
    selection_path = prep / "art/selection.json"
    selection = read(selection_path) if selection_path.is_file() else None
    selected_variant = selection.get("selected_variant") if selection else None
    if selection:
        if not isinstance(selected_variant, str) or selected_variant not in ("A", "B", "C", "D") or selection.get("user_selection") != selected_variant:
            raise RuntimeError("Invalid or unconfirmed cover selection")
        if selection.get("source_master") != "art/masters/" + selected_variant + ".png":
            raise RuntimeError("Selected master differs from the chosen variant")
        for path_key, hash_key in (("source_master", "source_master_sha256"),
                                   ("selected_poster", "selected_poster_sha256"),
                                   ("selected_cover", "selected_cover_sha256")):
            asset = (prep / selection[path_key]).resolve()
            if not asset.is_relative_to(prep.resolve()) or not asset.is_file() or digest(asset) != selection.get(hash_key):
                raise RuntimeError("Selected artwork differs: " + path_key)
        if digest(deploy.SOURCE / "42/poster.png") != selection["selected_poster_sha256"]:
            raise RuntimeError("Runtime poster does not match the selected export")
        if release["art"]["cover"]["status"] != "SELECTED_APPLIED":
            raise RuntimeError("Release preparation has not recorded the applied selection")
    if release["published"] or release["upload_attempted"] or release["art"]["cover"]["selected_variant"] != selected_variant:
        raise RuntimeError("Unexpected publication or art-selection mismatch")
    cover_status = ("封面已按用户选择定稿为" + selected_variant + "「雨夜归途」，poster已应用到源码、隔离版和发布候选；独立icon未替换。"
                    if selected_variant == "C" else
                    "封面已按用户选择定稿为" + selected_variant + "，poster已应用到源码、隔离版和发布候选；独立icon未替换。"
                    if selection else "封面等待用户选择，运行包保留既有测试图。")
    cover_next = ("用户选定封面与导出见 `" + str(prep / selection["selected_cover"]) + "`，选稿和哈希见 `" + str(selection_path) + "`。"
                  if selection else "封面查看 `" + str(prep / "art/四版封面对比.png") + "` 或 `" + str(prep / "封面候选.html") + "`，选择A／B／C／D后再沿该稿定稿。")
    cover_english = ("The user selected cover " + selected_variant + "; its poster export is applied to source, isolated runtime and staging. The independent icon remains generated and pending user review, with no runtime icon replacement."
                     if selection else "Four illustrated cover candidates and an independently generated transparent icon are ready for review; none was selected or promoted into runtime artwork.")
    counts = {}
    for name, check in validation["checks"].items():
        if "log" in check:
            text = Path(check["log"]).read_text(encoding="utf-8", errors="replace")
            match = re.search(r"checks=(\d+) failures=0|assertions passed: (\d+)", text)
            if match:
                counts[name] = int(match[1] or match[2])
    now = datetime.now(timezone(timedelta(hours=8))).isoformat()
    receipt = dict(version=version, verified_at=now, status="LOCAL_DELIVERY_COMPLETE_PENDING_USER_ACCEPTANCE",
        source=str(deploy.SOURCE), isolated_runtime=str(deploy.TARGET), staging=str(staged),
        source_equals_isolated_equals_staging_equals_package=True, runtime_files=len(source),
        offline_validation_matches_source=True, offline_validation_result="PASS",
        validation_sha256=digest(validation_path), offline_tests_rerun_during_handoff=False,
        checks=counts, translation_keys_per_language=validation["checks"]["localization"]["keys_per_language"],
        current_test_save=state["test_save"], test_save_files=len(state["test_save_before"]),
        test_save_hashes_unchanged=True, formal_protected_files_unchanged=True, retained_foundation_unchanged=True,
        package=str(archive), package_sha256=package["archive_sha256"], all_archive_members_verified=True,
        cover_selection=selected_variant, cover_selection_record=str(selection_path) if selection else None,
        cover_variants=["A", "B", "C", "D"],
        icon_status="generated_independently_pending_user_review", runtime_art_replaced=bool(selection),
        runtime_poster_replaced=bool(selection), runtime_icon_replaced=False,
        artwork_only_update=validation.get("artwork_only_update"),
        launch_entry=str(deploy.ISO / "Start-Portal-Test.cmd"),
        desktop_shortcut=r"C:\Users\15792\Desktop\传送门隔离测试.lnk",
        recovery_archive=state["archive"], recovery_archive_sha256=state["archive_sha256"],
        game_started=False, saves_written=False, workshop_uploaded=False, git_committed=False, git_pushed=False,
        gameplay_acceptance="pending_user", publication_authorized=False)
    previous = out / "handoff-verification.json"
    historical = folder / "handoff-before-finalization.json"
    if previous.exists() and not historical.exists():
        shutil.copy2(previous, historical)
    encoded = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    previous.write_text(encoded, encoding="utf-8")
    (folder / "final-handoff-verification.json").write_text(encoded, encoding="utf-8")
    report = f"""# 蘇清的传送门 {version}：隔离版与发布材料交付

完成核对时间：{now}（北京时间）。本轮代码、隔离部署、测试包及发布草稿已完成；未上传或发布。{cover_status}最新功能等待用户游戏内验收。

## 本轮完成

- 管理界面突出显示电源连接、可识别的市电／发电机来源与充电状态。无法可靠识别来源时显示区域供电／来源未确认；满电、无电池、损坏、缺电或事务锁定分别提示。
- 管理窗口可缩放，电池槽为紧凑2×2布局，传送按钮固定底部。普通1366×768、1920×1080及字体尺寸的模拟布局已有回归；小窗口或大字体允许必要滚动。真实显示仍待用户验收。
- 彻底移除右键领取材料入口、发放代码及沙盒测试开关。旧档残留 DebugTools=true 也不会发物品；旧人物已有物品与历史字段保留。本轮此前只从隔离预设移除了该开关，未改写 map_sand.bin。
- 保留原生新配方、0.5～4单次耗电（默认2）、整门0.05～4充电速率（默认0.5）和schema3四槽保存格式。起点承担全部传送耗电，终点无需电池或当地供电。
- A「工坊初启」、B「跨门归来」、C「雨夜归途」、D「双门远行」四版封面，以及独立透明icon的32／64／128／256导出均已完成。母版、提示词与来源在 `{prep / 'art'}`。{cover_status}
- 中英工坊介绍、短介绍与更新说明在 `{prep / 'text'}`；本地发布核对清单在 `{prep / '发布核对清单.md'}`。尚未创建工坊物品或上传任务。

## 当前文件与校验

源码：`{root}`。

隔离运行模组：`{deploy.TARGET}`。

发布候选：`{staged}`。源码、隔离部署、staging及ZIP运行内容共{len(source)}文件，逐文件SHA-256一致。最新离线记录与当前源码及游戏JAR核对一致，复用已通过的功能检查记录，没有为封面导出重复运行全套功能测试；美术替换的范围及哈希另记于离线记录的 artwork_only_update。

离线记录：`{validation_path}`。CN/EN各{validation['checks']['localization']['keys_per_language']}键；后端{counts.get('core_world')}项、客户端／动作／界面{counts.get('client_transfer')}项。其他配方、翻译、容器、电池持久化、拾取、模型与隔离预设检查均通过；完整分类见同目录JSON收据。独立解释器、mock和原生解析不等于游戏内验收。

测试包：`{archive}`。

ZIP SHA-256：`{package['archive_sha256']}`。{package['members']}个内容成员及manifest已读回核对。

当前隔离档：`{state['test_save']}`，{len(state['test_save_before'])}个文件部署前后SHA-256不变。正式档未写入，所选正式配置、名单、沙盒文件、游戏/PZO及隔离基础模组哈希与本轮基线一致；保留原名单顺序、PZO和Viewpoint。未启动或操作游戏，未提交或推送Git。

## 用户下一步

继续使用桌面「传送门隔离测试」或 `{deploy.ISO / 'Start-Portal-Test.cmd'}`。加载原隔离档后优先检查：电源／充电提示；拖动缩放且按钮不遮挡；地面和门体均无领取入口；保存重进后四槽、名称与配对正常。详细步骤：`{out / '用户测试步骤.md'}`。

{cover_next}当前候选仅支持B42.21单人角色和随身物品，不支持车辆、拖挂或联机；充电尚未增加独立发电机油耗。

## 恢复资料

已核验的上一版运行包和交付文件：`{state['archive']}`。

SHA-256：`{state['archive_sha256']}`。它是运行文件恢复材料，不是本轮新增世界备份。需要回退时先正常退出，只恢复其中 `mods/SuQingPortals` 到上述隔离运行目录；不要恢复正式档或执行旧整档回滚脚本。旧隔离预设副本及移除记录在同目录 `previous-test-preset.cfg`、`test-preset-removal.json`。本轮没有执行回退。

最终收据：`{out / 'handoff-verification.json'}`。

## English

The {version} local candidate is deployed to the existing isolated profile, packaged and hash-verified against source and staging. Visible power/source/charging states, resizable compact management and complete mod item-giver removal are implemented. The existing recipe, configurable departure-only cost, charging rate and schema3 battery storage are retained. Legacy test-tool flags cannot grant supplies.

{cover_english} Bilingual listing and update drafts are prepared. Recorded offline validation matches the current runtime; existing functional results are reused and the artwork-only hash update is recorded separately. Actual gameplay acceptance remains with the user. The {len(state['test_save_before'])}-file isolated save and selected personal/foundation files remain unchanged. No game launch/control, save edit, Workshop upload, Git commit or push occurred. Single-player characters only; vehicles and multiplayer remain unsupported. Charging has no separate generator fuel load yet.
"""
    (out / "交付说明.md").write_text(report, encoding="utf-8")
    (folder / "电源界面与发布材料交付.md").write_text(report, encoding="utf-8")
    shutil.copy2(validation_path, folder / "offline-validation.json")
    for name in ("core_world", "client_transfer", "native_building_localization", "isolated_native_preset"):
        shutil.copy2(root / "tests/results" / (name + ".log"), folder / (name + ".log"))
    print(json.dumps(dict(version=version, report=str(out / "交付说明.md"),
        verified_runtime_files=len(source), test_save_files=receipt["test_save_files"],
        archive_members=package["members"], published=False), ensure_ascii=False))


if __name__ == "__main__":
    main()
