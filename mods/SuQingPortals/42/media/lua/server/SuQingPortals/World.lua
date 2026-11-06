require "SuQingPortals/Core"
require "SuQingPortals/BatterySlots"
SuQingPortals = SuQingPortals or {}
local SP, Core = SuQingPortals, SuQingPortals.Core
local Slots = SuQingPortals.BatterySlots
local World = {}
SP.World = World
World.MODDATA_KEY = "SuQingPortals"
World.STORE_KEY = "SuQingPortals.World"
World.CONTAINER_TYPE = Slots.CONTAINER_TYPE
World.isInternalContainer = Slots.isInternalContainer
local runtime = { objects = {}, clocks = {}, ticks = 0 }

local function supported()
    return not ((isClient and isClient()) or (isServer and isServer()))
end

local function store()
    local data = ModData.getOrCreate(World.STORE_KEY)
    if not data.schema or data.schema < Core.SCHEMA then data.schema = Core.SCHEMA end
    data.nextId = data.nextId or 1
    data.nextTransfer = data.nextTransfer or 1
    data.nextPlayer = data.nextPlayer or 1
    data.portals = data.portals or {}
    data.pending = data.pending or {}
    data.completed = data.completed or {}
    return data
end

local function hours()
    return getGameTime():getWorldAgeHours()
end

local function chargeSnapshot(items)
    local before = {}
    for slot = 1, 4 do if items[slot] then before[slot] = items[slot]:getCurrentUsesFloat() end end
    return before
end

local function persistMutation(object, items, before)
    if object:getModData().SuQingPortals.schema ~= 3 then return true end
    local saved, code = Slots.persist(object, items)
    if saved then return true end
    local restored = true
    for slot = 1, 4 do
        if items[slot] and before[slot] ~= nil then
            local ok = pcall(function() items[slot]:setUsedDelta(before[slot]) end)
            if not ok or math.abs(items[slot]:getCurrentUsesFloat() - before[slot]) > Core.EPSILON then restored = false end
        end
    end
    return false, restored and code or "battery_rollback_failed"
end

local function objectData(object)
    if not object or not object.getModData then return nil end
    return object:getModData()[World.MODDATA_KEY]
end

local function dirty(object)
    if object and object.transmitModData then object:transmitModData() end
    if object and object.getContainer and object:getContainer() then
        local container = object:getContainer()
        if container.setDrawDirty then container:setDrawDirty(true) end
    end
end

local function spriteName(object)
    local sprite = object and object.getSprite and object:getSprite()
    return sprite and sprite:getName() or ""
end

function World.isPortal(object)
    if objectData(object) then return true end
    return string.match(spriteName(object), "^suqing_portal_01_%d+$") ~= nil
end

local function getSquare(record)
    return getCell():getGridSquare(record.x, record.y, record.z)
end

function World.findObject(recordOrId)
    local record = type(recordOrId) == "table" and recordOrId or store().portals[recordOrId]
    if not record or record.removed then return nil end
    local square = getSquare(record)
    if not square then runtime.objects[record.id] = nil; runtime.clocks[record.id] = nil; Slots.forget(record.id); return nil end
    local objects = square:getObjects()
    for index = 0, objects:size() - 1 do
        local object = objects:get(index)
        local data = objectData(object)
        if data and data.id == record.id then runtime.objects[record.id] = object; return object end
    end
    runtime.objects[record.id] = nil
    runtime.clocks[record.id] = nil
    return nil
end

function World.Container(object)
    -- Compatibility accessor for legacy recovery only; never creates storage.
    return object and object:getContainer() or nil
end

function World.AcceptBattery(container, item)
    return false
end

function World.validateContainer(object)
    if not objectData(object) then return false, "missing_portal" end
    local items, code = Slots.ensure(object)
    return items ~= nil, code
end

-- Reconcile the real container against saved slot IDs. External inventory
-- transfers may move an item; stale IDs never fabricate a battery or charge.
function World.batteries(object)
    local data = objectData(object)
    if not data then return {} end
    -- Old transfer receipts must settle against their original old container
    -- before migration takes ownership. No replacement items are constructed.
    if data.schema == 1 and data.pendingToken then return Slots.legacyBatteries(object) end
    local items = Slots.ensure(object)
    return items or {}
end

local function countBatteries(items)
    local count = 0
    for slot = 1, Core.SLOT_COUNT do if items[slot] then count = count + 1 end end
    return count
end

local function visual(object)
    local data = objectData(object)
    if not data then return end
    local items, mask = World.batteries(object), 0
    for slot = 1, 4 do if items[slot] then mask = mask + 2 ^ (slot - 1) end end
    local index = mask * 4 + (data.facing or 0)
    local name = "suqing_portal_01_" .. tostring(index)
    if spriteName(object) ~= name and object.setSpriteFromName then object:setSpriteFromName(name) end
    if SP.Visual and SP.Visual.apply then SP.Visual.apply(object, mask) end
end

function World.register(object, options)
    if not supported() then return nil, "singleplayer_only" end
    if not object or not object:getSquare() then return nil, "missing_portal" end
    options = options or {}
    local database, data = store(), objectData(object)
    local square = object:getSquare()
    if data and data.id then
        local existing = database.portals[data.id]
        if existing and (existing.x ~= square:getX() or existing.y ~= square:getY() or existing.z ~= square:getZ() or existing.removed) then
            return nil, "duplicate_portal_id"
        end
        if existing then
            local current = World.findObject(existing)
            if current and current ~= object then return nil, "duplicate_portal_id" end
        end
    else
        data = { schema = 1, slots = {}, facing = tonumber(string.match(spriteName(object), "_(%d+)$")) or 0 }
        data.facing = data.facing % 4
        repeat
            data.id = "SQP-" .. tostring(database.nextId)
            database.nextId = database.nextId + 1
        until not database.portals[data.id]
        object:getModData()[World.MODDATA_KEY] = data
    end
    local record = database.portals[data.id] or {}
    record.id, record.schema = data.id, Core.SCHEMA
    record.x, record.y, record.z = square:getX(), square:getY(), square:getZ()
    record.facing = data.facing or 0
    record.name = record.name or options.name or record.id
    record.removed = false
    database.portals[data.id] = record
    runtime.objects[data.id] = object
    if data.pendingToken then
        local completed = database.completed[data.pendingToken]
        if type(completed) == "table" then
            local items = World.batteries(object)
            local before = chargeSnapshot(items)
            local settled, code = Core.settle(items, completed.receipt, completed.phase == "committed")
            if settled then settled, code = persistMutation(object, items, before) end
            if settled then
                data.pendingToken, data.pendingTransfer = nil, nil
                completed.sourceSettled = true
            else data.recoveryError = code end
        elseif not database.pending[data.pendingToken] and data.pendingTransfer then
            -- The object chunk may have been saved after the global journal.
            database.pending[data.pendingToken] = data.pendingTransfer
        end
    end
    Slots.ensure(object)
    visual(object)
    dirty(object)
    return Core.copyRecord(record)
end

World.RegisterObject = World.register

function World.OnCreate(params)
    local object = params
    if type(params) == "table" and not params.getSquare then object = params.thumpable or params.object end
    if object then return World.register(object) end
end

function World.list()
    local list = {}
    for _, record in pairs(store().portals) do
        if not record.removed then list[#list + 1] = Core.copyRecord(record) end
    end
    table.sort(list, function(a, b) return a.id < b.id end)
    return list
end

function World.List(player, source)
    return World.list()
end

function World.localPower(object)
    local square = object and object:getSquare()
    if not square then return nil end
    if square.haveElectricity and square:haveElectricity() then return true end
    if square.hasGridPower and square:hasGridPower() and square.getRoom and square:getRoom() then return true end
    return false
end

-- Display-only inspection of this loaded square. The charging predicate above
-- remains unchanged. getGenerator() only finds an object on the same tile;
-- the native chunk coverage query also recognizes generators on other tiles.
function World.powerInfo(object)
    local info = { loaded = false, source = "unknown" }
    local ok, square = pcall(function() return object and object:getSquare() end)
    if not ok or not square then return info end
    local loaded, current = pcall(function()
        local cell = getCell and getCell()
        return cell and cell:getGridSquare(square:getX(), square:getY(), square:getZ())
    end)
    if not loaded or current ~= square then return info end
    info.loaded = true
    local read, regional, grid = pcall(function()
        local areaPower, gridPower
        if square.haveElectricity then areaPower = square:haveElectricity() == true end
        if square.hasGridPower and square.getRoom then
            gridPower = square:hasGridPower() and square:getRoom() ~= nil
        end
        return areaPower, gridPower
    end)
    if not read then return info end
    info.grid = grid
    if regional == true or grid == true then info.powered = true
    elseif regional ~= nil and grid ~= nil then info.powered = false end
    if regional == false then info.generator = false end
    if regional then
        local checked, covered = pcall(function()
            local chunk = square.getChunk and square:getChunk()
            if chunk and chunk.isGeneratorPoweringSquare then
                return chunk:isGeneratorPoweringSquare(square:getX(), square:getY(), square:getZ())
            end
        end)
        if checked and type(covered) == "boolean" then info.generator = covered end
    end
    info.area = regional == true and info.generator ~= true
    if grid and info.generator then info.source = "grid_generator"
    elseif grid and info.area then info.source = "grid_area"
    elseif grid then info.source = "grid"
    elseif info.generator then info.source = "generator"
    elseif info.powered then info.source = "area"
    elseif info.powered == false then info.source = "none" end
    return info
end

function World.getSnapshot(object)
    local data = objectData(object)
    if not data then return nil end
    local record = store().portals[data.id]
    if not record then return nil end
    local snapshot, items = Core.copyRecord(record), World.batteries(object)
    snapshot.slots = {}
    for slot = 1, Core.SLOT_COUNT do
        local item = items[slot]
        snapshot.slots[slot] = item and { itemId = item:getID(), type = item:getFullType(), name = item:getName(),
            charge = Core.chargeOf(item), condition = item:getCondition(), conditionMax = item.getConditionMax and item:getConditionMax() or 100 } or { empty = true, charge = 0 }
    end
    snapshot.slotCount = Core.SLOT_COUNT
    snapshot.batteryCount = countBatteries(items)
    snapshot.slotMask = 0
    for slot = 1, 4 do if items[slot] then snapshot.slotMask = snapshot.slotMask + 2 ^ (slot - 1) end end
    snapshot.totalCharge = Core.totalCharge(items)
    snapshot.cost = Core.getTransferCost()
    snapshot.pending = data.pendingToken ~= nil
    snapshot.pendingToken = data.pendingToken
    snapshot.powered = World.localPower(object)
    snapshot.powerInfo = World.powerInfo(object)
    snapshot.chargeError = data.chargeError
    snapshot.chargePerHour = SandboxVars and SandboxVars.SuQingPortals and tonumber(SandboxVars.SuQingPortals.ChargePerHour) or Core.DEFAULT_CHARGE_PER_HOUR
    snapshot.loaded = true
    local valid, validationCode = World.validateContainer(object)
    if World.findObject(record) ~= object then valid, validationCode = false, "duplicate_portal_id" end
    snapshot.invalidContainer = not valid
    snapshot.containerError = validationCode
    snapshot.storageReady = valid
    snapshot.migrationRequired = data.schema ~= 3 or data.migrationJournal ~= nil
    snapshot.migrationError = data.migrationError
    snapshot.reason = validationCode or (data.pendingToken and "portal_busy") or nil
    snapshot.legacyItems = {}
    if data.schema == 1 then
        for _, item in ipairs(Slots.legacyItems(object)) do
            snapshot.legacyItems[#snapshot.legacyItems + 1] = { itemId = item:getID(), type = item:getFullType(), name = item:getName(),
                charge = Core.isBattery(item) and Core.chargeOf(item) or nil, condition = item:getCondition() }
        end
    end
    snapshot.canTeleport = valid and snapshot.pairId ~= nil and not snapshot.pending and snapshot.totalCharge + Core.EPSILON >= snapshot.cost
    return snapshot
end

World.State = World.getSnapshot

local function validateAction(player, object)
    if not supported() then return false, "singleplayer_only" end
    local data = objectData(object)
    if not data or not store().portals[data.id] then return false, "missing_portal" end
    if World.findObject(store().portals[data.id]) ~= object then return false, "duplicate_portal_id" end
    if object.getObjectIndex and object:getObjectIndex() < 0 then return false, "missing_portal" end
    if not player or not player.getSquare or not player:getSquare() then return false, "missing_player" end
    if player.isDead and player:isDead() then return false, "player_dead" end
    if not Core.near({ x = player:getX(), y = player:getY(), z = player:getZ() }, store().portals[data.id], 3) then return false, "too_far" end
    if data.pendingToken then return false, "portal_busy" end
    return true
end

local function findInventoryItem(player, id)
    local inventory = player:getInventory()
    if inventory.getItemWithIDRecursiv then return inventory:getItemWithIDRecursiv(tonumber(id)) end
    return inventory:getItemWithID(tonumber(id))
end

function World.Install(player, object, itemOrId, slot)
    local ok, code = validateAction(player, object)
    if not ok then return false, code end
    local valid, invalidCode = World.validateContainer(object)
    if not valid then return false, invalidCode end
    local item = itemOrId
    if type(itemOrId) == "number" or type(itemOrId) == "string" then item = findInventoryItem(player, itemOrId) end
    if not Core.isBattery(item) then return false, "invalid_battery" end
    local inventory, original = player:getInventory(), item:getContainer()
    if not original or not inventory:containsRecursive(item) then return false, "battery_not_owned" end
    local data, items = objectData(object), World.batteries(object)
    for installedSlot = 1, Core.SLOT_COUNT do
        if items[installedSlot] and items[installedSlot]:getID() == item:getID() then return false, "duplicate_battery_id" end
    end
    slot = tonumber(slot)
    if not slot then for candidate = 1, Core.SLOT_COUNT do if not items[candidate] then slot = candidate; break end end end
    if not slot or slot < 1 or slot > Core.SLOT_COUNT or slot ~= math.floor(slot) then return false, "invalid_slot" end
    if items[slot] then return false, "slot_occupied" end
    local nextItems = {}
    for index = 1, 4 do nextItems[index] = items[index] end
    nextItems[slot] = item
    local prepared, prepareError = Slots.prepare(object, nextItems, true)
    if not prepared then return false, prepareError end
    local removed = pcall(function() original:Remove(item) end)
    if not removed or original:contains(item) then
        if not original:contains(item) then original:AddItem(item) end
        return false, "battery_move_failed"
    end
    local container = object:getContainer()
    local added = pcall(function() container:AddItem(item) end)
    if not added or not container:contains(item) then
        if container:contains(item) then container:Remove(item) end
        original:AddItem(item)
        return false, "battery_move_failed"
    end
    local moved, moveError = Slots.commit(object, nextItems, prepared)
    if not moved then
        container:Remove(item)
        original:AddItem(item)
        return false, moveError or "battery_move_failed"
    end
    runtime.clocks[data.id] = nil
    visual(object); dirty(object)
    return true, "installed", World.State(object)
end

function World.Remove(player, object, slot)
    local ok, code = validateAction(player, object)
    if not ok then return false, code end
    slot = tonumber(slot)
    if not slot or slot < 1 or slot > Core.SLOT_COUNT or slot ~= math.floor(slot) then return false, "invalid_slot" end
    local valid, invalidCode = World.validateContainer(object)
    if not valid then return false, invalidCode end
    local items = World.batteries(object)
    local item = items[slot]
    if not item then return false, "slot_empty" end
    local inventory = player:getInventory()
    local nextItems = {}
    for index = 1, 4 do if index ~= slot then nextItems[index] = items[index] end end
    local prepared, prepareError = Slots.prepare(object, nextItems, false)
    if not prepared then return false, prepareError end
    local container = object:getContainer()
    local removed = pcall(function() container:Remove(item) end)
    if not removed or container:contains(item) then
        if not container:contains(item) then container:AddItem(item) end
        return false, "battery_move_failed"
    end
    local moved = pcall(function() inventory:AddItem(item) end)
    if not moved or not inventory:contains(item) then
        if inventory:contains(item) then inventory:Remove(item) end
        container:AddItem(item)
        return false, "battery_move_failed"
    end
    local committed, commitError = Slots.commit(object, nextItems, prepared)
    if not committed then inventory:Remove(item); container:AddItem(item); return false, commitError end
    runtime.clocks[objectData(object).id] = nil
    visual(object); dirty(object)
    return true, "removed", World.State(object)
end

function World.Rename(player, object, name)
    local ok, code = validateAction(player, object)
    if not ok then return false, code end
    -- Avoid Kahlua's pattern replacement for Unicode names. Its Java-backed
    -- string.byte returns full UTF-16 code units; preserving each substring
    -- retains Chinese text and surrogate pairs without an encoding conversion.
    name = tostring(name or "")
    local clean = {}
    for index = 1, #name do
        local codePoint = string.byte(name, index)
        if codePoint == 0 then return false, "invalid_name" end
        if codePoint >= 32 and codePoint ~= 127 then clean[#clean + 1] = name:sub(index, index) end
    end
    name = table.concat(clean)
    while name:sub(1, 1) == " " do name = name:sub(2) end
    while name:sub(-1) == " " do name = name:sub(1, -2) end
    -- Reject oversized UTF-8 intact; byte truncation can cut a Chinese codepoint.
    if name == "" or #name > 240 then return false, "invalid_name" end
    store().portals[objectData(object).id].name = name
    dirty(object)
    return true, "renamed"
end

function World.recoverLegacy(player, object, itemId)
    local ok, code = validateAction(player, object)
    if not ok then return false, code end
    local data = objectData(object)
    if data.schema ~= 1 then return false, data.schema == 2 and "legacy_java_storage" or "migration_required" end
    local inventory = player:getInventory()
    local selected = {}
    for _, item in ipairs(Slots.legacyItems(object)) do
        if itemId == nil or item:getID() == tonumber(itemId) then selected[#selected + 1] = item end
    end
    if #selected == 0 and itemId ~= nil then return false, "slot_empty" end
    local moved, originalOwners = {}, {}
    for _, item in ipairs(selected) do
        local container = item:getContainer()
        originalOwners[item] = container
        container:Remove(item)
        local added = pcall(function() inventory:AddItem(item) end)
        if container:contains(item) or not added or not inventory:contains(item) then
            if inventory:contains(item) then inventory:Remove(item) end
            if not container:contains(item) then container:AddItem(item) end
            for _, previous in ipairs(moved) do inventory:Remove(previous); originalOwners[previous]:AddItem(previous) end
            return false, "battery_move_failed"
        end
        moved[#moved + 1] = item
    end
    Slots.ensure(object)
    visual(object); dirty(object)
    return true, "legacy_recovered", World.State(object)
end

function World.retryMigration(player, object)
    local ok, code = validateAction(player, object)
    if not ok then return false, code end
    local items, failure = Slots.ensure(object)
    if not items then return false, failure end
    visual(object); dirty(object)
    return true, "migration_completed", World.State(object)
end

function World.Unpair(player, object)
    local ok, code = validateAction(player, object)
    if not ok then return false, code end
    local record = store().portals[objectData(object).id]
    local other = record.pairId and store().portals[record.pairId]
    if other then
        local otherObject = World.findObject(other)
        if otherObject and objectData(otherObject).pendingToken then return false, "portal_busy" end
        if other.pairId == record.id then other.pairId = nil end
    end
    record.pairId = nil
    dirty(object)
    return true, "unpaired"
end

function World.Pair(player, object, targetId)
    local ok, code = validateAction(player, object)
    if not ok then return false, code end
    local database, data = store(), objectData(object)
    local target = database.portals[targetId]
    if not target or target.removed then return false, "missing_target" end
    if targetId == data.id then return false, "same_portal" end
    local source = database.portals[data.id]
    if source.pairId and source.pairId ~= targetId or target.pairId and target.pairId ~= data.id then return false, "already_paired" end
    local targetObject = World.findObject(target)
    if targetObject and objectData(targetObject).pendingToken then return false, "portal_busy" end
    source.pairId, target.pairId = targetId, data.id
    dirty(object)
    return true, "paired"
end

local function playerKey(player)
    local data, database = player:getModData(), store()
    if not data.SuQingPortalsPlayerId then
        local candidate, used
        repeat
            candidate = "SQPPLAYER-" .. tostring(database.nextPlayer)
            database.nextPlayer = database.nextPlayer + 1
            used = false
            for _, ticket in pairs(database.pending) do
                if ticket.playerKey == candidate then used = true; break end
            end
            if not used then
                for _, ticket in pairs(database.completed) do
                    if type(ticket) == "table" and ticket.playerKey == candidate then used = true; break end
                end
            end
        until not used
        data.SuQingPortalsPlayerId = candidate
    end
    return data.SuQingPortalsPlayerId
end

function World.getPending(player)
    if not player then return nil end
    local marker = player:getModData().SuQingPortalsPending
    if marker and store().pending[marker.token] and store().pending[marker.token].playerKey == playerKey(player) then
        return store().pending[marker.token]
    end
    for _, ticket in pairs(store().pending) do
        if ticket.playerKey == playerKey(player) then return ticket end
    end
    return nil
end

function World.reserveTeleport(player, object)
    local ok, code = validateAction(player, object)
    if not ok then return nil, code end
    local valid, invalidCode = World.validateContainer(object)
    if not valid then return nil, invalidCode end
    if World.getPending(player) then return nil, "transfer_pending" end
    local database, data = store(), objectData(object)
    local source = database.portals[data.id]
    local target = source.pairId and database.portals[source.pairId]
    if not target or target.removed or target.pairId ~= source.id then return nil, "missing_target" end
    local items = World.batteries(object)
    local cost = Core.getTransferCost()
    local receipt, failure = Core.planDebit(items, cost)
    if not receipt then return nil, failure end
    local token
    repeat
        token = "SQPT-" .. tostring(database.nextTransfer)
        database.nextTransfer = database.nextTransfer + 1
    until not database.pending[token] and not database.completed[token]
    local ticket = { token = token, sourceId = source.id, targetId = target.id, playerKey = playerKey(player),
        playerNum = player:getPlayerNum(),
        origin = { x = player:getX(), y = player:getY(), z = player:getZ() },
        target = Core.copyRecord(target), cost = cost, receipt = receipt, phase = "prepared", created = hours() }
    -- Journal first; if a subsequent write fails or a save occurs between
    -- files, recovery recognizes either before/after charge on each instance.
    database.pending[token], data.pendingToken = ticket, token
    data.pendingTransfer = ticket
    player:getModData().SuQingPortalsPending = { token = token, sourceId = source.id, targetId = target.id }
    dirty(object)
    local before = chargeSnapshot(items)
    local debited, debitFailure = Core.settle(items, receipt, true)
    if debited then debited, debitFailure = persistMutation(object, items, before) end
    if not debited then
        ticket.phase, ticket.failure = "recovery_required", debitFailure
        return nil, debitFailure
    end
    ticket.phase = "debited"
    dirty(object)
    return ticket
end

World.BeginTransfer = World.reserveTeleport

local function finish(player, token, success, reason)
    local database = store()
    local ticket = database.pending[token]
    if not ticket then
        if database.completed[token] then return true, "already_finished" end
        return false, "missing_transfer"
    end
    if not player or ticket.playerKey ~= playerKey(player) then return false, "wrong_player" end
    local object = World.findObject(ticket.sourceId)
    if not object and not success then ticket.phase = "recovery_required"; return false, "source_not_loaded" end
    if object then
        local items = World.batteries(object)
        local before = chargeSnapshot(items)
        local settled, code = Core.settle(items, ticket.receipt, success)
        if settled then settled, code = persistMutation(object, items, before) end
        if not settled then ticket.phase, ticket.failure = "recovery_required", code; return false, code end
        objectData(object).pendingToken, objectData(object).pendingTransfer = nil, nil
    end
    ticket.phase, ticket.reason = success and "committed" or "refunded", reason
    ticket.sourceSettled = object ~= nil
    database.completed[token] = ticket
    database.pending[token] = nil
    player:getModData().SuQingPortalsPending = nil
    runtime.clocks[ticket.sourceId] = nil
    dirty(object)
    if object then Slots.ensure(object); visual(object); dirty(object) end
    -- Bound successful receipts; pending records are never pruned automatically.
    local count = 0
    for _ in pairs(database.completed) do count = count + 1 end
    if count > 32 then
        local oldest
        for completed, completion in pairs(database.completed) do
            local number = tonumber(string.match(completed, "(%d+)$")) or 0
            if type(completion) ~= "table" or completion.sourceSettled then
                if not oldest or number < oldest.number then oldest = { token = completed, number = number } end
            end
        end
        if oldest then database.completed[oldest.token] = nil end
    end
    return true, ticket.phase
end

World.FinishTransfer = finish

function World.commitTeleport(ticket, player)
    player = player or (getSpecificPlayer and getSpecificPlayer(ticket.playerNum))
    return finish(player, ticket.token, true, "arrived")
end

function World.abortTeleport(ticket, player)
    player = player or (getSpecificPlayer and getSpecificPlayer(ticket.playerNum))
    return finish(player, ticket.token, false, "cancelled")
end

function World.recoverPlayer(player, verifiedOutcome)
    local ticket = World.getPending(player)
    if not ticket then
        -- A player-file marker can outlive the world journal after a completed
        -- save. Never manufacture a refund from the marker alone.
        player:getModData().SuQingPortalsPending = nil
        return true, "nothing_pending"
    end
    -- The client transfer service verifies the real target object/floor (or
    -- returns the player to the source) before supplying this outcome.
    if verifiedOutcome == "arrived" then return finish(player, ticket.token, true, "recovered_at_target") end
    if verifiedOutcome == "returned" then return finish(player, ticket.token, false, "recovered_at_source") end
    ticket.phase, ticket.failure = "recovery_required", "recovery_needs_verification"
    return false, ticket.failure
end

function World.command(player, object, command, args)
    args = args or {}
    if command == "install" then return World.Install(player, object, args.itemId, args.slot) end
    if command == "remove" then return World.Remove(player, object, args.slot) end
    if command == "pair" then return World.Pair(player, object, args.targetId) end
    if command == "unpair" then return World.Unpair(player, object) end
    if command == "rename" then return World.Rename(player, object, args.name) end
    if command == "recoverLegacy" or command == "return_legacy_batteries" then return World.recoverLegacy(player, object, args.itemId) end
    if command == "retry_migration" then return World.retryMigration(player, object) end
    return false, "unknown_command"
end

function World.chargeTick()
    if not supported() then return end
    local now = hours()
    local rate = Core.DEFAULT_CHARGE_PER_HOUR
    if SandboxVars and SandboxVars.SuQingPortals and tonumber(SandboxVars.SuQingPortals.ChargePerHour) then
        rate = math.max(0, tonumber(SandboxVars.SuQingPortals.ChargePerHour))
    end
    for id, record in pairs(store().portals) do
        local object = not record.removed and World.findObject(record) or nil
        if object then
            local data, previous = objectData(object), runtime.clocks[id]
            local powered = World.localPower(object) == true
            local valid = World.validateContainer(object)
            if valid and not data.pendingToken and powered and previous and previous.powered and now > previous.hours then
                local items = World.batteries(object)
                local before = chargeSnapshot(items)
                local amount, code = Core.charge(items, (now - previous.hours) * rate)
                if amount and amount > 0 then
                    local saved, persistError = persistMutation(object, items, before)
                    if not saved then amount, code = nil, persistError end
                end
                if amount == nil then data.chargeError = code
                elseif amount > 0 then data.chargeError = nil; dirty(object) end
            end
            runtime.clocks[id] = { hours = now, powered = powered }
            visual(object)
        else runtime.clocks[id] = nil end
    end
end

local function loadedSquare(square)
    if not supported() then return end
    local objects = square:getObjects()
    for index = 0, objects:size() - 1 do
        local object = objects:get(index)
        if World.isPortal(object) then
            local record = World.register(object)
            if record then runtime.clocks[record.id] = nil end
        end
    end
end

local function removedObject(object)
    local data = objectData(object)
    if not data or not supported() then return end
    local record = store().portals[data.id]
    if not record then return end
    -- Destruction must release the original battery instances, never recreate
    -- them from IDs or charge counters.
    local container, square = object:getContainer(), object:getSquare()
    if data.schema == 3 then
        -- Destruction returns every actual native original even if an outside
        -- modification invalidated its four-slot ID map. No item is recreated.
        local items = Slots.legacyItems(object)
        if square then
            for _, item in ipairs(items) do
                item:getContainer():Remove(item)
                square:AddWorldInventoryItem(item, 0.5, 0.5, 0)
            end
            Slots.release(object)
        end
    end
    if container and square then
        local items = container:getItems()
        for index = items:size() - 1, 0, -1 do
            local item = items:get(index)
            container:Remove(item)
            square:AddWorldInventoryItem(item, 0.5, 0.5, 0)
        end
    end
    record.removed = true
    if record.pairId and store().portals[record.pairId] then store().portals[record.pairId].pairId = nil end
    record.pairId = nil
    runtime.objects[data.id], runtime.clocks[data.id] = nil, nil
end

if Events then
    if Events.OnGameStart then Events.OnGameStart.Add(function()
        runtime.objects, runtime.clocks, runtime.ticks = {}, {}, 0
    end) end
    if Events.OnTick then Events.OnTick.Add(function()
        runtime.ticks = runtime.ticks + 1
        if runtime.ticks % 30 == 0 then World.chargeTick() end
    end) end
    if Events.LoadGridsquare then Events.LoadGridsquare.Add(loadedSquare)
    elseif Events.LoadGridSquare then Events.LoadGridSquare.Add(loadedSquare) end
    if Events.OnObjectAboutToBeRemoved then Events.OnObjectAboutToBeRemoved.Add(removedObject) end
    if Events.OnCreatePlayer then Events.OnCreatePlayer.Add(function(index, player)
        runtime.clocks = {}
    end) end
end

return World
