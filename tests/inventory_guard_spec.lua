local P,W,S,G=SuQingPortals,SuQingPortals.World,SuQingPortals.BatterySlots,SuQingPortals.InventoryGuard
local checks=0
local function check(value,label) checks=checks+1;if not value then error(label) end end
local origin=TEST.square(0,0,0)
local player=TEST.player(origin)
player.inventory:setType('inventory')
local portal=TEST.object(TEST.square(1,0,0))
check(W.register(portal)~=nil,'production backend creates pure-Lua internal storage')
local bank=portal:getContainer()
check(S.isInternalContainer(bank),'production predicate identifies the actual native bank')
local firstBattery
for slot=1,4 do
    local item=TEST.battery(1);player:getInventory():AddItem(item)
    check(W.Install(player,portal,item,slot),'dedicated backend installs an original battery')
    if slot==1 then firstBattery=item end
end
local chest=TEST.guardContainer('crate')
local vehicle=TEST.guardContainer('TruckBed')
local backpack=TEST.guardContainer('bag')
local floor=TEST.guardContainer('floor');TEST.guardFloor=floor
local lookalike=TEST.guardContainer('suqingportal_internal')
local sameParentWrongRef=TEST.guardContainer('suqingportal_internal',portal)
check(not G.isInternal(chest) and not G.isInternal(vehicle) and not G.isInternal(backpack),'ordinary chest, vehicle and bag are never internal storage')
check(not G.isInternal(lookalike),'same type text alone cannot hide another container')
check(not G.isInternal(sameParentWrongRef),'same portal parent plus wrong container reference cannot hide another container')
local page=TEST.guardPage({chest,bank,vehicle,backpack,lookalike,sameParentWrongRef,floor},bank)
page.forceSelectedContainer=bank;page.forceSelectedContainerTime=99999
page.selectedButton=page.backpacks[2];page.backpackChoice=2
TEST.guardInventoryPage=TEST.guardPage({player:getInventory()},player:getInventory())
TEST.guardInventoryPage.onCharacter=true
TEST.guardLootPage=page
TEST.nativeFinishRefresh(page,#page.backpacks)
check(#page.backpacks==6,'native buttonsAdded event removes exactly one internal-bank button')
local expected={chest,vehicle,backpack,lookalike,sameParentWrongRef,floor}
for index,container in ipairs(expected) do
    check(page.backpacks[index].inventory==container,'all other container buttons keep their relative order '..index)
    check(page.backpacks[index].y==(index-1)*32-1,'native vertical button positions compact correctly '..index)
end
check(page.inventory==floor and page.inventoryPane.inventory==floor,'hidden active container safely falls back to native floor')
check(page.inventoryPane.lastinventory==floor,'last-inventory reference cannot reselect hidden bank')
check(page.forceSelectedContainer==nil,'force-selected hidden bank cannot override repaired selection')
check(page.selectedButton.inventory==floor,'native post-event selection targets a visible button')
check(page.backpackChoice==6,'joypad container choice follows visible repaired selection')
check(#page.buttonPool==1 and page.buttonPool[1].inventory==bank,'hidden button is detached and returned to native pool once')
TEST.nativeFinishRefresh(page,#page.backpacks)
check(#page.buttonPool==1,'repeated native refresh does not duplicate pooled buttons')
check(page.inventoryPane.refreshCount>=2,'real native refresh tail refreshes the pane after filtering')

-- Preserve a non-portal selection even while another hidden bank is removed.
local selectedPage=TEST.guardPage({chest,bank,vehicle,backpack,floor},vehicle)
TEST.nativeFinishRefresh(selectedPage,#selectedPage.backpacks)
check(selectedPage.inventoryPane.inventory==vehicle,'visible selected vehicle remains selected')
check(selectedPage.backpacks[2].inventory==vehicle,'vehicle keeps its relative position after only hidden removal')

-- The installed CleanUI grid helper receives the compacted backing order.
if TEST.nativeCleanUIPosition then
    local grid=TEST.guardPage({chest,bank,vehicle,backpack,floor},chest)
    grid.padding,grid.containerButtonColumns=3,2
    grid.cleanUIGetContainerButtonPosition=TEST.nativeCleanUIPosition
    TEST.nativeFinishRefresh(grid,#grid.backpacks)
    check(grid.backpacks[1].x==3 and grid.backpacks[1].y==3,'actual CleanUI first grid position is preserved')
    check(grid.backpacks[2].x==38 and grid.backpacks[2].y==3,'actual CleanUI second grid position is preserved')
    check(grid.backpacks[3].x==3 and grid.backpacks[3].y==38,'actual CleanUI next-row position compacts correctly')
end

-- Reinsert a stale button deliberately: actual native getContainers still
-- filters it for native and Neat Crafting callers, without mutating the rail.
page.backpacks[#page.backpacks+1]=TEST.guardButton(bank,7)
local unfiltered=TEST.nativeGetContainers(player)
local filtered=ISInventoryPaneContextMenu.getContainers(player)
check(unfiltered:size()==8 and filtered:size()==7,'actual nearby-material provider filters one internal bank')
check(#page.backpacks==7,'nearby-material filtering does not mutate another caller backing rail')
for index=0,filtered:size()-1 do check(filtered:get(index)~=bank,'internal original batteries are absent from crafting container sources') end
check(unfiltered:get(unfiltered:size()-1)==bank,'copy filtering leaves original native result untouched')

-- Stale direct selection routes cannot reopen an internal bank.
local oldInventory=page.inventoryPane.inventory
check(ISInventoryPage.selectContainer(page,{inventory=bank})==false,'native selectContainer rejects hidden bank reference')
check(ISInventoryPage.setNewContainer(page,bank)==false,'native setNewContainer rejects hidden bank reference')
check(page.inventoryPane.inventory==oldInventory,'selection guards do not mutate the current visible container')
ISInventoryPage.setNewContainer(page,chest)
check(page.inventoryPane.inventory==chest,'ordinary native setNewContainer still works')

-- Exercise the actual installed transfer methods, not a stand-in true/false.
local loose=TEST.battery(0.5);chest:AddItem(loose)
local function action(item,source,destination)
    return setmetatable({item=item,character=player,srcContainer=source,destContainer=destination}, {__index=ISInventoryTransferAction})
end
local ordinary=action(loose,chest,player:getInventory())
check(ordinary:isValid(),'ordinary transfer retains actual native validity')
ordinary:transferItem(loose)
check(player:getInventory():contains(loose) and not chest:contains(loose),'ordinary actual native transfer moves the same item')
check(loose:getContainer()==player:getInventory(),'ordinary native transfer keeps item ownership correct')
local blockedOut=action(firstBattery,bank,player:getInventory())
check(not blockedOut:isValid(),'internal-bank output is blocked even without pending token')
blockedOut:transferItem(firstBattery)
check(bank:contains(firstBattery) and not player:getInventory():contains(firstBattery),'final native transfer guard cannot remove an installed original')
portal:getModData().SuQingPortals.pendingToken='active-test-ticket'
check(not blockedOut:isValid(),'pending internal-bank output remains blocked')
portal:getModData().SuQingPortals.pendingToken=nil
local blockedIn=action(loose,player:getInventory(),bank)
check(not blockedIn:isValid(),'all native input is blocked rather than bypassing four-slot assignment')
blockedIn:transferItem(loose)
check(loose:getContainer()==player:getInventory(),'native input cannot change battery ownership')
check(ISTransferAction:transferItem(player,firstBattery,bank,player:getInventory(),nil)==firstBattery,'shared final transfer returns the unchanged internal original')
check(bank:contains(firstBattery),'shared direct-call guard also blocks output')
ISTransferAction:transferItem(player,loose,player:getInventory(),bank,nil)
check(loose:getContainer()==player:getInventory(),'shared direct-call guard also blocks input')
check(W.Remove(player,portal,1),'authorized dedicated backend can still remove an original')
check(firstBattery:getContainer()==player:getInventory(),'dedicated backend removal preserves native owner')
check(W.Install(player,portal,firstBattery,1),'authorized dedicated backend can still reinstall an original')
check(firstBattery:getContainer()==bank,'dedicated backend installation preserves exact original identity')

-- An old pending receipt keeps its old real bank until backend recovery.
local legacyPortal=TEST.object(TEST.square(10,0,0))
legacyPortal.data.SuQingPortals={schema=1,id='legacy-pending-ui',pendingToken='old-pending',slots={}}
local legacyBank=TEST.guardContainer('suqingportalbattery',legacyPortal);legacyPortal:setContainer(legacyBank)
local legacyItem=TEST.battery(0.5);legacyBank:AddItem(legacyItem)
check(not G.isInternal(legacyBank),'old pending bank is not falsely identified as schema3 internal storage')
check(G.blocksNativeTransfer(legacyBank),'exact old pending bank retains its recovery transfer lock')
local legacyAction=action(legacyItem,legacyBank,player:getInventory())
check(not legacyAction:isValid(),'old pending native output is blocked before migration')
legacyAction:transferItem(legacyItem)
check(legacyItem:getContainer()==legacyBank,'old pending final transfer cannot remove the original recovery battery')
legacyPortal.data.SuQingPortals.pendingToken=nil
check(not G.blocksNativeTransfer(legacyBank),'legacy nonpending containers are not indiscriminately blocked')

-- Foreign containers with a copied display/type string retain native behavior.
player:getInventory():Remove(loose);lookalike:AddItem(loose)
local copiedType=action(loose,lookalike,player:getInventory())
check(copiedType:isValid(),'foreign container with identical type is not blocked')
local previousContains=lookalike.contains
lookalike.contains=function() error('native-container-failure-remains-visible') end
local okay=pcall(function() copiedType:isValid() end)
check(not okay,'unrelated native exceptions propagate through local wrappers')
lookalike.contains=previousContains
local before=ISInventoryTransferAction.isValid
G.install()
check(ISInventoryTransferAction.isValid==before,'reinstalling guard does not stack wrappers')
G.filterPage({backpacks={}},'buttonsAdded')
check(G.reported.inventory_pane==true,'unsupported inventory framework emits an explicit diagnostic')
print('PORTAL_NATIVE_INTERNAL_UI_GUARD checks='..checks..' failures=0')
