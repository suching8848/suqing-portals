"""Refresh local release-preparation files from an exactly validated test build.

This script has no upload, Git, Workshop, game-start or deployment capability.
It only reads the source, isolated runtime and validation record, then writes
inside publishing/ReleasePrep_20261106. Artwork is recorded, never selected or
copied into runtime assets here. Historical staging and receipts are retained.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mods/SuQingPortals"
PREP = ROOT / "publishing/ReleasePrep_20261106"
VALIDATION = ROOT / "tests/results/offline-validation.json"
ISOLATED = Path(r"D:\steam\steamapps\common\ProjectZomboid\CodexAssets\SuQingPortals_20261106\IsolatedTest\data\mods\SuQingPortals")
LOCAL_FILES = (
    "release-candidate.json", "read-only-audit.json", "runtime-files.json",
    "runtime-files.sha256", "art-files.json", "发布核对清单.md",
)
TEXT_SUFFIXES = {".txt", ".lua", ".json", ".md", ".bbcode", ".info", ".properties", ".mtl", ".obj"}
PATH_PATTERN = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/]|\\\\[^\\\s]+\\")
REQUIRED_CHECKS = (
    "pure_lua_runtime", "kahlua_compile", "localization", "core_world",
    "client_transfer", "inventory_guard", "native_building_localization",
    "isolated_native_preset",
)


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def inventory(folder):
    if not folder.is_dir():
        raise RuntimeError("Missing directory: " + str(folder))
    files = []
    for file in sorted(folder.rglob("*")):
        if file.is_symlink() or (hasattr(file, "is_junction") and file.is_junction()):
            raise RuntimeError("Linked paths are not accepted in the candidate: " + str(file))
        if file.is_file():
            files.append(dict(path=file.relative_to(folder).as_posix(), bytes=file.stat().st_size, sha256=sha(file)))
    if not files:
        raise RuntimeError("Empty candidate: " + str(folder))
    return files


def hashes(files):
    return {entry["path"]: entry["sha256"] for entry in files}


def local_destination(path):
    resolved = path.resolve()
    if not resolved.is_relative_to(PREP.resolve()) or resolved == PREP.resolve():
        raise RuntimeError("Destination escapes the release-preparation directory: " + str(path))
    return path


def write_json(path, value):
    local_destination(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def audit_text(folder):
    found = []
    for file in folder.rglob("*"):
        if file.is_file() and file.suffix.lower() in TEXT_SUFFIXES:
            content = file.read_text(encoding="utf-8-sig")
            for line, text in enumerate(content.splitlines(), 1):
                if PATH_PATTERN.search(text):
                    found.append(dict(path=file.relative_to(folder).as_posix(), line=line))
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="Read-only preflight; no local staging or receipts are changed")
    args = parser.parse_args()
    validation_bytes = VALIDATION.read_bytes()
    validation = json.loads(validation_bytes)
    if validation.get("result") != "PASS":
        raise RuntimeError("No successful offline validation record")
    for name in REQUIRED_CHECKS:
        check = validation.get("checks", {}).get(name)
        if not check or check.get("exit_code", 0) != 0 or check.get("result", "PASS") != "PASS":
            raise RuntimeError("Missing or unsuccessful final check: " + name)
    for name, check in validation.get("checks", {}).items():
        if check.get("exit_code", 0) != 0 or check.get("result", "PASS") != "PASS":
            raise RuntimeError("Validation record contains an unsuccessful check: " + name)
    source = inventory(SOURCE)
    runtime = inventory(SOURCE / "42")
    isolated = inventory(ISOLATED)
    if hashes(runtime) != validation.get("runtime_sha256"):
        raise RuntimeError("Source runtime has changed since the successful offline validation; do not refresh staging yet")
    if source != isolated:
        raise RuntimeError("Isolated runtime does not match source; finish isolated deployment before refreshing staging")
    info = (SOURCE / "42/mod.info").read_text(encoding="utf-8-sig")
    version = re.search(r"^modversion=(.+)$", info, re.M)[1].strip()
    core = (SOURCE / "42/media/lua/shared/SuQingPortals/Core.lua").read_text(encoding="utf-8-sig")
    if re.search(r'Core.VERSION\s*=\s*"([^"]+)"', core)[1] != version or version != validation.get("version"):
        raise RuntimeError("Version mismatch between source metadata, logic and validation")
    if "test" not in version.lower():
        raise RuntimeError("This preparation flow must retain a test-candidate version; no stable release is authorized")
    if any(Path(entry["path"]).suffix.lower() in {".jar", ".class", ".dll", ".so", ".dylib"} for entry in source):
        raise RuntimeError("Unexpected runtime binary in the pure-Lua candidate")
    leaks = audit_text(SOURCE)
    # Publishing prose stays outside content, but must also be safe to reuse.
    prose_leaks = audit_text(PREP / "text") if (PREP / "text").is_dir() else []
    if leaks or prose_leaks:
        raise RuntimeError("Machine-path text must be reviewed before preparing external materials: " + repr(leaks + prose_leaks))
    art = inventory(PREP / "art") if (PREP / "art").is_dir() else []
    exports = json.loads((PREP / "art/exports.json").read_text(encoding="utf-8"))
    cover_variants = {variant: "art/exports/" + variant + "-1024.png" for variant in "ABCD"}
    icon_exports = ["art/exports/icon-" + str(size) + ".png" for size in (32, 64, 128, 256)]
    for relative in list(cover_variants.values()) + icon_exports:
        asset = local_destination(PREP / relative)
        expected = exports.get("exports", {}).get(relative)
        if not asset.is_file() or not expected or sha(asset) != expected.get("sha256"):
            raise RuntimeError("Missing or changed artwork export: " + relative)
    for relative in (exports["comparison"], exports["icon_actual_sizes"]):
        if not local_destination(PREP / relative).is_file():
            raise RuntimeError("Missing artwork review sheet: " + relative)
    if not exports.get("icon_independently_generated") or exports.get("runtime_art_replaced"):
        raise RuntimeError("Artwork record no longer describes unselected independent candidates")
    selection_path = PREP / "art/selection.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8")) if selection_path.is_file() else None
    selected_variant = selection.get("selected_variant") if selection else None
    if selection:
        if not isinstance(selected_variant, str) or selected_variant not in ("A", "B", "C", "D") or selection.get("user_selection") != selected_variant:
            raise RuntimeError("Invalid or unconfirmed cover selection")
        if selection.get("source_master") != "art/masters/" + selected_variant + ".png":
            raise RuntimeError("Selected cover master differs from the chosen variant")
        for path_key, hash_key in (("source_master", "source_master_sha256"),
                                   ("selected_poster", "selected_poster_sha256"),
                                   ("selected_cover", "selected_cover_sha256")):
            asset = local_destination(PREP / selection[path_key])
            if not asset.is_file() or sha(asset) != selection.get(hash_key):
                raise RuntimeError("Selected artwork is missing or changed: " + path_key)
        if sha(SOURCE / "42/poster.png") != selection["selected_poster_sha256"]:
            raise RuntimeError("Runtime poster does not match the selected cover export")
    if args.check_only:
        print(json.dumps(dict(status="PREFLIGHT_MATCH", version=version, runtime_files=len(source), art_files=len(art), writes=False), ensure_ascii=False))
        return

    # A unique temporary stage lets all copy/readback work finish before any
    # previous local candidate is moved. No existing user art is overwritten.
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M%S_%f")
    prepared_at = datetime.now(timezone(timedelta(hours=8))).isoformat()
    temporary = local_destination(PREP / ("staging.pending-" + stamp))
    candidate = temporary / "content/mods/SuQingPortals"
    shutil.copytree(SOURCE, candidate)
    if inventory(candidate) != source:
        raise RuntimeError("Staging copy readback differs; previous staging was preserved")
    if inventory(SOURCE) != source or inventory(ISOLATED) != isolated or VALIDATION.read_bytes() != validation_bytes:
        raise RuntimeError("Source, isolated runtime or validation changed during refresh; previous staging was preserved")
    (temporary / "README-NOT-FOR-UPLOAD.txt").write_text(
        ("LOCAL TEST CANDIDATE ONLY. Cover " + selected_variant + " selected and applied; gameplay acceptance is pending.\n"
         if selection else "LOCAL TEST CANDIDATE ONLY. Cover choice and current gameplay acceptance are pending.\n") +
        "No Workshop item, upload task or publication is created by this directory.\n"
        "Only content/ is the proposed runtime-content root. Keep audit files outside it.\n", encoding="utf-8")
    history = local_destination(PREP / "history" / stamp)
    history.mkdir(parents=True)
    staging = local_destination(PREP / "staging")
    if staging.exists():
        shutil.move(str(staging), str(local_destination(history / "staging")))
    for name in LOCAL_FILES:
        old = local_destination(PREP / name)
        if old.exists():
            shutil.move(str(old), str(local_destination(history / name)))
    shutil.move(str(temporary), str(staging))
    if inventory(staging / "content/mods/SuQingPortals") != source:
        raise RuntimeError("Final staging readback differs; retained history is available")

    manifest = dict(scope="staging/content/mods/SuQingPortals only; relative paths", algorithm="SHA-256", files=source)
    write_json(PREP / "runtime-files.json", manifest)
    (PREP / "runtime-files.sha256").write_text("".join(x["sha256"] + "  " + x["path"] + "\n" for x in source), encoding="utf-8")
    write_json(PREP / "art-files.json", dict(status="SELECTED_COVER_APPLIED" if selection else "UNSELECTED_LOCAL_ART_CANDIDATES", selected_variant=selected_variant, algorithm="SHA-256", files=art,
        runtime_art_replaced_by_this_refresh=False, scope="art/ only; original private references are not copied into content"))
    check_records = {}
    for name, check in validation["checks"].items():
        recorded = dict(check)
        if check.get("log"):
            log = Path(check["log"])
            recorded["log_exists"] = log.is_file()
            if log.is_file():
                recorded["log_sha256"] = sha(log)
                recorded["summary"] = [line for line in log.read_text(encoding="utf-8", errors="replace").splitlines()
                                       if any(token in line for token in ("checks=", "PASS", "assertions passed"))][-6:]
        check_records[name] = recorded
    audit = dict(audited_at=prepared_at,
        scope="Local source/isolated/staging hash audit and recorded offline-validation readback; no new tests or game startup by this script",
        source=str(SOURCE), isolated_runtime=str(ISOLATED), source_equals_isolated=True, source_equals_staging=True,
        source_equals_recorded_validation_hashes=True,
        validation_record=dict(path=str(VALIDATION), sha256=hashlib.sha256(validation_bytes).hexdigest(), version=version,
            result="PASS", scope=validation.get("scope"), checks=check_records),
        private_absolute_paths_in_distributable_text=leaks, private_absolute_paths_in_publishing_prose=prose_leaks,
        preserved_history=str(history), game_started=False, runtime_edited=False, workshop_uploaded=False,
        git_remote_changed=False, personal_config_or_saves_edited=False,
        excluded_from_external_content=["Local audit/checklist/manifests", "tools/tests/logs", "historical backups", "private character reference images", "other mods and loaders", "saves and personal configuration"])
    write_json(PREP / "read-only-audit.json", audit)
    release = dict(prepared_at=prepared_at, status="LOCAL_STAGING_DRAFT_NOT_PUBLISHED", published=False, upload_attempted=False,
        release_ready=False, stable_accepted=False, mod_id="SuQingPortals", display_name="SuQing's Portals", display_name_zh="蘇清的传送门",
        version=version, schema=3, version_changed_for_publication=False,
        supported_game_metadata={key: re.search(r"^" + key + r"=(.+)$", info, re.M)[1].strip() for key in ("versionMin", "versionMax")},
        scope="single-player characters; vehicle/multiplayer transport excluded",
        dependencies=dict(required_portal_java=False, required_zombiebuddy=False, optional_viewpoint=True, loadModAfter="Viewpoint"),
        candidate_content_root="staging/content", mod_root="staging/content/mods/SuQingPortals",
        file_count=len(source), total_bytes=sum(x["bytes"] for x in source), source_isolated_and_staging_hash_equal=True,
        recorded_offline_validation_matches=True, offline_validation_result="PASS", offline_tests_rerun_during_preparation=False,
        gameplay_acceptance=dict(current_candidate_fully_accepted=False, status="Latest power display/resizing/item-giver removal awaits user in-game acceptance; offline PASS does not establish stable acceptance"),
        art=dict(cover=dict(status="SELECTED_APPLIED" if selection else "GENERATED_UNSELECTED", selected_variant=selected_variant, variant_count_requested=4,
                selection_record="art/selection.json" if selection else None,
                selected_cover=selection["selected_cover"] if selection else None,
                selected_poster=selection["selected_poster"] if selection else None,
                variant_exports=cover_variants, comparison=exports["comparison"], inherited_test_poster_in_staging=not bool(selection)),
            icon=dict(status="GENERATED_PENDING_USER_REVIEW", independently_generated=True,
                exports=icon_exports, actual_size_sheet=exports["icon_actual_sizes"],
                inherited_test_icon_in_staging=True), manifest="art-files.json", rebuild_hashes_after_art_changes=True),
        text=dict(directory="text", status="bilingual local drafts; no publishing/upload action"),
        manifest=dict(json="runtime-files.json", json_sha256=sha(PREP / "runtime-files.json"), sha256_file="runtime-files.sha256", sha256_file_sha256=sha(PREP / "runtime-files.sha256")),
        local_audit="read-only-audit.json", local_audit_is_not_upload_content=True,
        open_items=(["User chooses a cover; no selection inferred"] if not selection else []) +
            ["User reviews the generated independent icon and actual-size sheet before final runtime art export", "User verifies the latest management UI and gameplay", "Rebuild hashes after any runtime/art change", "Publication requires a later explicit user instruction"])
    write_json(PREP / "release-candidate.json", release)
    checklist = f"""# 蘇清的传送门：本地发布准备核对清单

刷新时间：{prepared_at}。当前为 **{version} / schema 3 测试候选**，尚未发布，未创建工坊项目、SteamID 或上传任务。

- [x] 源码、隔离运行目录和 staging 共 {len(source)} 个文件、{sum(x['bytes'] for x in source):,} 字节；逐文件大小及 SHA-256 相同。
- [x] 源码与最新离线 PASS 记录的运行文件哈希完全一致；本次刷新只读回记录，不重复运行测试。
- [x] 保留纯 Lua 产品及测试版号；没有自有 Java/JAR 或 ZombieBuddy 必需依赖，Viewpoint 为可选外观适配。
- [x] 拟外发内容仅为 `staging/content/mods/SuQingPortals`；未复制私人参考图、测试、工具、历史记录或个人存档。
- [x] 候选文本和 `text/` 发布文案扫描未发现盘符绝对路径或 UNC 路径。
- [x] 旧 staging 和收据已保留到 `history/{stamp}`；本轮没有修改运行包、个人配置或存档。
- [x] 四版封面及独立透明 icon 已生成，1024 封面和32／64／128／256 icon 导出与记录哈希相同；对比图和实际尺寸检查图已备齐。
{('- [x] 用户已选定' + selected_variant + '版封面；已核验母版与正式导出，staging poster已应用该稿。') if selection else '- [ ] 用户从四版封面中选定一版；当前未选，staging 保留旧测试 poster。'}
- [ ] 用户查看独立 icon 及实际尺寸检查图后定稿；本轮未替换运行 icon。
- [ ] 用户游戏内验收最新供电显示、窗口缩放、四槽布局和移除物资赠送；其余长距加载、异常恢复及 Viewpoint 仍按验收步骤确认。
- [ ] 任意源码、美术或资源变化后重新验证对应范围并刷新哈希。
- [ ] 用户另行明确授权后才进行工坊发布及可见性操作。

离线记录及日志摘要见 `read-only-audit.json`。这些独立解释器、mock、原生解析及持久化检查不代替游戏内运行验收，也不构成稳定版、联机或车辆支持声明。

`release-candidate.json`、`runtime-files.json`、`runtime-files.sha256`、`art-files.json` 和本清单均为本地资料，保留在 content 外。四版原图与提示词在 `art/`；{'用户选稿与导出哈希记录在 art/selection.json。' if selection else '未替用户选稿。'}发布文案在 `text/`。
"""
    (PREP / "发布核对清单.md").write_text(checklist, encoding="utf-8")
    print(json.dumps(dict(status=release["status"], version=version, files=len(source), bytes=release["total_bytes"],
                         history=history.relative_to(PREP).as_posix(), cover=selected_variant or "UNSELECTED", uploaded=False), ensure_ascii=False))


if __name__ == "__main__":
    main()
