-- Exercise the bridge with the installed Live Wire registry, demand, history and battery Lua.
local T, P, lw = TEST, SuQingPortals, LiveWire
local W, E, R = P.World, P.Power, lw.Registry
local check, near = T.assert, T.near
local packageVersion, active = LIVEWIRE_PACKAGE_VERSION or lw.VERSION, true
local version = packageVersion
local modern = lw.VERSION ~= "1.7.2"
function getActivatedMods() return { contains = function(_, id) return active and id == "batman_LiveWire" end } end
function getModInfoByID() return { getModVersion = function() return version end } end
local temperature = 20
function getClimateManager() return { getTemperature = function() return temperature end } end
function sendItemStats() end
lw.Config = { get = function(key)
    if key == "BatteryCapacityMultiplier" then return 1 end
    return key == "BatteryCold"
end, tileRange = function() return 20 end, verticalRange = function() return 3 end }
lw.Migration = { run = function() return true end }
R.init()

local square = T.square(12, 10, 0)
square.powered = true
local portal, player = T.object(square), T.player(square, 0)
W.register(portal)
local doorBattery = T.battery(0)
doorBattery.quantize = true
function doorBattery:getUseDelta() return 0.00001 end
player.inventory:AddItem(doorBattery)
check(W.Install(player, portal, doorBattery, 1), "install the original portal battery")

local function device(id, model, role, x, y)
    local sq = T.square(x, y, 0)
    function sq:isOutside() return false end
    local obj = T.object(sq)
    obj.container = T.container(obj)
    lw.Marks.set(obj, { id = id, model = model })
    local d = { id = id, model = model, role = role, state = "on", cond = 100, eff = 0.85, x = x, y = y, z = 0 }
    R.addDevice(d)
    return d, obj
end

local inv = device("i1", "Inverter", "inverter", 10, 10)
local grid = R.createGrid(inv)
grid.powered = true
local bank, bankObject = device("b1", "PowerBank", "storage", 11, 10)
R.link(bank, grid)
local function storageBattery(charge)
    local item = T.battery(charge, "Base.CarBattery3", 100)
    item.data = {}
    function item:getUseDelta() return 0.00001 end
    function item:getCurrentUses() return math.floor(self.charge / self:getUseDelta() + 0.5) end
    function item:setCurrentUses(uses) self.charge = uses * self:getUseDelta() end
    function item:setCurrentUsesFloat(value)
        self:setCurrentUses(math.floor(value / self:getUseDelta() + 0.5))
        if self.failDebit then self.failDebit = nil; error("injected Live Wire item write failure") end
    end
    function item:getModData() return self.data end
    function item:setConditionNoSound(value) self.condition = value end
    bankObject.container:AddItem(item)
    return item
end
local bankBattery = storageBattery(0.8)
local secondBattery = storageBattery(0.5)
lw.Demand.inventories[inv.id] = { measured = true }
R.setAnchor(inv, true)

local function charge()
    return doorBattery:getCurrentUsesFloat()
end
local function energy(item)
    return lw.Batteries.energy(item, lw.Batteries.capacity(item:getFullType(), lw.Batteries.condition(item)))
end
local function advance(hours)
    T.hours = T.hours + hours
    grid.lastTick = T.hours
    W.chargeTick()
end

check(E.info(portal).source == "livewire", "online anchored grid with a real cabinet is recognized")
local oldStock, untouched = energy(bankBattery), energy(secondBattery)
W.chargeTick()
near(charge(), 0, "first observation does not charge")
advance(0.1)
near(charge(), 0.05, "portal charges at the original rate")
near(oldStock - energy(bankBattery), charge() * 0.30 / 0.85, "exact delivered amount charged at inverter input")
near(energy(secondBattery), untouched, "unused battery not debited")
near(bank.slots[1].charge * lw.Batteries.capacity(bankBattery.kind, bankBattery.condition), energy(bankBattery), "slot snapshot agrees with original item")
local chargedStock, delivered = energy(bankBattery), charge()
W.chargeTick()
near(charge(), delivered, "same time gives no extra charge")
near(energy(bankBattery), chargedStock, "same time gives no extra debit")
local receipt, approved = E.begin(portal, 0.02)
check(receipt and approved == 0.02 and E.finish(receipt, 0.02) and E.finish(receipt, 0.02), "successful receipt can be acknowledged twice")
near(chargedStock - energy(bankBattery), 0.02 * 0.30 / 0.85, "one payment per receipt")

local stock, before = energy(bankBattery), charge()
doorBattery.failNext = true
advance(0.1)
near(charge(), before, "failed portal write restores the door")
near(energy(bankBattery), stock, "failed portal write never debits cabinet")

local realPersist = P.BatterySlots.persist
local failPersist = true
P.BatterySlots.persist = function(...)
    if failPersist then failPersist = false; return false, "storage_conflict" end
    return realPersist(...)
end
advance(0.1)
P.BatterySlots.persist = realPersist
near(charge(), before, "failed portal persistence restores the door")
near(energy(bankBattery), stock, "failed portal persistence never debits cabinet")

local slots, uses = bank.slots, bankBattery:getCurrentUses()
local carry = bankBattery.data[lw.Batteries.ENERGY_KEY]
secondBattery.failDebit = true
advance(0.1)
near(charge(), before, "failed second bank item write rolls back door")
check(bank.slots == slots and bankBattery:getCurrentUses() == uses and bankBattery.data[lw.Batteries.ENERGY_KEY] == carry,
    "failed second bank write restores earlier item, exact carry and slot snapshot")
near(energy(bankBattery), stock, "failed bank write leaves no debit")
near(energy(secondBattery), untouched, "failed bank write restores second item")

advance(0.01)
advance(1)
near(charge(), before + 0.005, "a long observation gap receives no retroactive charge")
before = charge()
grid.equipmentOff = true
advance(0.1)
check(E.info(portal).error == "power_livewire_unavailable", "equipment breaker blocks portal")
grid.equipmentOff = false
advance(0.1)
near(charge(), before, "circuit reopening starts a fresh observation")

local history = lw.PowerHistory
history.record(R.data, inv, false, T.hours + 0.01)
history.record(R.data, inv, true, T.hours + 0.02)
advance(0.1)
near(charge(), before, "power transition between samples invalidates old time")
history.equipment(R.data, inv, true, T.hours + 0.01)
history.equipment(R.data, inv, false, T.hours + 0.02)
advance(0.1)
near(charge(), before, "equipment transition between samples invalidates old time")

local bankSq = T.squares["11:10:0"]
T.squares["11:10:0"] = nil
advance(0.1)
check(E.info(portal).error == "power_livewire_unavailable", "unloaded cabinet cannot charge from its slot snapshot")
T.squares["11:10:0"] = bankSq
advance(0.1)
near(charge(), before, "reloading cabinet cannot charge old time")
local beforeEnergy = energy(bankBattery)
doorBattery:setUsedDelta(1)
advance(0.1)
near(energy(bankBattery), beforeEnergy, "full portal does not bill the cabinet")
doorBattery:setUsedDelta(0.1)
portal.data.SuQingPortals.pendingToken = "transfer"
advance(0.1)
near(energy(bankBattery), beforeEnergy, "locked portal does not bill the cabinet")
portal.data.SuQingPortals.pendingToken = nil
advance(0.1)
near(charge(), 0.1, "unlocking starts a fresh observation")

version = "1.7.3"
check(not E.info(portal).metered, "unknown Live Wire version refuses settlement")
version = modern and "1.7.2" or "2.0.1"
check(not E.info(portal).metered, "mismatched LiveWire runtime and package refuse settlement")
version = lw.VERSION == "2.1.0" and "2.0.3" or "2.1.0"
check(not E.info(portal).metered, "mismatched package and runtime versions are refused")
version = packageVersion
active = false
check(not E.info(portal).metered, "disabled Live Wire does not participate")
active = true
local gen = T.generator(T.square(12, 11, 0), 8)
function gen:getModData() return {} end
E.refreshSources()
check(E.info(portal).source == "generator", "ordinary generator retains priority over Live Wire")
function gen:getModData() return { LiveWireBackup = { id = "backup1" } } end
check(E.info(portal).source == "livewire", "marked backup is never directly billed as ordinary fuel")
local backup = { id = "backup1", model = "Backup", role = "backup", x = 12, y = 11, z = 0 }
R.addDevice(backup)
R.link(backup, grid)
check(not E.info(portal).metered, "network with linked backup is excluded")
R.unlink(backup)
square.room, square.grid = {}, true
check(E.info(portal).source == "grid", "mains retains priority")
square.room, square.grid = nil, false

grid.demand = 10000
check(not E.info(portal).metered, "existing loads retain a storage reserve")
grid.demand = 0
if lw.VERSION == "2.2.0" then
    grid.linkedW = 10000
    check(not E.info(portal).metered, "wired third-party loads retain a storage reserve")
    grid.linkedW = -1
    check(not E.info(portal).metered, "invalid wired demand is refused")
    grid.linkedW = nil
end
temperature = -10
bankBattery:setCurrentUses(100)
secondBattery:setCurrentUses(100)
check(not E.info(portal).metered, "cold reserve is not eligible for charging")
temperature = 20
bankBattery:setCurrentUses(10000)
secondBattery:setCurrentUses(0)
local limited, allowed = E.begin(portal, 2)
check(limited and allowed > 0 and allowed < 2, "approved amount limited by available real cabinet energy")
check(E.finish(limited, allowed), "partial source availability can be settled")
doorBattery:setUsedDelta(0.4)
local inverters = modern and lw.Inverters or lw.Sim
local reserve = inverters.idleW(grid) * lw.STEP_HOURS / (1000 * inv.eff)
local outputCost = 0.30 / inv.eff
local warm = lw.Batteries.capacity(bankBattery.kind, bankBattery.condition)
lw.Batteries.setEnergy(bankBattery, reserve + outputCost * 0.012346, warm)
W.chargeTick()
advance(0.1)
check(charge() > 0.41233 and charge() < 0.412346, "source-limited writes round down to a native battery use")
check(energy(bankBattery) >= reserve, "native rounding cannot spend protected ordinary-load reserve")
if modern then
    bankBattery:setCurrentUses(90000)
    local cut = false
    check(lw.CircuitProvider.register({ blocked = function(object, kind, owner)
        return cut and object == portal and kind == "equipment" and owner == grid
    end }), "register a simulated equipment provider through the real extension interface")
    cut = true
    check(E.info(portal).error == "power_livewire_unavailable", "2.0 circuit provider can cut the portal")
    cut = false
    check(E.info(portal).metered, "closed provider circuit restores eligibility")
    lw.Extended = { Points = { servedAt = function() return true end } }
    check(E.info(portal).error == "power_livewire_unavailable", "an unwired portal cannot bypass a board")
    lw.Extended = nil

    local enabledExtra = true
    check(lw.Coverage.register({
        replacesDisc = true,
        covers = function(id, _, x, y, z)
            return enabledExtra and id == inv.id and x == 55 and y == 10 and z == 0
        end,
        bounds = function() end, positions = function() return {} end,
        scan = function() end, step = function() return true, 0 end, idsAt = function() return {} end,
    }), "register a simulated coverage provider through the real extension interface")
    local extendedSquare = T.square(55, 10, 0)
    extendedSquare.powered = true
    local extendedPortal = T.object(extendedSquare)
    check(not E.info(portal).metered, "replaced disc is not a source of portal power")
    check(E.info(extendedPortal).source == "livewire", "confirmed extended coverage is eligible outside the disc")
    enabledExtra = false
    check(not E.info(extendedPortal).metered, "losing extended coverage ends charging eligibility")
end
print("PORTAL_LIVEWIRE_STORAGE checks=" .. T.checks .. " failures=0")
