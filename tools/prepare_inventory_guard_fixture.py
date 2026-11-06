"""Extract current native Lua method bodies for standalone guard regression.

This reads installed source only. It never launches the game or loads a save.
"""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
GAME = Path(r"D:\steam\steamapps\common\ProjectZomboid")


def between(source: str, start: str, end: str) -> str:
    offset = source.index(start)
    finish = source.index(end, offset + len(start))
    return source[offset:finish].rstrip() + "\n"


def main():
    sources = {
        "page": GAME / "media/lua/client/ISUI/ISInventoryPage.lua",
        "context": GAME / "media/lua/client/ISUI/ISInventoryPaneContextMenu.lua",
        "action": GAME / "media/lua/client/TimedActions/ISInventoryTransferAction.lua",
        "shared": GAME / "media/lua/shared/TimedActions/ISTransferAction.lua",
    }
    text = {key: path.read_text(encoding="utf-8-sig") for key, path in sources.items()}
    blocks = [
        between(text["context"], "ISInventoryPaneContextMenu.getContainers = function(character)", "ISInventoryPaneContextMenu.addFixerSubOption"),
        between(text["page"], "function ISInventoryPage:selectContainer(button)", "function ISInventoryPage:selectButtonForContainer(container)"),
        between(text["action"], "function ISInventoryTransferAction:isValid()", "function ISInventoryTransferAction:update()"),
        between(text["action"], "function ISInventoryTransferAction:transferItem(item)", "function ISInventoryTransferAction:canMergeAction"),
    ]
    # This is the real selection/refresh tail after every container was added.
    # The fixture supplies container buttons; production code supplies the event,
    # selection, force-selection, native refresh, scrollbar and end ordering.
    refresh = between(text["page"], '\ttriggerEvent("OnRefreshInventoryWindowContainers", self, "buttonsAdded")', "ISInventoryPage.onRenameContainer = function")
    refresh = "function TEST.nativeFinishRefresh(self, oldNumBackpacks)\nlocal playerObj=getSpecificPlayer(self.player)\nlocal floorContainer=ISInventoryPage.GetFloorContainer(self.player)\n" + refresh
    blocks.append(refresh)
    shared_start = text["shared"].index("function ISTransferAction:transferItem(character, item, srcContainer, destContainer, dropSquare)")
    blocks.append(text["shared"][shared_start:])
    clean_ui = Path(r"D:\steam\steamapps\workshop\content\108600\3437629766\mods\CleanUI\42.19\media\lua\client\ISUI\ISInventoryPage.lua")
    if clean_ui.exists():
        clean_text = clean_ui.read_text(encoding="utf-8-sig")
        clean_position = between(clean_text, "function ISInventoryPage:cleanUIGetContainerButtonPosition(index)", "function ISInventoryPage:cleanUIApplyScaleSettings(force)")
        blocks.append(clean_position.replace("function ISInventoryPage:cleanUIGetContainerButtonPosition(index)", "function TEST.nativeCleanUIPosition(self,index)"))
        sources["clean_ui"] = clean_ui
    blocks.append("TEST.nativeGetContainers=ISInventoryPaneContextMenu.getContainers\n")
    output = ROOT / "tests/inventory_guard_native.lua"
    output.write_text("-- Generated from the current installed native Lua. No game execution.\n" + "\n".join(blocks), encoding="utf-8")
    receipt = {
        "scope": "Read-only native source extraction for standalone Kahlua mocks; game_started=false",
        "sources": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources.values()},
        "extracted": ["getContainers", "selectContainer", "setNewContainer", "ISInventoryTransferAction.isValid", "ISInventoryTransferAction.transferItem", "ISTransferAction.transferItem", "native buttonsAdded-to-end refresh tail"],
        "output": str(output),
    }
    (ROOT / "tests/results").mkdir(parents=True, exist_ok=True)
    (ROOT / "tests/results/inventory-native-source.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print("INVENTORY_NATIVE_SOURCE methods=7 game_started=false")


if __name__ == "__main__":
    main()
