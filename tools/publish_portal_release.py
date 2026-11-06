"""One explicit Steam stage for one frozen SuQing Workshop release.

Stages: read, preflight, create, upload, dependencies, verify. No stage chains
creation, upload or dependency mutations. Native callback bytes and call handles
are durably recorded. A timed-out/uncertain mutation is never retried by this tool.

release.json schema is documented in publish_workshop_release.schema.json.
API reference: https://partner.steamgames.com/doc/api/ISteamUGC
"""
from __future__ import annotations

import argparse
import ctypes as c
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import sys
import time
import uuid


APP = 108600
OWNER = "76561198881912882"
TASK = Path(r"D:\steam\steamapps\common\ProjectZomboid\CodexAssets\ReleaseRepair_20261106")
BASE_SCRIPT = Path(r"D:\steam\steamapps\common\ProjectZomboid\CodexAssets\IrrigationRelease100_20261102_013011\publish_irrigation.py")
SPEC = importlib.util.spec_from_file_location("suqing_steam_native_base", BASE_SCRIPT)
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)  # Definitions/assertions only; never inputs()/main().
INVALID = (1 << 64) - 1
require, sha, now = BASE.require, BASE.sha, BASE.now
SLUGS = {"container-upgrade", "backpack-super-upgrade", "refrigeration-upgrade",
         "irrigation-care", "firearm-weight-charms", "mfs-fixed-buyback",
         "container-auto-upgrade", "patch-collection", "music-albums", "weight-training"}
EXISTING = {"container-upgrade": "3823988025", "firearm-weight-charms": "3824003141",
            "irrigation-care": "3831881094", "backpack-super-upgrade":"3832223700", "refrigeration-upgrade":"3832223788", "mfs-fixed-buyback":"3832223597", "container-auto-upgrade":"3832223857", "patch-collection":"3832223928"}
DEPENDENCIES = {"firearm-weight-charms": ["3633421539"],
                "mfs-fixed-buyback": ["3633421539"], "irrigation-care": ["3546314080"], "music-albums":["3397198968"]}

EXPECTED_PATCH_IDS = {'Codex_FashionoidFluidTooltip_4221', 'Codex_InventoryTransferPerformance_4221', 'Codex_MustangRecipeGuard_4221', 'Codex_MFS_AttachedLight_Hotkey_4221', 'Codex_DAMN_VanillaTires_4221', 'Codex_AttachedGrouping_4221', 'CodexCharacterMenuTweaks_4221', 'Codex_DebugMenu_Generator_4221', 'CodexXFACTION_CN_4221', 'CodexTranslatorPercentFix_4221', 'Codex_MFS_AmmoVisual_Compat_4221', 'SuQingChumMassProduction', 'Codex_TheyKnew_CN_TextFix_4221', 'SuQingBatchFarmingMenu_4221', 'Codex_TrueMusic_Headphones_4221', 'Codex_AmmoBox_CN_TextFix_4221', 'Codex_MFSOpticsFix_4221', 'SuQingRecipeInputGuard_4221', 'Codex_NarcoticsStatus_4221', 'CodexNarcotics_CN_4221', 'PinyinSearch_SafeSources_4221_LocalFix', 'SuQingProteinTrainingBoost', 'Codex_XFDynamicRecordGuard_4221', 'Codex_ChineseCrop_Tooltip_4221', 'Codex_NoirSling_SP_Compat_4221'}

# Explicitly reviewed additions for the 2026-11-06 local candidates. Never
# infer new IDs or turn optional per-submod requirements into global ones.
SLUGS.update({"search-enhancement", "freshness-fridge", "freshness-lunchbox", "portals"})
EXPECTED_PATCH_IDS.update({"Codex_ViewpointLegacyPromptFix_4221", "Codex_ChinaBrewingBooks50_4221",
    "SuQingBoatRVRoomGuard_4221", "SuQingBoatCraftFromFloor_4221", "SuQingUIInteractionFixes",
    "SuQingMustangProtectionRepair", "SuQingWorldStateGuard_4221"})
EXPECTED_NEW_IDS = {"search-enhancement": "SuQingSearchEnhancement", "freshness-fridge": "SuQingFreshnessFridge",
                    "freshness-lunchbox": "SuQingFreshnessLunchbox", "portals": "SuQingPortals"}

class Steam(BASE.Steam):
    def __init__(self, stage):
        super().__init__("dependency" if stage == "dependencies" else stage)

    def bind(self, name, result, *args):
        if name == "SteamAPI_ISteamUGC_SetLanguage" or (self.mode == "upload" and name == "SteamAPI_ISteamUGC_SetItemUpdateLanguage"):
            fn = getattr(self.dll, name)
            fn.restype, fn.argtypes = result, list(args)
            self.bound.append(name)
            return fn
        return super().bind(name, result, *args)

    def query(self, handle, deadline):
        # Uploads and reads use the same language slot for combined bilingual text.
        try:
            language = self.ugcfn("SetLanguage", c.c_bool, c.c_uint64, c.c_char_p)
        except AttributeError:
            pass
        else:
            require(language(self.ugc, handle, b"english"), "Query SetLanguage rejected")
        return super().query(handle, deadline)

    def published(self, deadline):
        # Creator app=0 also finds items created through non-game publishing APIs.
        create = self.ugcfn("CreateQueryUserUGCRequest", c.c_uint64, c.c_uint32,
                            c.c_int32, c.c_int32, c.c_int32, c.c_uint32, c.c_uint32, c.c_uint32)
        items, expected_total = [], None
        for page in range(1, 201):
            handle = create(self.ugc, int(OWNER) & 0xffffffff, 0, -1, 0, 0, APP, page)
            try:
                result = self.query(handle, deadline)
                if expected_total is None:
                    expected_total = result.total
                require(result.total == expected_total, "Published list changed during enumeration")
                for index in range(result.returned):
                    detail = self.read_result(handle, index)
                    items.append({"id": str(detail.item), "title": bytes(detail.title).decode("utf-8"),
                                  "visibility": detail.visibility})
                if len(items) >= expected_total:
                    require(len(items) == expected_total and len({v['id'] for v in items}) == expected_total,
                            "Published count/duplicate mismatch")
                    return items
                require(result.returned > 0, "Incomplete published enumeration")
            finally:
                if handle not in (0, INVALID):
                    self.release(handle)
        raise ValueError("Published page limit exceeded")


def canonical_tree_hash(files):
    return sha(json.dumps(files, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def load_inputs(path):
    raw = BASE.regular(path).read_bytes()
    meta = json.loads(raw.decode("utf-8-sig"))
    require(meta.get("schema_version") == 1 and meta.get("appid") == APP
            and str(meta.get("owner")) == OWNER and meta.get("slug") in SLUGS,
            "Frozen release app/account/schema/slug mismatch")
    slug = meta["slug"]
    required = [str(x) for x in meta.get("required_workshop_ids", [])]
    require(required == DEPENDENCIES.get(slug, []),
            "Only this project's actual global prerequisite may be a Workshop dependency")
    existing = str(meta["existing_item_id"]) if meta.get("existing_item_id") else None
    if slug in EXISTING:
        require(existing == EXISTING[slug], "Existing public item must reuse its known Workshop ID")
    elif existing:
        require(existing.isdigit() and 0 < int(existing) < INVALID, "Invalid existing item ID")
        require(existing not in EXISTING.values(), "This ID belongs to another known SuQing project")
    require(existing not in required, "Cannot target the original dependency item")
    content = BASE.regular(Path(meta["content_path"]), True)
    files = BASE.tree(content)
    tree_hash = canonical_tree_hash(files)
    require(tree_hash == meta.get("content_tree_sha256"), "Frozen content tree hash mismatch")
    actual_versions, runtime_infos, metadata_branches = {}, {}, []
    mods_root = BASE.regular(content / "mods", True)
    for mod_root in sorted(p for p in mods_root.iterdir() if p.is_dir()):
        # This publication targets B42.21: an exact branch takes precedence over
        # the shared 42 branch; legacy root metadata is only a fallback. Root and
        # other retained branch versions need not equal the active branch.
        candidates = [mod_root / "42.21/mod.info", mod_root / "42/mod.info", mod_root / "mod.info"]
        selected = next((p for p in candidates if p.is_file()), None)
        require(selected is not None, f"No applicable B42.21 mod.info: {mod_root}")
        for info_path in sorted(mod_root.rglob("mod.info")):
            info = dict(line.split("=", 1) for line in info_path.read_text("utf-8-sig").splitlines() if "=" in line)
            metadata_branches.append({"path": info_path.relative_to(content).as_posix(),
                                      "id": info.get("id"), "modversion": info.get("modversion"),
                                      "selected_for_b4221": info_path == selected})
            if info_path == selected:
                require(info.get("id"), f"Active mod.info has no ID: {info_path}")
                require(info["id"] not in actual_versions, "Duplicate active Mod ID across packaged mod folders")
                actual_versions[info["id"]] = info.get("modversion")
                runtime_infos[info["id"]] = info_path.relative_to(content).as_posix()
    require(set(actual_versions) == set(meta["mod_ids"]) and len(meta["mod_ids"]) == len(actual_versions),
            "Packaged Mod ID set mismatch")
    require(actual_versions == meta["mod_versions"], "Packaged mod.info versions differ from frozen release")
    if slug == "backpack-super-upgrade":
        require(set(actual_versions) == {"ExSuQingBackpackSuperUpgrade_4221", "CodexNekomataEXCompat_4221",
                    "CodexNekomataEXUpgrade_4221", "Codex_SuQingWearableCompat_4221"}, "EX must contain main + three optional IDs")
    if slug == "patch-collection":
        require(set(actual_versions) == EXPECTED_PATCH_IDS, "Patch Workshop package must match the reviewed 32 optional IDs")
    if slug in EXPECTED_NEW_IDS:
        require(set(actual_versions) == {EXPECTED_NEW_IDS[slug]}, "New main project must contain exactly its reviewed Mod ID")
        active = runtime_infos[EXPECTED_NEW_IDS[slug]]
        active_info = dict(line.split("=", 1) for line in (content / active).read_text("utf-8-sig").splitlines() if "=" in line)
        require(not active_info.get("require", "").strip(), "New main project's optional integrations must not become hard dependencies")
    if slug == "portals":
        require("test" in str(meta["version"]) or (
            existing == "3834693880" and meta.get("publication_authorized") is True
            and meta.get("readiness", {}).get("gameplay_accepted") is True
            and meta.get("readiness", {}).get("publication_ready") is True),
            "Stable portal publication requires the existing item, explicit authorization and accepted readiness")
        require(not any(Path(p).suffix.lower() in {".jar", ".dll", ".class", ".so", ".dylib"} for p in files),
                "Reviewed portal content is pure Lua and must not acquire a native/Java loader")
    new_visibility = meta.get("new_item_visibility", 2)
    require(type(new_visibility) is int and new_visibility in (0, 1, 2, 3), "Invalid frozen visibility for a newly created item")
    # Offline validation and private test preparation remain available while
    # the pending icon/gameplay review is truthfully recorded. Public upload
    # of this test candidate requires its recorded publication readiness.
    if slug == "portals" and not existing and new_visibility == 0:
        require(meta.get("readiness", {}).get("publication_ready") is True,
                "Portal public publication is not ready: review icon and latest gameplay first")
    loaded, paths = {}, {}
    for key in ("title", "description", "preview", "changenote"):
        source = BASE.regular(Path(meta[key + "_file"]))
        data = source.read_bytes()
        require(sha(data) == meta[key + "_sha256"], f"Frozen {key} hash mismatch")
        loaded[key], paths[key] = data, source
    title = loaded["title"].decode("utf-8-sig").strip().encode("utf-8")
    desc = loaded["description"].decode("utf-8-sig").encode("utf-8")
    note = loaded["changenote"].decode("utf-8-sig").encode("utf-8")
    require(0 < len(title) <= 128 and not any(x in title for x in (b"\0", b"\r", b"\n")), "Invalid title")
    require(0 < len(desc) < 8000 and b"\0" not in desc, "Description must be less than 8000 UTF-8 bytes")
    require(0 < len(note) <= 8000 and b"\0" not in note, "Invalid change note")
    preview = loaded["preview"]
    require(24 <= len(preview) < 1_000_000 and preview[:8] == b"\x89PNG\r\n\x1a\n"
            and all(0 < n <= 8192 for n in struct.unpack(">II", preview[16:24])), "Preview must be a valid PNG below 1 MB")
    tags = meta["tags"]
    require(isinstance(tags, list) and tags and len(tags) == len(set(tags))
            and all(isinstance(v, str) and 0 < len(v.encode()) < 255 and not re.search(r"[\x00\r\n,]", v) for v in tags), "Invalid tags")
    require(isinstance(meta.get("duplicate_keywords"), list) and meta["duplicate_keywords"]
            and all(isinstance(v, str) and v.strip() for v in meta["duplicate_keywords"]), "Duplicate search keywords required")
    metadata = json.dumps({"suqing_release": 1, "slug": slug, "version": str(meta["version"]),
                           "content_tree_sha256": tree_hash}, separators=(",", ":"), ensure_ascii=False)
    identity = {"release_sha256": sha(raw), "content_tree_sha256": tree_hash,
                "content_bytes": sum(v["bytes"] for v in files.values()), "files": len(files),
                "title_sha256": sha(title), "description_sha256": sha(desc),
                "changenote_sha256": sha(note), "preview_sha256": sha(preview),
                "metadata": metadata, "mod_versions": actual_versions,
                "runtime_mod_infos": runtime_infos, "metadata_branches": metadata_branches,
                "native_base_script_sha256": sha(BASE_SCRIPT.read_bytes())}
    return meta, paths, title, desc, note, identity


def save_json(path, state, initial=False):
    target = path if initial else path.with_name(path.name + ".tmp")
    with target.open("x" if initial else "w", encoding="utf-8") as stream:
        json.dump(state, stream, ensure_ascii=False, indent=2)
        stream.flush(); os.fsync(stream.fileno())
    if not initial:
        os.replace(target, path)


def history(directory, current):
    result = []
    for path in directory.glob("*.json"):
        if path == current:
            continue
        try:
            receipt = json.loads(path.read_text("utf-8-sig"))
        except (OSError, ValueError) as error:
            raise ValueError(f"Unreadable prior receipt; inspect before mutation: {path}") from error
        result.append((path, receipt))
    return result


def resolve_item(meta, old, requested):
    known = {str(v["item"]) for _, v in old if v.get("stage") == "create"
             and v.get("callback", {}).get("result") == 1 and v.get("item")}
    if meta.get("existing_item_id"):
        known.add(str(meta["existing_item_id"]))
    require(len(known) <= 1, "Conflicting durable item IDs; manual reconciliation required")
    target = next(iter(known), None)
    if requested:
        require(str(requested) == target, "--item must match the frozen or durably created target")
    return int(target) if target else None


def callback_record(value, callback_id):
    result = {"type": callback_id, "result": value.result, "id": str(value.item),
              "raw_hex": c.string_at(c.byref(value), c.sizeof(value)).hex(), "bytes": c.sizeof(value)}
    if hasattr(value, "needs_legal"):
        result["needs_legal"] = bool(value.needs_legal)
    if hasattr(value, "child"):
        result["child"] = str(value.child)
    return result


def normalized_text(value):
    return value.replace("\r\n", "\n").strip()


def remote_matches(remote, meta, title, desc, identity):
    return {"title": remote["title"] == title.decode(),
            "description": normalized_text(remote["description"]) == normalized_text(desc.decode()),
            "metadata": remote["metadata"] == identity["metadata"],
            "content_bytes": remote["total_files_size"] == identity["content_bytes"],
            "preview_present": remote["preview_size"] > 0,
            # Steam returns canonical tag casing (for example QoL becomes QOL).
            "tags": not remote["tags_truncated"] and {v.strip().casefold() for v in remote["tags"].split(",")} == {v.casefold() for v in meta["tags"]},
            "dependencies": set(meta["required_workshop_ids"]).issubset(remote["children"])}


def allow_upload_retry(args, old, target, identity):
    attempted = [(p, v) for p, v in old if v.get("stage") == "upload" and v.get("mutation_attempted")
                 and v.get("item") == str(target) and v.get("inputs") == identity]
    if not attempted:
        return
    require(args.retry_after_receipt and args.read_receipt,
            "Upload previously attempted; inspect callback and fresh read before explicit retry")
    previous = json.loads(BASE.regular(args.retry_after_receipt).read_text("utf-8-sig"))
    readback = json.loads(BASE.regular(args.read_receipt).read_text("utf-8-sig"))
    require(previous in [v for _, v in attempted] and previous.get("callback", {}).get("result", 1) != 1,
            "Only a returned explicit callback failure can be retried; uncertain/successful submit must be reconciled")
    require(readback.get("stage") == "read" and readback.get("status") == "read_complete"
            and readback.get("inputs") == identity and readback.get("item") == str(target)
            and readback.get("started_at", "") > previous.get("finished_at", "~"), "A newer matching read receipt is required")
    payload_checks = {k: v for k, v in readback.get("remote_matches_release", {}).items() if k != "dependencies"}
    require(payload_checks and not all(payload_checks.values()),
            "Remote upload payload already matches; finish dependencies/verification instead of uploading again")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=["read", "preflight", "create", "upload", "dependencies", "verify"])
    parser.add_argument("--release", required=True, type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--item", type=int)
    parser.add_argument("--preflight-receipt", type=Path)
    parser.add_argument("--retry-after-receipt", type=Path)
    parser.add_argument("--read-receipt", type=Path)
    parser.add_argument("--deadline-seconds", type=int, default=1200)
    args = parser.parse_args()
    require(args.release.is_absolute(), "Use an absolute frozen release.json path")
    require(60 <= args.deadline_seconds <= 3600, "Deadline must be 60..3600 seconds")
    # Read only the identity needed to choose one canonical receipt directory.
    meta_hint = json.loads(BASE.regular(args.release).read_text("utf-8-sig"))
    require(meta_hint.get("slug") in SLUGS, "Unknown release slug")
    receipt_dir = TASK / "publication-receipts" / meta_hint["slug"]
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt = args.receipt or receipt_dir / (args.stage + "-" + datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8] + ".json")
    require(receipt.is_absolute() and receipt.parent.resolve() == receipt_dir.resolve()
            and receipt.suffix == ".json" and not receipt.exists(), "Receipt must be a new JSON in this project's publication-receipts directory")
    state = {"publisher": "suqing-frozen-release-v2-local-preparation", "stage": args.stage, "slug": meta_hint["slug"],
             "started_at": now(), "owner": OWNER, "app": APP, "release": str(args.release),
             "publisher_script_sha256": sha(Path(__file__).read_bytes()),
             "item": None, "status": "starting", "mutation_attempted": False}
    save_json(receipt, state, True)
    steam, exit_code = None, 1
    def save(): save_json(receipt, state)
    def guard(operation):
        state.update(status="mutation_in_progress", mutation_attempted=True,
                     operation=operation, mutation_started_at=now()); save()
    try:
        meta, paths, title, desc, note, identity = load_inputs(args.release)
        state["inputs"] = identity
        old = history(receipt_dir, receipt)
        require(all(v.get("slug") == meta["slug"] and str(v.get("owner")) == OWNER and v.get("app") == APP for _, v in old), "Receipt history target mismatch")
        item = resolve_item(meta, old, args.item)
        state["item"] = str(item) if item else None
        if args.stage == "create":
            require(item is None and not meta.get("existing_item_id"), "Existing item found; reuse its ID, do not create")
            require(args.preflight_receipt, "create requires a successful matching --preflight-receipt")
            preflight = json.loads(BASE.regular(args.preflight_receipt).read_text("utf-8-sig"))
            require(preflight.get("status") == "preflight_passed" and preflight.get("inputs") == identity
                    and preflight.get("slug") == meta["slug"] and not preflight.get("duplicates"), "Preflight mismatch")
            require(not any(v.get("stage") == "create" and v.get("mutation_attempted") for _, v in old),
                    "Create already attempted; recover its item ID, never blindly repeat")
        if args.stage in {"upload", "dependencies", "verify"}:
            require(item is not None and str(item) not in meta["required_workshop_ids"], "No unambiguous owned target ID")
        if args.stage == "upload":
            allow_upload_retry(args, old, item, identity)
        steam = Steam(args.stage); steam.start()
        state["api_dll_sha256"] = sha((BASE.GAME / "steam_api64.dll").read_bytes())
        deadline = time.monotonic() + args.deadline_seconds
        if args.stage in {"read", "preflight", "create"}:
            owned = steam.published(deadline)
            state.update(published=owned, published_count=len(owned))
            duplicates = [v for v in owned if any(term.casefold() in v["title"].casefold() for term in meta["duplicate_keywords"])
                          and (not item or v["id"] != str(item))]
            state["duplicates"] = duplicates
            if item:
                remote = steam.details(item, deadline)
                state["remote"] = remote
                state["remote_matches_release"] = remote_matches(remote, meta, title, desc, identity)
            if args.stage == "preflight":
                require(item is not None or not duplicates, "Potential same-project item exists; recover its ID before creation")
                state["status"] = "preflight_passed"
            elif args.stage == "read":
                state["status"] = "read_complete"
            else:
                require(not duplicates and load_inputs(args.release)[5] == identity, "Duplicate/changed frozen input before create")
                create = steam.ugcfn("CreateItem", c.c_uint64, c.c_uint32, c.c_int32)
                guard("CreateItem")
                call = create(steam.ugc, APP, 0); state["api_call"] = str(call); save()
                value = steam.wait(call, 3403, BASE.Created, deadline)
                state["callback"] = callback_record(value, 3403)
                state["item"] = str(value.item); save()  # Persist native returned ID before anything else.
                require(value.result == 1 and 0 < value.item < INVALID, "Create callback failed")
                require(not value.needs_legal, "Workshop legal agreement requires the user")
                state["status"] = "created_empty"
        else:
            before = steam.details(item, deadline); state["remote_before"] = before; save()
            require(load_inputs(args.release)[5] == identity, "Frozen inputs changed after remote check")
            if meta.get("existing_item_id") and meta["slug"] not in EXISTING:
                try: same_slug = json.loads(before["metadata"]).get("slug") == meta["slug"]
                except (ValueError, AttributeError): same_slug = False
                require(same_slug or any(term.casefold() in before["title"].casefold() for term in meta["duplicate_keywords"]),
                        "Recovered target does not identify this project")
            if args.stage == "dependencies":
                missing = set(meta["required_workshop_ids"]) - set(before["children"])
                require(len(missing) <= 1, "This release supports at most one mandatory global dependency")
                if not missing:
                    state["status"] = "dependencies_already_present"
                else:
                    child = int(next(iter(missing)))
                    add = steam.ugcfn("AddDependency", c.c_uint64, c.c_uint64, c.c_uint64)
                    guard("AddDependency")
                    call = add(steam.ugc, item, child); state["api_call"] = str(call); save()
                    value = steam.wait(call, 3412, BASE.DependencyAdded, deadline)
                    state["callback"] = callback_record(value, 3412); save()
                    require(value.result == 1 and value.item == item and value.child == child, "Dependency callback mismatch/failure")
                    state["status"] = "dependency_added"
            elif args.stage == "verify":
                checks = remote_matches(before, meta, title, desc, identity)
                state["checks"] = checks
                require(all(checks.values()), "Remote content/description/metadata/tags/dependency check failed")
                successful = [v for _, v in old if v.get("stage") == "upload" and v.get("status") == "uploaded"
                              and v.get("item") == str(item) and v.get("inputs") == identity
                              and v.get("callback", {}).get("result") == 1]
                require(successful, "No successful native submit receipt for these exact inputs")
                require(before["visibility"] == successful[-1]["submitted_visibility"], "Remote visibility differs from successful submit")
                state["status"] = "verified_public" if before["visibility"] == 0 else "verified_preserved_visibility"
                state["extra_dependencies_preserved"] = sorted(set(before["children"]) - set(meta["required_workshop_ids"]))
                state["verification_boundary"] = "Native success plus exact text, metadata tree hash, content-byte total, tags and preview presence; not a remote per-file SHA download."
            else:
                update = steam.ugcfn("StartItemUpdate", c.c_uint64, c.c_uint32, c.c_uint64)(steam.ugc, APP, item)
                require(update not in (0, INVALID), "Invalid update handle")
                try:
                    language = steam.ugcfn("SetItemUpdateLanguage", c.c_bool, c.c_uint64, c.c_char_p)
                except AttributeError:
                    state["update_language"] = "API unavailable; Steam default language"
                else:
                    require(language(steam.ugc, update, b"english"), "SetItemUpdateLanguage rejected")
                    state["update_language"] = "english (description contains both languages)"
                values = [("SetItemContent", str(Path(meta["content_path"])).encode("utf-8")),
                          ("SetItemTitle", title), ("SetItemDescription", desc),
                          ("SetItemPreview", str(paths["preview"]).encode("utf-8")),
                          ("SetItemMetadata", identity["metadata"].encode("utf-8"))]
                for name, data in values:
                    require(steam.ugcfn(name, c.c_bool, c.c_uint64, c.c_char_p)(steam.ugc, update, data), name + " rejected")
                encoded = [v.encode("utf-8") for v in meta["tags"]]
                array = (c.c_char_p * len(encoded))(*encoded)
                tags = BASE.StringArray(array, len(encoded))
                require(steam.ugcfn("SetItemTags", c.c_bool, c.c_uint64, c.POINTER(BASE.StringArray), c.c_bool)
                        (steam.ugc, update, c.byref(tags), False), "SetItemTags rejected")
                # Existing choices are retained. A newly created item uses
                # the explicit frozen target and defaults to a private draft.
                visibility = before["visibility"] if meta.get("existing_item_id") else meta.get("new_item_visibility", 2)
                require(visibility in (0, 1, 2, 3), "Unsupported current visibility")
                require(steam.ugcfn("SetItemVisibility", c.c_bool, c.c_uint64, c.c_int32)
                        (steam.ugc, update, visibility), "SetItemVisibility rejected")
                state["submitted_visibility"] = visibility
                submit = steam.ugcfn("SubmitItemUpdate", c.c_uint64, c.c_uint64, c.c_char_p)
                progress = steam.ugcfn("GetItemUpdateProgress", c.c_int32, c.c_uint64, c.POINTER(c.c_uint64), c.POINTER(c.c_uint64))
                require(load_inputs(args.release)[5] == identity, "Frozen input changed immediately before submit")
                guard("SubmitItemUpdate")
                call = submit(steam.ugc, update, note); state["api_call"] = str(call); save()
                last = [0.0]
                def tick():
                    if time.monotonic() - last[0] < 5: return
                    last[0] = time.monotonic(); done, total = c.c_uint64(), c.c_uint64()
                    status = progress(steam.ugc, update, c.byref(done), c.byref(total))
                    state["progress"] = {"at": now(), "stage": status, "processed": done.value, "total": total.value}
                    save(); print(json.dumps({"progress": state["progress"]}), flush=True)
                value = steam.wait(call, 3404, BASE.Submitted, deadline, tick)
                state["callback"] = callback_record(value, 3404); save()
                require(value.result == 1 and value.item == item and not value.needs_legal, "Submit callback failed/mismatch/agreement required")
                require(load_inputs(args.release)[5] == identity, "Frozen inputs changed during submit")
                state["status"] = "uploaded"
        exit_code = 0
    except BaseException as error:
        callback = state.get("callback", {})
        state["status"] = ("needs_user_agreement" if callback.get("needs_legal") else
                           "mutation_failed" if callback.get("result", 1) != 1 else
                           "uncertain_do_not_retry" if state["mutation_attempted"] else "failed_before_mutation")
        state["error"] = f"{type(error).__name__}: {error}"
        exit_code = 2 if state["mutation_attempted"] else 1
    finally:
        if steam:
            state["bound_api"] = sorted(set(steam.bound))
            try: steam.close()
            except BaseException as error: state["shutdown_error"] = f"{type(error).__name__}: {error}"
        state["finished_at"] = now(); save()
    print(json.dumps({"status": state["status"], "item": state.get("item"), "receipt": str(receipt),
                      "error": state.get("error")}, ensure_ascii=False), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
