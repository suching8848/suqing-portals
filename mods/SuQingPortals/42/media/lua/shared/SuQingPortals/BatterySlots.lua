-- Pure Lua four-slot adapter. Real items remain in one native saveable container.
require "SuQingPortals/Core"
local SP, Core = SuQingPortals, SuQingPortals.Core
local Slots = { SCHEMA = 3, CONTAINER_TYPE = "suqingportal_internal" }
SP.BatterySlots = Slots
local function dataOf(object) return object and object:getModData().SuQingPortals end
local function owners()
    local database = ModData.getOrCreate("SuQingPortals.World")
    database.batteryOwners = database.batteryOwners or {}
    return database.batteryOwners
end

-- Predicate used by inventory/crafting UI guards; no creation/migration/mutation.
function Slots.isInternalContainer(container)
    if not container or not container.getParent or container:getType() ~= Slots.CONTAINER_TYPE then return false end
    local parent = container:getParent()
    if not parent or not parent.getModData or (parent.hasModData and not parent:hasModData()) then return false end
    local data = parent and dataOf(parent)
    return data ~= nil and data.schema == 3 and type(data.internalStorage) == "table"
        and data.internalStorage.schema == 3 and data.internalStorage.containerType == Slots.CONTAINER_TYPE
        and parent:getContainer() == container
end
Slots.isInternal = Slots.isInternalContainer
function Slots.AcceptItem(container, item) return false end
function Slots.available() return true end

function Slots.legacyContainers(object)
    local result = {}
    if object.getContainerCount and object.getContainerByIndex then
        for index=0,object:getContainerCount()-1 do result[#result+1]=object:getContainerByIndex(index) end
    elseif object:getContainer() then result[1]=object:getContainer() end
    return result
end
function Slots.legacyItems(object)
    local result = {}
    for _, container in ipairs(Slots.legacyContainers(object)) do
        local items=container:getItems()
        for index=0,items:size()-1 do result[#result+1]=items:get(index) end
    end
    return result
end
function Slots.legacyBatteries(object)
    local data, result, byId, used=dataOf(object),{},{},{}
    for _, item in ipairs(Slots.legacyItems(object)) do if Core.isBattery(item) then byId[tostring(item:getID())]=item end end
    for slot=1,4 do
        local item=data.slots and byId[tostring(data.slots[slot])]
        if item and not used[tostring(item:getID())] then result[slot]=item;used[tostring(item:getID())]=true end
    end
    for _, item in ipairs(Slots.legacyItems(object)) do
        if Core.isBattery(item) and not used[tostring(item:getID())] then
            for slot=1,4 do if not result[slot] then result[slot]=item;used[tostring(item:getID())]=true;break end end
        end
    end
    return result
end

local function validate(items, portalId, requiredContainer, allowContainer)
    local seen, ownership = {}, owners()
    for slot=1,4 do
        local item=items[slot]
        if item then
            if not Core.isBattery(item) then return false,"invalid_battery" end
            local key=tostring(item:getID())
            if seen[key] then return false,"duplicate_battery_id" end
            if ownership[key] and ownership[key]~=portalId then return false,"storage_conflict" end
            if not allowContainer and item:getContainer()~=requiredContainer then return false,"storage_conflict" end
            seen[key]=true
        end
    end
    return true
end

function Slots.prepare(object, items, allowContainer)
    local data=dataOf(object)
    if not data or data.schema~=3 or not Slots.isInternalContainer(object:getContainer()) then return nil,"storage_version" end
    local valid,code=validate(items,data.id,object:getContainer(),allowContainer)
    if not valid then return nil,code end
    local prepared={schema=3,containerType=Slots.CONTAINER_TYPE,revision=(data.internalStorage.revision or 0)+1,slots={}}
    for slot=1,4 do if items[slot] then prepared.slots[slot]=items[slot]:getID() end end
    return prepared
end

function Slots.commit(object, items, prepared)
    local data,container,ownership=dataOf(object),object:getContainer(),owners()
    if not data or not Slots.isInternalContainer(container) or not prepared or prepared.schema~=3 then return false,"storage_version" end
    local valid,code=validate(items,data.id,container,false)
    if not valid then return false,code end
    local actual,expected={},0
    for slot=1,4 do
        if items[slot] then actual[tostring(items[slot]:getID())]=true;expected=expected+1 end
        if prepared.slots[slot]~=(items[slot] and items[slot]:getID() or nil) then return false,"storage_conflict" end
    end
    local nativeItems=container:getItems()
    if nativeItems:size()~=expected then return false,"storage_conflict" end
    for index=0,nativeItems:size()-1 do if not actual[tostring(nativeItems:get(index):getID())] then return false,"storage_conflict" end end
    local previous=data.internalStorage
    for slot=1,4 do
        local id=previous.slots[slot]
        if id and ownership[tostring(id)]==data.id then ownership[tostring(id)]=nil end
    end
    data.internalStorage=prepared
    for slot=1,4 do if items[slot] then ownership[tostring(items[slot]:getID())]=data.id end end
    data.storageError,data.migrationError=nil,nil
    return true
end
function Slots.persist(object,items)
    local prepared,code=Slots.prepare(object,items,false)
    if not prepared then return false,code end
    return Slots.commit(object,items,prepared)
end

function Slots.read(object)
    local data,container=dataOf(object),object:getContainer()
    if not data or data.schema~=3 or not data.internalStorage or type(data.internalStorage.slots)~="table"
        or not Slots.isInternalContainer(container) then return nil,"storage_version" end
    if object.getContainerCount and object:getContainerCount()~=1 then return nil,"storage_conflict" end
    local storage=data.internalStorage
    if type(storage.revision)~="number" or storage.revision<0 or storage.revision~=math.floor(storage.revision) then return nil,"storage_corrupt" end
    for slot,id in pairs(storage.slots) do
        if type(slot)~="number" or slot<1 or slot>4 or slot~=math.floor(slot) or type(id)~="number" then return nil,"storage_corrupt" end
    end
    local byId,result,used={},{},{}
    local actual=container:getItems()
    if actual:size()>4 then return nil,"container_overflow" end
    for index=0,actual:size()-1 do
        local item=actual:get(index)
        if not Core.isBattery(item) then return nil,"container_foreign_item" end
        local key=tostring(item:getID())
        if byId[key] then return nil,"duplicate_battery_id" end
        byId[key]=item
    end
    for slot=1,4 do
        local id=storage.slots[slot]
        if id then
            local key=tostring(id)
            if used[key] or not byId[key] then return nil,"storage_conflict" end
            used[key]=true;result[slot]=byId[key]
        end
    end
    for id in pairs(byId) do if not used[id] then return nil,"storage_conflict" end end
    local valid,code=validate(result,data.id,container,false)
    if not valid then return nil,code end
    for slot=1,4 do if result[slot] then owners()[tostring(result[slot]:getID())]=data.id end end
    return result
end

local function protectJavaStorage(data)
    if data.migrationJournal or data.pendingToken or data.pendingTransfer then return true end
    local storage=data.batteryStorage
    if storage then
        if type(storage)~="table" or type(storage.slots)~="table" then return true end
        for _ in pairs(storage.slots) do return true end
    end
    return false
end

function Slots.migrate(object)
    local data=dataOf(object)
    if not data then return nil,"missing_portal" end
    if data.schema==3 then return Slots.read(object) end
    -- No Lua reconstruction of opaque native Java codec payloads. Preserve all
    -- old fields and require the old version to return originals first.
    if data.schema==2 and protectJavaStorage(data) then return nil,"legacy_java_storage" end
    if data.schema==2 and #Slots.legacyItems(object)>0 then return nil,"legacy_java_storage" end
    if data.schema~=1 and data.schema~=2 then return nil,"storage_version" end
    if data.pendingToken then return nil,"migration_pending_transfer" end
    if data.migrationJournal then return nil,"migration_failed" end
    local containers=Slots.legacyContainers(object)
    if #containers>1 then return nil,"migration_legacy_invalid" end
    local originals,seen=Slots.legacyItems(object),{}
    if #originals>4 then return nil,"migration_legacy_invalid" end
    for _,item in ipairs(originals) do
        local key=tostring(item:getID())
        if not Core.isBattery(item) or seen[key] then return nil,"migration_legacy_invalid" end
        seen[key]=true
    end
    local items=Slots.legacyBatteries(object)
    local valid,code=validate(items,data.id,nil,true)
    if not valid then return nil,code end
    local container=object:getContainer()
    -- A new/empty gate is the only path that creates storage. Existing v1
    -- gates keep their original native container and every original item.
    if not container then container=ItemContainer.new(Slots.CONTAINER_TYPE,object:getSquare(),object);object:setContainer(container) end
    local oldType=container:getType()
    local configured=pcall(function()
        container:setType(Slots.CONTAINER_TYPE)
        container:setCapacity(20)
        container:setExplored(true)
        container:setAcceptItemFunction("SuQingPortals.BatterySlots.AcceptItem")
    end)
    if not configured then pcall(function() container:setType(oldType) end);return nil,"migration_failed" end
    local prepared={schema=3,containerType=Slots.CONTAINER_TYPE,revision=0,slots={}}
    for slot=1,4 do if items[slot] then prepared.slots[slot]=items[slot]:getID() end end
    data.internalStorage,data.schema=prepared,3
    data.slots=nil
    data.batteryStorage=nil -- Only absent/empty schema2 data reaches here.
    for slot=1,4 do if items[slot] then owners()[tostring(items[slot]:getID())]=data.id end end
    return items
end
function Slots.ensure(object)
    local data=dataOf(object)
    local items,code=Slots.migrate(object)
    if items then
        local container=object:getContainer()
        -- ItemContainer's save format need not retain its Lua admission hook.
        -- Rebind only this exact marked store after every native reload.
        local admission="SuQingPortals.BatterySlots.AcceptItem"
        local bound=Slots.isInternalContainer(container) and pcall(function()
            if not container.getAcceptItemFunction or container:getAcceptItemFunction()~=admission then
                container:setAcceptItemFunction(admission)
            end
            if container.getAcceptItemFunction and container:getAcceptItemFunction()~=admission then
                error("internal admission hook readback mismatch")
            end
        end)
        if not bound then items,code=nil,"storage_conflict" end
    end
    if not items then data.storageError=code;data.migrationError=code
    else data.storageError,data.migrationError=nil,nil end
    return items,code
end
function Slots.forget(id) end -- Native container persistence owns reload/unload.
function Slots.release(object)
    local data,ownership=dataOf(object),owners()
    local storage=data.internalStorage
    if type(storage)=="table" and type(storage.slots)=="table" then
        for slot=1,4 do
            local id=storage.slots[slot]
            if id and ownership[tostring(id)]==data.id then ownership[tostring(id)]=nil end
        end
    end
    local revision=type(storage)=="table" and tonumber(storage.revision) or 0
    data.internalStorage={schema=3,containerType=Slots.CONTAINER_TYPE,revision=(revision or 0)+1,slots={}}
end
return Slots
