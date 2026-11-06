require "SuQingPortals/Core"
require "SuQingPortals/BatterySlots"
require "ISUI/ISInventoryPage"
require "ISUI/ISInventoryPaneContextMenu"
require "TimedActions/ISInventoryTransferAction"
require "TimedActions/ISTransferAction"

local P=SuQingPortals
P.InventoryGuard=P.InventoryGuard or {}
local G=P.InventoryGuard
G.wrappers=G.wrappers or {}
G.reported=G.reported or {}
local function warn(key,detail)
    if G.reported[key] then return end
    G.reported[key]=true
    print("[SuQingPortals] inventory integration unavailable ("..key.."): "..tostring(detail))
end

function G.isInternal(container)
    if not container then return false end
    local slots=P.BatterySlots
    if not slots or not slots.isInternalContainer then
        warn("slot_predicate","BatterySlots.isInternalContainer is missing")
        return false
    end
    return slots.isInternalContainer(container)==true
end

function G.blocksNativeTransfer(container)
    if G.isInternal(container) then return true end
    -- A version-1 gate with a pending trip must retain its original legacy
    -- container until that receipt settles. Lock only that exact owned bank;
    -- do not hide every legacy/foreign container while recovering an old save.
    local parent=container and container.getParent and container:getParent()
    local data=parent and parent.getModData and parent:getModData().SuQingPortals
    return data~=nil and data.schema==1 and type(data.id)=="string"
        and data.pendingToken~=nil and parent.getContainer~=nil and parent:getContainer()==container
end

local function repairSelection(page,fallback,stage)
    local pane=page.inventoryPane
    if not pane then warn("inventory_pane","page.inventoryPane is missing");return end
    local changed=false
    if G.isInternal(pane.inventory) then pane.inventory=fallback and fallback.inventory;pane.selected={};changed=true end
    if G.isInternal(pane.lastinventory) then pane.lastinventory=fallback and fallback.inventory;changed=true end
    if G.isInternal(page.inventory) then page.inventory=fallback and fallback.inventory;changed=true end
    if G.isInternal(page.forceSelectedContainer) then page.forceSelectedContainer=nil;page.forceSelectedContainerTime=0 end
    if page.selectedButton and G.isInternal(page.selectedButton.inventory) then page.selectedButton=nil end
    if changed and fallback then
        page.inventory=pane.inventory
        page.selectedButton=fallback
        page.title=fallback.name
        page.capacity=fallback.capacity
        pane.lastinventory=pane.inventory
        if stage=="end" and pane.refreshContainer then pane:refreshContainer() end
        if stage=="end" and page.refreshWeight then page:refreshWeight() end
        if stage=="end" and page.updateItemCount then page:updateItemCount() end
    end
    if page.backpackChoice~=nil then
        for index,button in ipairs(page.backpacks) do
            if button.inventory==pane.inventory then page.backpackChoice=index;break end
        end
        if page.backpackChoice>#page.backpacks then page.backpackChoice=1 end
    end
end

function G.filterPage(page,stage)
    if stage~="buttonsAdded" and stage~="end" then return end
    if not page or type(page.backpacks)~="table" then warn("backpacks","unsupported inventory container rail");return end
    if not page.inventoryPane then warn("inventory_pane","page.inventoryPane is missing");return end
    local removed=false
    for index=#page.backpacks,1,-1 do
        local button=page.backpacks[index]
        if G.isInternal(button.inventory) then
            table.remove(page.backpacks,index)
            if page.containerButtonPanel and page.containerButtonPanel.removeChild then
                page.containerButtonPanel:removeChild(button)
                page.buttonPool=page.buttonPool or {}
                page.buttonPool[#page.buttonPool+1]=button
            else
                warn("container_panel","cannot detach an internal-bank container button")
                if button.setVisible then button:setVisible(false) end
            end
            removed=true
        end
    end
    local fallback
    for _,button in ipairs(page.backpacks) do
        if not fallback or button.inventory:getType()=="floor" then fallback=button end
        if button.inventory==page.inventoryPane.inventory and not G.isInternal(button.inventory) then
            fallback=button;break
        end
    end
    repairSelection(page,fallback,stage)
    if not removed then return end
    if page.cleanUIUpdateContainerPanelMetrics then page:cleanUIUpdateContainerPanelMetrics() end
    local bottom=0
    for index,button in ipairs(page.backpacks) do
        local x,y
        if page.cleanUIGetContainerButtonPosition then x,y=page:cleanUIGetContainerButtonPosition(index)
        elseif type(page.buttonSize)=="number" then x,y=0,(index-1)*page.buttonSize-1
        else warn("button_layout","unknown container rail layout") end
        if x and button.setX and button.setY then button:setX(x);button:setY(y) end
        if button.getBottom then bottom=math.max(bottom,button:getBottom()) end
    end
    if page.containerButtonPanel and page.containerButtonPanel.setScrollHeight then
        page.containerButtonPanel:setScrollHeight(bottom+(page.padding or 0))
    end
end

function G.filterContainers(list)
    if not list then return list end
    if list.size and list.get and ArrayList and ArrayList.new then
        local filtered=ArrayList.new()
        for index=0,list:size()-1 do
            local container=list:get(index)
            if not G.blocksNativeTransfer(container) then filtered:add(container) end
        end
        return filtered
    end
    if type(list)=="table" then
        local filtered={}
        for _,container in ipairs(list) do if not G.blocksNativeTransfer(container) then filtered[#filtered+1]=container end end
        warn("lua_container_list","non-native table result filtered as a plain array")
        return filtered
    end
    warn("container_list","unrecognized nearby-container list; native transfer guards remain active")
    return list
end

local function install(owner,name,key,wrapperFactory)
    if not owner or type(owner[name])~="function" then warn(key,"required method is missing");return false end
    if owner[name]==G.wrappers[key] then return true end
    local wrapper=wrapperFactory(owner[name])
    G.wrappers[key]=wrapper
    owner[name]=wrapper
    return true
end

function G.install()
    install(ISInventoryPaneContextMenu,"getContainers","nearby_materials",function(previous)
        return function(character,...) return G.filterContainers(previous(character,...)) end
    end)
    install(ISInventoryPage,"selectContainer","select_container",function(previous)
        return function(page,button,...)
            if button and G.isInternal(button.inventory) then return false end
            return previous(page,button,...)
        end
    end)
    install(ISInventoryPage,"setNewContainer","set_container",function(previous)
        return function(page,container,...)
            if G.isInternal(container) then return false end
            return previous(page,container,...)
        end
    end)
    install(ISInventoryTransferAction,"isValid","native_transfer_valid",function(previous)
        return function(action,...)
            if G.blocksNativeTransfer(action.srcContainer) or G.blocksNativeTransfer(action.destContainer) then return false end
            return previous(action,...)
        end
    end)
    install(ISInventoryTransferAction,"transferItem","native_transfer_final",function(previous)
        return function(action,item,...)
            if G.blocksNativeTransfer(action.srcContainer) or G.blocksNativeTransfer(action.destContainer) then return nil end
            return previous(action,item,...)
        end
    end)
    install(ISTransferAction,"transferItem","shared_transfer_final",function(previous)
        return function(action,character,item,source,destination,...)
            if G.blocksNativeTransfer(source) or G.blocksNativeTransfer(destination) then return item end
            return previous(action,character,item,source,destination,...)
        end
    end)
end

if not G.eventsInstalled then
    G.eventsInstalled=true
    if Events and Events.OnRefreshInventoryWindowContainers then
        Events.OnRefreshInventoryWindowContainers.Add(G.filterPage)
    else warn("refresh_event","OnRefreshInventoryWindowContainers is missing") end
    if Events and Events.OnGameStart then Events.OnGameStart.Add(G.install) end
end
G.install()
return G
