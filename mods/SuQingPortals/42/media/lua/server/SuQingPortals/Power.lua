-- Optional sources and transactional charging costs. Never edits native load totals.
require "SuQingPortals/Core"
require "SuQingPortals/ISAPower"
require "SuQingPortals/LiveWirePower"
local P, Core = SuQingPortals, SuQingPortals.Core
local LiveWirePower = P.LiveWirePower
local Power = { sources = {}, fuelCarry = {}, sourceIds = {}, nextSourceId = 0 }
P.Power = Power
Power.RAW_FUEL_PER_EQUIVALENT = 0.3 -- Native charger: 0.05 L/h at 1/6 battery/h.
local function finite(value)
    value = tonumber(value)
    return value and value - value == 0 and value or nil
end
function Power.fuelMultiplier()
    local value = finite(SandboxVars and SandboxVars.GeneratorFuelConsumption)
    return value and math.max(0, value) or 0.1
end
function Power.chargeRate()
    local value = finite(SandboxVars and SandboxVars.SuQingPortals and SandboxVars.SuQingPortals.ChargePerHour)
    return math.max(0, value or Core.DEFAULT_CHARGE_PER_HOUR)
end
local function solarObject(object)
    return object.getTextureName and object:getTextureName() == "solarmod_tileset_01_0"
end
local function loaded(object)
    local square = object and object:getSquare()
    if not square then return nil end
    return getCell():getGridSquare(square:getX(), square:getY(), square:getZ()) == square and square or nil
end
function Power.refreshSources()
    local sources, seen = {}, {}
    local ok, objects = pcall(function() return getCell():getProcessIsoObjects() end)
    if ok and objects then
        for index = 0, objects:size() - 1 do
            local object = objects:get(index)
            if instanceof(object, "IsoGenerator") and not solarObject(object) then
                sources[#sources + 1] = { generator = object, kind = "generator" }; seen[object] = true
            end
        end
    end
    local adapter = P.ISAPower
    if adapter then
        local valid, banks = pcall(adapter.banks)
        if valid and type(banks) == "table" then
            for _, source in ipairs(banks) do
                if source.generator and not seen[source.generator] then
                    source.kind = "solar"; sources[#sources + 1] = source; seen[source.generator] = true
                end
            end
        end
    end
    Power.sources, Power.initialized = sources, true
end
local function active(source, square)
    local gen = source.generator
    local genSquare = loaded(gen)
    if not genSquare or not gen:isConnected() or not gen:isActivated() or gen:getCondition() <= 0 then return false end
    if not IsoGenerator or not IsoGenerator.isPoweringSquare or LiveWirePower.managedGenerator(gen) then return false end
    if not IsoGenerator.isPoweringSquare(genSquare:getX(), genSquare:getY(), genSquare:getZ(), square:getX(), square:getY(), square:getZ()) then return false end
    if source.kind == "solar" then
        return source.bank and source.bank:getIsoObject() == gen and source.bank:shouldDrain(gen) == true
    end
    return finite(gen:getFuel()) ~= nil and gen:getFuel() > 0
end
function Power.provider(object)
    local square = loaded(object)
    if not square then return nil, "power_unknown" end
    if square.hasGridPower and square:hasGridPower() and square.getRoom and square:getRoom() then
        return { kind = "grid", key = "grid" }
    end
    if not square.haveElectricity or not square:haveElectricity() then return nil, "power_disconnected" end
    if not Power.initialized then Power.refreshSources() end
    local best, distance, identity
    for _, source in ipairs(Power.sources) do
        local ok, eligible = pcall(active, source, square)
        if ok and eligible then
            local gs = source.generator:getSquare()
            local d = (gs:getX() - square:getX()) ^ 2 + (gs:getY() - square:getY()) ^ 2 + (gs:getZ() - square:getZ()) ^ 2
            if not Power.sourceIds[source.generator] then
                Power.nextSourceId = Power.nextSourceId + 1
                Power.sourceIds[source.generator] = Power.nextSourceId
            end
            local key = source.kind .. ":" .. gs:getX() .. ":" .. gs:getY() .. ":" .. gs:getZ() .. ":" .. Power.sourceIds[source.generator]
            if not best or d < distance or (d == distance and key < identity) then
                best, distance, identity = source, d, key
            end
        end
    end
    if best then best.key = identity; return best end
    local source, reason = LiveWirePower.source(square)
    return source, reason or (not source and "power_unsupported" or nil)
end
function Power.info(object)
    local ok, source, code = pcall(Power.provider, object)
    local square = loaded(object)
    local info = { loaded = square ~= nil, source = "unknown", metered = false }
    if not ok then info.error = "power_query_failed"; return info end
    if source then
        info.powered, info.metered, info.source, info.providerKey = true, true, source.kind, source.key
        info.rawLoadPerHour = Power.chargeRate() * Power.RAW_FUEL_PER_EQUIVALENT
        info.maxInterval = source.maxInterval
    elseif code == "power_disconnected" then info.powered, info.source = false, "none"
    elseif code == "power_unsupported" then info.powered, info.source, info.error = true, "area", code
    elseif code == "power_livewire_unavailable" then info.powered, info.source, info.error = true, "livewire", code
    else info.error = code end
    return info
end
function Power.capacity(items)
    local available = 0
    for slot = 1, Core.SLOT_COUNT do
        local item = items[slot]
        if Core.isBattery(item) and item:getCondition() > 0 then available = available + 1 - Core.chargeOf(item) end
    end
    return available
end
local function writeFuel(receipt, amount)
    local gen = receipt.source.generator
    local desired = math.max(0, receipt.before - amount * receipt.cost - receipt.carryBefore)
    if desired < 0.0000001 then desired = 0 end
    gen:setFuel(desired)
    local actual = finite(gen:getFuel())
    if not actual or math.abs(actual - desired) > 0.000002 then error("fuel readback mismatch") end
    Power.fuelCarry[gen] = amount * receipt.cost + receipt.carryBefore - (receipt.before - actual)
end
function Power.rollback(receipt)
    if not receipt then return false, "power_rollback_failed" end
    if receipt.rolledBack then return true end
    if receipt.finished then return false, "power_receipt_closed" end
    local ok, result = pcall(function()
        if receipt.source.kind == "solar" then return P.ISAPower.rollback(receipt.solarReceipt) end
        if receipt.source.kind == "livewire" then return LiveWirePower.rollback(receipt.source) end
        if receipt.source.kind == "generator" then
            local gen = receipt.source.generator
            gen:setFuel(receipt.before)
            if math.abs(gen:getFuel() - receipt.before) > 0.000002 then return false end
            Power.fuelCarry[gen] = receipt.carryBefore
            if receipt.activatedBefore and not gen:isActivated() then gen:setActivated(true) end
        end
        return true
    end)
    if ok and result then receipt.rolledBack = true; return true end
    return false, "power_rollback_failed"
end
function Power.begin(object, requested, expectedKey)
    requested = finite(requested)
    if not requested or requested <= 0 then return nil, 0, "power_invalid_amount" end
    local ok, source, code = pcall(Power.provider, object)
    if not ok or not source then return nil, 0, ok and code or "power_query_failed" end
    if expectedKey and source.key ~= expectedKey then return nil, 0, "power_source_changed" end
    local receipt = { source = source, requested = requested }
    local approved = requested
    if source.kind == "solar" then
        local valid, solarReceipt, amount, failure = pcall(P.ISAPower.begin, source.bank, requested,
            Power.RAW_FUEL_PER_EQUIVALENT, Power.fuelMultiplier())
        if not valid or not solarReceipt then
            return nil, 0, valid and (failure == "isa_rollback_failed" and "power_rollback_failed" or failure) or "power_write_failed"
        end
        receipt.solarReceipt, approved = solarReceipt, amount
    elseif source.kind == "livewire" then
        approved = math.min(requested, source.available / source.cost)
        receipt.liveWireLimited = source.available / source.cost <= requested + Core.EPSILON
    elseif source.kind == "generator" then
        local gen = source.generator
        receipt.before, receipt.cost = gen:getFuel(), Power.RAW_FUEL_PER_EQUIVALENT * Power.fuelMultiplier()
        receipt.activatedBefore = gen:isActivated()
        receipt.carryBefore = Power.fuelCarry[gen] or 0
        if receipt.cost > 0 then
            approved = math.min(requested, math.max(0, receipt.before - receipt.carryBefore) / receipt.cost)
        end
        if approved <= 0 then return nil, 0, "power_insufficient" end
        local valid = pcall(writeFuel, receipt, approved)
        if not valid then
            local restored = Power.rollback(receipt)
            return nil, 0, restored and "power_write_failed" or "power_rollback_failed"
        end
    end
    receipt.approved = approved
    return receipt, approved
end
function Power.finish(receipt, amount)
    if receipt.finished then return receipt.actual == amount, "power_receipt_closed" end
    if receipt.rolledBack or not finite(amount) or amount < 0 or amount > receipt.approved + Core.EPSILON then return false, "power_invalid_amount" end
    local ok, result = pcall(function()
        if receipt.source.kind == "solar" then return P.ISAPower.finish(receipt.solarReceipt, amount) end
        if receipt.source.kind == "livewire" then return LiveWirePower.debit(receipt.source, amount) end
        if receipt.source.kind == "generator" then
            writeFuel(receipt, amount)
            if receipt.source.generator:getFuel() <= 0 then receipt.source.generator:setActivated(false) end
        end
        return true
    end)
    if not ok or result == false then return false, "power_write_failed" end
    receipt.actual, receipt.finished = amount, true
    return true
end
function Power.loadForGenerator(generator)
    local load = { count = 0, rawPerHour = 0, fuelPerHour = 0, solar = solarObject(generator) == true }
    if not P.World then return load end
    for _, record in ipairs(P.World.list()) do
        local object = P.World.findObject(record)
        if object then
            local data = object:getModData().SuQingPortals
            local valid = P.World.validateContainer(object)
            if valid and not data.pendingToken and not data.chargeError and Power.capacity(P.World.batteries(object)) > Core.EPSILON then
                local source = Power.provider(object)
                if source and source.generator == generator then
                    load.count = load.count + 1
                    load.rawPerHour = load.rawPerHour + Power.chargeRate() * Power.RAW_FUEL_PER_EQUIVALENT
                end
            end
        end
    end
    load.fuelPerHour = load.rawPerHour * Power.fuelMultiplier()
    return load
end
return Power
