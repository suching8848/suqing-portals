-- Optional Live Wire 1.7.2 storage settlement. No simulation hooks.
SuQingPortals = SuQingPortals or {}
local A = { KWH_PER_EQUIVALENT = 0.30 }
SuQingPortals.LiveWirePower = A
local VERSION, EPS = "1.7.2", 0.00000001
local unavailable = "power_livewire_unavailable"

local function finite(value)
    return type(value) == "number" and value - value == 0
end

local function enabled()
    return not (isClient and isClient()) and not (isServer and isServer())
        and getActivatedMods and getActivatedMods():contains("batman_LiveWire")
end

local function runtime()
    if not enabled() then return nil end
    local lw = LiveWire
    local info = getModInfoByID and getModInfoByID("batman_LiveWire")
    if not lw or lw.VERSION ~= VERSION or lw.SCHEMA ~= 2 or not info or info:getModVersion() ~= VERSION then return nil end
    local r = lw.Registry
    if r and r.ready and not r.readOnly and r.data and r.anchors and lw.Batteries and lw.Demand and lw.Sim then
        return lw, r
    end
end

-- A Live Wire backup remains a real IsoGenerator. Never bill it a second way.
function A.managedGenerator(generator)
    if not enabled() or (generator.hasModData and not generator:hasModData()) then return false end
    local mark = generator:getModData().LiveWireBackup
    return type(mark) == "table" and type(mark.id) == "string"
end

local function historyKey(history)
    local function stamp(log)
        local last = log and log[#log]
        return last and tostring(last.t) or "-"
    end
    return stamp(history.log) .. ":" .. stamp(history.panelLog)
end

local function bankOffer(batteries, bank, reserve, cost)
    if not batteries.container(bank) then return nil end
    local entries, stock = batteries.read(bank), 0
    local identity = {}
    for i, entry in ipairs(entries) do
        if not entry.item or not finite(entry.charge) or entry.charge < 0 or not finite(entry.warmCapacity) then return nil end
        stock = stock + entry.charge
        identity[i] = tostring(entry.id)
    end
    if stock - reserve <= cost * SuQingPortals.Core.EPSILON then return nil end
    return { bank = bank, entries = entries, available = stock - reserve, identity = table.concat(identity, ",") }
end

function A.source(square)
    local lw, r = runtime()
    if not lw then return nil end
    local x, y, z = square:getX(), square:getY(), square:getZ()
    local selected, nearest
    for id, anchor in pairs(r.anchors) do
        if anchor.on == true and IsoGenerator.isPoweringSquare(anchor.x, anchor.y, anchor.z, x, y, z) then
            local distance = (anchor.x - x)^2 + (anchor.y - y)^2
            if not selected or distance < nearest or (distance == nearest and id < selected) then
                selected, nearest = id, distance
            end
        end
    end
    if not selected then return nil end
    local inv, anchor = r.device(selected), r.anchors[selected]
    local grid = inv and r.grid(inv.grid)
    if not grid or grid.inverter ~= selected or not grid.powered or inv.state ~= "on"
        or not finite(inv.cond) or inv.cond <= 0 or inv.x ~= anchor.x or inv.y ~= anchor.y or inv.z ~= anchor.z
        or grid.mainOff or grid.equipmentOff then return nil, unavailable end

    local invSquare = getCell():getGridSquare(inv.x, inv.y, inv.z)
    local history = r.data.powerHistory and r.data.powerHistory[selected]
    if not invSquare or not lw.Marks.findOnSquare(invSquare, selected)
        or not history or not history.on or history.x ~= inv.x or history.y ~= inv.y or history.z ~= inv.z
        or not lw.Demand.ready(inv) then return nil, unavailable end

    local eff, now = inv.eff, getGameTime():getWorldAgeHours()
    if not finite(eff) or eff < 0.05 or eff > 1 or not finite(grid.lastTick)
        or now < grid.lastTick or now - grid.lastTick > 2 * lw.STEP_HOURS then return nil, unavailable end

    local demand, pump, idle = grid.demand, grid.pumpW or 0, lw.Sim.idleW(grid)
    if not finite(demand) or demand < 0 or not finite(pump) or pump < 0 or not finite(idle) or idle < 0 then
        return nil, unavailable
    end
    -- Keep at least one regular simulation step of ordinary loads in reserve.
    -- Assume no new production and do not count energy reserved by the cold model.
    local reserve = (demand + pump + idle) * math.max(now - grid.lastTick, lw.STEP_HOURS) / (1000 * eff)
    local cost, offer = A.KWH_PER_EQUIVALENT / eff, nil
    for id in pairs(grid.members) do
        local dev = r.device(id)
        if dev and dev.grid == grid.id then
            local def = lw.Defs.devices[dev.model]
            if dev.role == "backup" or (def and def.kind == "breaker" and dev.state == "tripped") then
                return nil, unavailable
            end
            if dev.role == "storage" and (not offer or id < offer.bank.id) then
                local candidate = bankOffer(lw.Batteries, dev, reserve, cost)
                if candidate then offer = candidate end
            end
        end
    end
    if not offer then return nil, unavailable end
    offer.kind, offer.batteries = "livewire", lw.Batteries
    offer.cost = cost
    offer.maxInterval = 2 * lw.STEP_HOURS
    offer.key = table.concat({ "livewire", grid.id, selected, offer.bank.id, offer.identity,
        tostring(eff), historyKey(history) }, ":")
    return offer
end

function A.rollback(receipt)
    local before = receipt.before
    if not before then return true end
    local batteries, restored = receipt.batteries, true
    receipt.bank.slots = receipt.slots
    for _, state in ipairs(before) do
        local ok, equal = pcall(function()
            local item, data = state.item, state.item:getModData()
            item:setConditionNoSound(state.condition)
            item:setCurrentUses(state.uses)
            data[batteries.CONDITION_KEY] = state.conditionData
            data[batteries.CYCLES_KEY] = state.cyclesData
            data[batteries.ENERGY_KEY] = state.energyData
            return item:getCondition() == state.condition and item:getCurrentUses() == state.uses
        end)
        if not ok or not equal then restored = false end
    end
    if restored then receipt.before = nil end
    return restored
end

-- Called synchronously after the portal has written the actual accepted charge.
-- Preserve the native item and the exact Live Wire carry and slot snapshot.
function A.debit(receipt, amount)
    if amount <= 0 then return true end
    local remaining = amount * receipt.cost
    if remaining > receipt.available + EPS then return false end
    local batteries, before, expected = receipt.batteries, {}, {}
    for i, entry in ipairs(receipt.entries) do
        local item, data = entry.item, entry.item:getModData()
        before[i] = { item = item, condition = item:getCondition(), uses = item:getCurrentUses(),
            conditionData = data[batteries.CONDITION_KEY], cyclesData = data[batteries.CYCLES_KEY],
            energyData = data[batteries.ENERGY_KEY] }
        local debit = math.min(remaining, entry.charge)
        entry.charge = entry.charge - debit
        remaining = remaining - debit
        expected[i] = entry.charge + entry.reserve
    end
    if remaining > EPS then return false end
    receipt.before, receipt.slots = before, receipt.bank.slots
    batteries.write(receipt.bank, receipt.entries)
    for i, entry in ipairs(receipt.entries) do
        local slot = receipt.bank.slots[i]
        local energy = batteries.energy(entry.item, entry.warmCapacity)
        if not slot or slot.id ~= entry.id or not finite(slot.charge)
            or not finite(energy) or math.abs(energy - expected[i]) > EPS
            or math.abs(slot.charge * entry.warmCapacity - expected[i]) > EPS then return false end
    end
    receipt.before = nil
    return true
end

return A
