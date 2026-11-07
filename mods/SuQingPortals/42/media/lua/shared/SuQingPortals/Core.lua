-- SuQing's Portals: deterministic logic. No game/world initialization here.
SuQingPortals = SuQingPortals or {}
local Core = {}
SuQingPortals.Core = Core

Core.VERSION = "0.1.5"
Core.SCHEMA = 3
Core.SLOT_COUNT = 4
Core.TRANSFER_COST = 2.0
Core.DEFAULT_CHARGE_PER_HOUR = 0.5 -- Total battery-equivalents per portal/hour.
Core.EPSILON = 0.0001

function Core.getTransferCost()
    local value = SandboxVars and SandboxVars.SuQingPortals and tonumber(SandboxVars.SuQingPortals.TransferCost)
    -- Subtracting a nonfinite double from itself yields NaN. This also works
    -- in the game's Kahlua library without depending on math.huge.
    if type(value) ~= "number" or value - value ~= 0 then return Core.TRANSFER_COST end
    return math.max(0.5, math.min(4.0, value))
end

function Core.clampCharge(value)
    value = tonumber(value)
    if not value or value ~= value then return 0 end
    return math.max(0, math.min(1, value))
end

function Core.isBattery(item)
    if not item or not item.getFullType or not item.getCurrentUsesFloat or not item.setUsedDelta then return false end
    local fullType = item:getFullType()
    if fullType == "Base.CarBattery1" or fullType == "Base.CarBattery2" or fullType == "Base.CarBattery3" then return true end
    return ItemTag and ItemTag.CAR_BATTERY and item.hasTag and item:hasTag(ItemTag.CAR_BATTERY) or false
end

function Core.chargeOf(item)
    if not Core.isBattery(item) then return 0 end
    if item.getCondition and item:getCondition() <= 0 then return 0 end
    return Core.clampCharge(item:getCurrentUsesFloat())
end

function Core.totalCharge(items)
    local total = 0
    for slot = 1, Core.SLOT_COUNT do total = total + Core.chargeOf(items[slot]) end
    return total
end

local function writeCharge(item, value)
    item:setUsedDelta(value)
    local actual = Core.clampCharge(item:getCurrentUsesFloat())
    if math.abs(actual - value) > Core.EPSILON then error("battery charge readback mismatch") end
    return actual
end

function Core.planDebit(items, cost)
    cost = tonumber(cost) or Core.TRANSFER_COST
    if cost < 0 or cost ~= cost then return nil, "invalid_cost" end
    local seen = {}
    for slot = 1, Core.SLOT_COUNT do
        local item = items[slot]
        if item then
            if not Core.isBattery(item) then return nil, "invalid_battery" end
            local key = tostring(item:getID())
            if seen[key] then return nil, "duplicate_battery_id" end
            seen[key] = true
        end
    end
    if Core.totalCharge(items) + Core.EPSILON < cost then return nil, "insufficient_charge" end
    local receipt, remaining = {}, cost
    for slot = 1, Core.SLOT_COUNT do
        local item = items[slot]
        if item then
            local before = Core.chargeOf(item)
            local take = math.min(before, remaining)
            if take > 0 then
                receipt[#receipt + 1] = { slot = slot, itemId = item:getID(), before = before, after = math.max(0, before - take) }
                remaining = math.max(0, remaining - take)
            end
        end
    end
    return receipt
end

-- Absolute before/after values make recovery idempotent. A changed/missing
-- original instance is a conflict; recovery never creates a replacement item.
function Core.settle(items, receipt, commit)
    local desired = commit and "after" or "before"
    for _, entry in ipairs(receipt or {}) do
        local item = items[entry.slot]
        if not item or item:getID() ~= entry.itemId or not Core.isBattery(item) then return false, "battery_changed" end
        local current = Core.clampCharge(item:getCurrentUsesFloat())
        if math.abs(current - entry.before) > Core.EPSILON and math.abs(current - entry.after) > Core.EPSILON then
            return false, "battery_charge_changed"
        end
    end
    local changed = {}
    for _, entry in ipairs(receipt or {}) do
        local item = items[entry.slot]
        local before = Core.clampCharge(item:getCurrentUsesFloat())
        changed[#changed + 1] = { item = item, value = before }
        local ok = pcall(function() writeCharge(item, entry[desired]) end)
        if not ok then
            local rollbackOK = true
            for index = #changed, 1, -1 do
                local previous = changed[index]
                local restored = pcall(function() writeCharge(previous.item, previous.value) end)
                if not restored then rollbackOK = false end
            end
            return false, rollbackOK and "battery_write_failed" or "battery_rollback_failed"
        end
    end
    return true
end

function Core.debit(items, cost)
    local receipt, code = Core.planDebit(items, cost)
    if not receipt then return nil, code end
    local ok, failure = Core.settle(items, receipt, true)
    if not ok then return nil, failure, receipt end
    return receipt
end

function Core.refund(items, receipt)
    return Core.settle(items, receipt, false)
end

-- This distributes the portal's total charging rate across its installed
-- healthy batteries. It changes only UsedDelta, preserving identity/condition.
function Core.charge(items, amount, roundDown)
    amount = tonumber(amount) or 0
    if amount <= 0 or amount ~= amount then return 0 end
    local changed, total = {}, 0
    for slot = 1, Core.SLOT_COUNT do
        local item = items[slot]
        if Core.isBattery(item) and (not item.getCondition or item:getCondition() > 0) then
            local before = Core.clampCharge(item:getCurrentUsesFloat())
            local target = before + math.min(1 - before, amount - total)
            -- A source-limited payment cannot fund a native use rounded upward.
            if roundDown and target > before and item.getUseDelta then
                local step = item:getUseDelta()
                if step > 0 then target = math.floor((target - 0.0000001) / step) * step end
            end
            if target > before then
                changed[#changed + 1] = { item = item, value = before }
                local actual
                local ok = pcall(function() actual = writeCharge(item, target) end)
                if not ok then
                    local rollbackOK = true
                    for index = #changed, 1, -1 do
                        local previous = changed[index]
                        local restored = pcall(function() writeCharge(previous.item, previous.value) end)
                        if not restored then rollbackOK = false end
                    end
                    return nil, rollbackOK and "battery_write_failed" or "battery_rollback_failed"
                end
                total = total + actual - before
            end
        end
    end
    return total
end

function Core.near(position, target, radius)
    if not position or not target then return false end
    radius = radius or 4
    return math.floor(position.z) == math.floor(target.z)
        and math.abs(position.x - target.x) <= radius and math.abs(position.y - target.y) <= radius
end

function Core.copyRecord(record)
    if not record then return nil end
    return { id = record.id, name = record.name, pairId = record.pairId,
        x = record.x, y = record.y, z = record.z, facing = record.facing,
        schema = record.schema, removed = record.removed or false }
end

return Core
