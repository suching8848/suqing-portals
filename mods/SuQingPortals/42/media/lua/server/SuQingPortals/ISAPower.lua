-- Optional ISA energy settlement. No upstream hooks or native load mutation.
SuQingPortals = SuQingPortals or {}
local A = {}
SuQingPortals.ISAPower = A
local EPS, locked = 0.0001, {}
local CARRY_KEY = "SuQingPortalsISAEnergyCarry"

local function finite(value)
    return type(value) == "number" and value - value == 0
end

local function system()
    local ok, result = pcall(function()
        if (isClient and isClient()) or (isServer and isServer()) or not getActivatedMods then return nil end
        local mods = getActivatedMods()
        if not mods or not mods:contains("ISA") or mods:contains("ISA-Fix") then return nil end
        local info = getModInfoByID and getModInfoByID("ISA")
        if not info or not info.getModVersion or info:getModVersion() ~= "1.2.15" then return nil end
        local isa = require "ImmersiveSolarArrays/Utilities"
        local s = type(isa) == "table" and isa.PBSystem_Server
        if s and s.getLuaObjectCount and s.getLuaObjectByIndex and s.getLuaObjectOnSquare and s.isValidIsoObject then return s end
    end)
    return ok and result or nil
end

function A.isSupported() return system() ~= nil end

local function identity(bank)
    local s = system()
    if not s or not bank or bank.luaSystem ~= s or not bank.getIsoObject or not bank.getSquare then return nil end
    local generator, square = bank:getIsoObject(), bank:getSquare()
    if not generator or not square or generator:getSquare() ~= square or square:getGenerator() ~= generator then return nil end
    if s:getLuaObjectOnSquare(square) ~= bank or not s:isValidIsoObject(generator) then return nil end
    return generator
end

function A.banks()
    local result = {}
    local s = system()
    if not s then return result end
    local ok = pcall(function()
        for index = 1, s:getLuaObjectCount() do
            local bank = s:getLuaObjectByIndex(index)
            local valid, generator = pcall(identity, bank)
            if valid and generator then result[#result + 1] = {generator = generator, bank = bank} end
        end
    end)
    return ok and result or {}
end

function A.costPerEquivalent(raw, factor)
    local mode = SandboxVars and SandboxVars.ISA and SandboxVars.ISA.DrainCalc
    if not finite(raw) or raw <= 0 or not finite(factor) or factor < 0 or (mode ~= 1 and mode ~= 2) then return nil end
    local result = mode == 1 and raw * 920 or raw * 800 * factor
    return finite(result) and result or nil
end

local function snapshot(bank, generator)
    local container = generator:getContainer()
    if not container or not bank.updateBatteries or not bank.saveData or not bank.shouldDrain then return nil end
    local r = {bank = bank, generator = generator, container = container, items = {}, originals = {},
        before = {charge = bank.charge, maxcapacity = bank.maxcapacity, batteries = bank.batteries},
        activated = generator:isActivated(), phase = "active", charge = 0, capacity = 0, batteries = 0,
        carryBefore = generator:getModData()[CARRY_KEY]}
    if r.carryBefore ~= nil and not finite(r.carryBefore) then return nil end
    local list = container:getItems()
    for index = 0, list:size() - 1 do
        local item = list:get(index)
        if not item or r.items[item] then return nil end
        r.items[item] = true
        local maximum = item:getModData().ISA_maxCapacity
        if maximum ~= nil then
            local condition, charge = item:getCondition(), item:getCurrentUsesFloat()
            if not finite(maximum) or maximum <= 0 or not finite(condition) or condition < 0 or condition > 100 or
               not finite(charge) or charge < 0 or charge > 1 or not item.setCurrentUsesFloat then return nil end
            local effective = maximum * (1 - (1 - condition / 100) ^ 6)
            r.capacity = r.capacity + effective
            r.charge = r.charge + effective * charge
            if condition > 0 then r.batteries = r.batteries + 1 end
            r.originals[#r.originals + 1] = {item = item, charge = charge, condition = condition,
                maximum = maximum, capacity = effective, allowed = {charge}}
        end
    end
    if not finite(r.charge) or not finite(r.capacity) then return nil end
    r.carry = r.carryBefore or 0
    return r
end

local function unchangedContents(r, checkCharge)
    if identity(r.bank) ~= r.generator or r.generator:getContainer() ~= r.container then return false end
    local list, seen = r.container:getItems(), {}
    for index = 0, list:size() - 1 do
        local item = list:get(index)
        if not r.items[item] or seen[item] then return false end
        seen[item] = true
    end
    for item in pairs(r.items) do if not seen[item] then return false end end
    if checkCharge then
        for _, row in ipairs(r.originals) do
            if row.item:getCondition() ~= row.condition or row.item:getModData().ISA_maxCapacity ~= row.maximum then return false end
            local charge, matches = row.item:getCurrentUsesFloat(), false
            for _, allowed in ipairs(row.allowed) do if finite(charge) and math.abs(charge - allowed) <= EPS then matches = true end end
            if not matches then return false end
        end
    end
    return true
end

local function apply(r, amount)
    if not unchangedContents(r, true) then error("ISA bank changed during settlement") end
    local idealDebit = amount * r.cost + r.carry
    local charge = math.max(0, math.min(r.capacity, r.charge - idealDebit))
    local ratio = r.capacity > 0 and charge / r.capacity or 0
    for _, row in ipairs(r.originals) do row.allowed[#row.allowed + 1] = ratio end
    r.bank.charge, r.bank.maxcapacity, r.bank.batteries = charge, r.capacity, r.batteries
    r.bank:updateBatteries(r.container, ratio)
    local actualCharge = 0
    for _, row in ipairs(r.originals) do
        local actual = row.item:getCurrentUsesFloat()
        if not finite(actual) or math.abs(actual - ratio) > EPS then error("ISA battery write readback failed") end
        actualCharge = actualCharge + row.capacity * actual
    end
    r.bank.charge = actualCharge
    r.generator:getModData()[CARRY_KEY] = idealDebit - (r.charge - actualCharge)
    if actualCharge <= 0 then r.generator:setActivated(false)
    elseif r.activated and r.bank.on == true then r.generator:setActivated(true) end
    if r.bank.updateSprite then r.bank:updateSprite(ratio) end
    r.bank:saveData(true)
    if not finite(r.bank.charge) or math.abs(r.bank.charge - actualCharge) > EPS or not unchangedContents(r, true) then
        error("ISA save readback failed")
    end
    r.debitedAmount, r.afterCharge = amount, actualCharge
end

function A.rollback(r)
    if type(r) ~= "table" or r.owner ~= A then return false, "isa_invalid_receipt" end
    if r.phase == "rolledback" then return true end
    if r.phase == "finished" then return false, "isa_receipt_closed" end
    local ok = pcall(function()
        if not unchangedContents(r, true) then error("ISA rollback bank changed") end
        for _, row in ipairs(r.originals) do
            row.item:setCurrentUsesFloat(row.charge)
            if row.item:getCurrentUsesFloat() ~= row.charge then error("ISA exact rollback readback failed") end
        end
        r.bank.charge, r.bank.maxcapacity, r.bank.batteries = r.before.charge, r.before.maxcapacity, r.before.batteries
        r.generator:getModData()[CARRY_KEY] = r.carryBefore
        r.generator:setActivated(r.activated)
        if r.bank.updateSprite then
            r.bank:updateSprite(r.capacity > 0 and r.charge / r.capacity or 0)
        end
        r.bank:saveData(true)
    end)
    if not ok then r.phase = "fault"; return false, "isa_rollback_failed" end
    r.phase, locked[r.bank] = "rolledback", nil
    return true
end

function A.begin(bank, requested, raw, factor)
    if not finite(requested) or requested <= 0 then return nil, 0, "isa_invalid_amount" end
    local cost = A.costPerEquivalent(raw, factor)
    if not cost or not finite(cost) then return nil, 0, "isa_unsupported_cost" end
    if locked[bank] then return nil, 0, "isa_busy" end
    local ok, r, code = pcall(function()
        local generator = identity(bank)
        if not generator then return nil, "isa_unavailable" end
        if bank.on ~= true or not generator:isActivated() or not generator:isConnected() or not bank:shouldDrain(generator) then
            return nil, "isa_not_supplying"
        end
        local receipt = snapshot(bank, generator)
        if not receipt or receipt.capacity <= 0 or receipt.batteries <= 0 then return nil, "isa_invalid_storage" end
        return receipt
    end)
    if not ok or not r then return nil, 0, code or "isa_read_failed" end
    r.owner, r.cost = A, cost
    r.approved = cost == 0 and requested or math.min(requested, math.max(0, r.charge - r.carry) / cost)
    if r.approved <= 0 then return nil, 0, "isa_insufficient_charge" end
    locked[bank] = r
    local saved = pcall(apply, r, r.approved)
    if not saved then
        local restored = A.rollback(r)
        return nil, 0, restored and "isa_write_failed" or "isa_rollback_failed"
    end
    return r, r.approved
end

function A.finish(r, actual)
    if type(r) ~= "table" or r.owner ~= A or not finite(actual) or actual < 0 or actual > r.approved + EPS then
        return false, "isa_invalid_receipt"
    end
    if r.phase == "finished" then return math.abs(actual - r.actual) <= 0.000000001, "isa_receipt_closed" end
    if r.phase ~= "active" then return false, "isa_receipt_closed" end
    if actual == 0 or math.abs(actual - r.approved) > 0.000000001 then
        if actual == 0 then
            local ok, code = A.rollback(r)
            if not ok then return false, code end
        elseif not pcall(apply, r, actual) then return false, "isa_write_failed" end
    else
        local ok, unchanged = pcall(unchangedContents, r, true)
        if not ok or not unchanged then return false, "isa_bank_changed" end
    end
    r.phase, r.actual, locked[r.bank] = "finished", actual, nil
    return true
end

return A
