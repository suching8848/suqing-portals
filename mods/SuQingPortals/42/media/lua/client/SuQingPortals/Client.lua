require "SuQingPortals/Core"
require "SuQingPortals/Build"
require "SuQingPortals/UI"
require "SuQingPortals/Transfer"
require "SuQingPortals/Actions"
require "SuQingPortals/InventoryGuard"
require "SuQingPortals/Viewpoint"

local P=SuQingPortals
P.Client=P.Client or {}
local C=P.Client
local function text(key,...) return getText("IGUI_SQP_"..key,...) end
local function notify(player,ok,code)
    if P.UI.instance and P.UI.instance.player==player then P.UI.instance:setResult(ok,code)
    else player:Say(P.UI.resultText(code)) end
end

function C.twoDFallbackAllowed(playerIndex)
    if not Viewpoint then return true end
    if playerIndex~=0 or not Viewpoint.View or not Viewpoint.View.next then return false end
    -- Viewpoint 0.1.6.1 next() is a read-only query of the next mode, not a
    -- camera switch: "first" means the current mode is ordinary isometric.
    local ok,nextMode=pcall(Viewpoint.View.next)
    if not ok then
        if not C.cameraQueryReported then
            C.cameraQueryReported=true
            print("[SuQingPortals] optional camera query failed; 2D click fallback disabled: "..tostring(nextMode))
        end
        return false
    end
    return nextMode=="first"
end

function C.queueInstall(player,object,itemId,slot)
    local state=P.World.getSnapshot(object)
    if not state then return notify(player,false,"missing_portal") end
    if not slot then
        for index=1,4 do
            if state.slots[index] and state.slots[index].empty then slot=index;break end
        end
    end
    if not slot then return notify(player,false,"slots_full") end
    local ok,code=P.Actions.queue(player,object,"install",{itemId=itemId,slot=slot},function(success,result)
        notify(player,success,result)
    end)
    notify(player,ok,code)
end

function C.queueRemove(player,object,slot,itemId)
    local ok,code=P.Actions.queue(player,object,"remove",{slot=slot,itemId=itemId},function(success,result)
        notify(player,success,result)
    end)
    notify(player,ok,code)
end

-- The original picker is authoritative. This optional fallback is constrained
-- to actual opaque portal pixels, projected from that object's own tile.
function C.hitPortal(object,playerIndex,mouseX,mouseY)
    local visual=P.Visual
    if not visual or not visual.getMetadata or not visual.hitPixel or not object or not object:getSquare() then return false end
    local sprite=object:getSprite()
    local name=sprite and sprite:getName()
    local meta=name and visual.getMetadata(name)
    if not meta then return false end
    if object.getTargetAlpha and object:getTargetAlpha(playerIndex)<=0.05 then return false end
    local square=object:getSquare()
    local zoom=getCore():getZoom(playerIndex)
    if not zoom or zoom<=0 then return false end
    local projectedX=(IsoUtils.XToScreen(square:getX(),square:getY(),square:getZ(),0)-IsoCamera.getOffX(playerIndex))/zoom+IsoCamera.getScreenLeft(playerIndex)
    local projectedY=(IsoUtils.YToScreen(square:getX(),square:getY(),square:getZ(),0)-IsoCamera.getOffY(playerIndex))/zoom+IsoCamera.getScreenTop(playerIndex)
    local localX=math.floor((mouseX-projectedX)*zoom+meta.anchorX)
    local localY=math.floor((mouseY-projectedY)*zoom+meta.anchorY)
    if localX<0 or localY<0 or localX>=meta.width or localY>=meta.height then return false end
    return visual.hitPixel(name,localX,localY),projectedY
end

function C.findPortals(playerIndex,worldObjects,mouseX,mouseY)
    local found,seen={},{}
    local function add(object)
        if object and not seen[object] and P.Build.isPortal(object) then
            seen[object]=true;found[#found+1]=object
        end
    end
    if IsoObjectPicker and IsoObjectPicker.Instance then
        local picker=IsoObjectPicker.Instance
        -- Same direct IsoObject API used by the current native debug picker.
        -- ContextPick returns an opaque ClickObject, whose Java fields are not
        -- Lua properties; never dereference its .tile or invent a getter.
        add(picker:PickThumpable(mouseX,mouseY))
    end
    if #found>0 then return {found[1]} end
    local twoD=C.twoDFallbackAllowed(playerIndex)
    for _,object in ipairs(worldObjects or {}) do
        if P.Build.isPortal(object) and (not twoD or not P.Visual or not P.Visual.getMetadata or
            C.hitPortal(object,playerIndex,mouseX,mouseY)) then add(object) end
    end
    if #found>0 then return {found[1]} end
    if twoD and P.World and P.World.list and IsoUtils and IsoCamera then
        local player=getSpecificPlayer(playerIndex)
        local best,bestDepth
        for _,record in ipairs(P.World.list()) do
            if math.floor(player:getZ())==record.z then
                local object=P.World.findObject(record)
                if object then
                    local hit,depth=C.hitPortal(object,playerIndex,mouseX,mouseY)
                    if hit and (not best or (depth or 0)>(bestDepth or 0)) then best,bestDepth=object,depth end
                end
            end
        end
        add(best)
    end
    return found
end

local function submenu(context,label)
    local option=context:addOption(label,nil,nil)
    local menu=context:getNew(context)
    context:addSubMenu(option,menu)
    return option,menu
end

function C.addPortalOptions(player,context,object)
    P.World.register(object)
    local state=P.World.getSnapshot(object)
    if not state then return end
    context:addOption(text("OpenNamed",state.name or text("Name")),object,function(target) P.UI.open(player,target) end)
    if state.migrationRequired then
        if state.reason=="legacy_java_storage" or state.migrationError=="legacy_java_storage" then
            context:addOption(P.UI.resultText("legacy_java_storage"),nil,nil).notAvailable=true
            return
        end
        context:addOption(text("RecoverLegacy"),object,function(target)
            local ok,code=P.Actions.queue(player,target,"recoverLegacy",{},function(success,result) notify(player,success,result) end)
            notify(player,ok,code)
        end)
        return
    end
    local installOption,installMenu=submenu(context,text("InstallDirect"))
    local batteries=P.UI.collectBatteries(player:getInventory())
    local free=false
    for slot=1,4 do if state.slots[slot] and state.slots[slot].empty then free=true end end
    if not state.storageReady or state.pending or not free or #batteries==0 then
        installOption.notAvailable=true
        installMenu:addOption(P.UI.resultText(state.pending and "portal_busy" or not state.storageReady and (state.reason or "bridge_missing") or
            (not free and "slots_full" or "no_battery")),nil,nil).notAvailable=true
    else
        for _,battery in ipairs(batteries) do
            installMenu:addOption(P.UI.batteryLabel(battery),object,function(target,itemId) C.queueInstall(player,target,itemId) end,battery:getID())
        end
    end
    local removeOption,removeMenu=submenu(context,text("RemoveDirect"))
    local installed=0
    for slot=1,4 do
        local item=state.slots[slot]
        if item and item.itemId then
            installed=installed+1
            local label=text("RemoveSlotMenu",tostring(slot),item.name or item.type,tostring(math.floor((item.charge or 0)*100+0.5)))
            removeMenu:addOption(label,object,function(target,index,itemId) C.queueRemove(player,target,index,itemId) end,slot,item.itemId)
        end
    end
    if installed==0 or state.pending then removeOption.notAvailable=true end
end

function C.fillContext(playerIndex,context,worldObjects,test)
    if isClient() or isServer() then return end
    local player=getSpecificPlayer(playerIndex)
    if not player or player:isDead() then return end
    if P.Transfer.isBusy(player) then
        if test then
            if ISWorldObjectContextMenu then ISWorldObjectContextMenu.Test=true end
            return true
        end
        context:addOption(text("RetryRecovery"),player,function(target) P.Transfer.retryRecovery(target) end)
        return
    end
    local mouseX=(context and context.requestX) or getMouseX()
    local mouseY=(context and context.requestY) or getMouseY()
    local found=C.findPortals(playerIndex,worldObjects,mouseX,mouseY)
    if test then
        local present=#found>0
        if present and ISWorldObjectContextMenu then ISWorldObjectContextMenu.Test=true end
        return present
    end
    for _,object in ipairs(found) do C.addPortalOptions(player,context,object) end
end

if not C.eventsInstalled then
    C.eventsInstalled=true
    Events.OnFillWorldObjectContextMenu.Add(C.fillContext)
end
return C
