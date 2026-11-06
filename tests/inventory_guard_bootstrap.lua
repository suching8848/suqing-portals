-- Loaded after the real Core/BatterySlots/World modules. These mocks provide
-- widget/list/character services used by extracted current native Lua methods.
TEST.guardChecks=0
ISInventoryPage={}
ISInventoryPaneContextMenu={}
ISInventoryTransferAction={}
ISTransferAction={}
function isClient() return false end
function isServer() return false end
function getTimestampMs() return 1000 end
function getText() return 'native-ui' end
function instanceof(object,typeName) return object and object.className==typeName or false end
ArrayList={new=function()
    local list=TEST.list()
    function list:add(value) self.values[#self.values+1]=value end
    return list
end}
for _,name in ipairs({'OnRefreshInventoryWindowContainers','OnGameStart'}) do
    Events[name]=Events[name] or {callbacks={}}
    local event=Events[name]
    event.Add=function(fn) event.callbacks[#event.callbacks+1]=fn end
end
function triggerEvent(name,...)
    for _,callback in ipairs(Events[name].callbacks or {}) do callback(...) end
end
local baseContainer=TEST.container
function TEST.container(parent)
    local container=baseContainer(parent)
    function container:getEffectiveCapacity() return self.capacity or 40 end
    function container:getMaxWeight() return self.capacity or 40 end
    function container:isExplored() return true end
    function container:isLockedToCharacter() return false end
    function container:isExistYet() return true end
    function container:isRemoveItemAllowed() return not self.denyRemove end
    function container:isItemAllowed() return not self.denyAdd end
    function container:hasRoomFor() return true end
    function container:isInside() return false end
    function container:setHasBeenLooted() end
    function container:DoRemoveItem(item) return self:Remove(item) end
    return container
end
local baseBattery=TEST.battery
function TEST.battery(...)
    local item=baseBattery(...)
    function item:getIsCraftingConsumed() return false end
    function item:setJobDelta() end
    function item:isFavorite() return false end
    function item:getType() return 'CarBattery1' end
    return item
end
local basePlayer=TEST.player
function TEST.player(square,index)
    local player=basePlayer(square,index)
    function player:getJoypadBind() return -1 end
    function player:getInventory() return self.inventory end
    return player
end
ItemPicker={fillContainer=function() error('explored fixture must not spawn loot') end,updateOverlaySprite=function() end}
ISMouseDrag={}
function ISInventoryTransferAction:isAlreadyTransferred() return false end
function ISInventoryTransferAction:getNotFullFloorSquare() return nil end
function ISInventoryTransferAction:playTransferCompleteSound() end
function ISInventoryPage:playContainerOpenCloseSounds() end
function ISInventoryPage:playContainerOpenSound() end
function ISInventoryPage:getContainerParent(container) return container and container:getParent() end
function ISInventoryPage:refreshWeight() self.weightRefresh=(self.weightRefresh or 0)+1 end
function ISInventoryPage:updateItemCount() self.countRefresh=(self.countRefresh or 0)+1 end
function ISInventoryPage.GetFloorContainer(playerNum) return TEST.guardFloor end
function getPlayerInventory() return TEST.guardInventoryPage end
function getPlayerLoot() return TEST.guardLootPage end
function TEST.guardParent()
    return {getModData=function() return {} end,getOverlaySprite=function() return nil end}
end
function TEST.guardContainer(typeName,parent)
    local container=TEST.container(parent or TEST.guardParent());container:setType(typeName);return container
end
function TEST.guardButton(container,index)
    local button={inventory=container,x=0,y=(index-1)*32-1,width=32,height=32,name=container:getType(),capacity=40}
    function button:setX(value) self.x=value end
    function button:setY(value) self.y=value end
    function button:getBottom() return self.y+self.height end
    function button:setBackgroundRGBA(r,g,b,a) self.background={r,g,b,a} end
    return button
end
function TEST.guardPage(containers,selected)
    local page={player=0,onCharacter=false,buttonSize=32,buttonPool={},backpacks={}}
    setmetatable(page,{__index=ISInventoryPage})
    for index,container in ipairs(containers) do page.backpacks[index]=TEST.guardButton(container,index) end
    page.inventoryPane={inventory=selected,lastinventory=selected,inventoryPage=page,height=200,y=0,selected={}}
    function page.inventoryPane:bringToTop() end
    function page.inventoryPane:hideButtons() end
    function page.inventoryPane:refreshContainer() self.refreshCount=(self.refreshCount or 0)+1 end
    local panel={removed={}}
    function panel:removeChild(button) self.removed[#self.removed+1]=button end
    function panel:setHeight(value) self.height=value end
    function panel:setY(value) self.y=value end
    function panel:setScrollHeight(value) self.scrollHeight=value end
    page.containerButtonPanel=panel
    page.resizeWidget={height=0,bringToTop=function() end}
    page.resizeWidget2={bringToTop=function() end}
    page.inventory=selected
    function page:refreshBackpacks() TEST.nativeFinishRefresh(self,#self.backpacks) end
    return page
end
