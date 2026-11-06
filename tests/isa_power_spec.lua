-- Independent ISA settlement mocks: no game startup or upstream mutation.
local A = SuQingPortals.ISAPower
local checks = 0
local function check(value, message) checks = checks + 1; if not value then error(message) end end
local function near(actual, expected, message) check(math.abs(actual - expected) < 0.0001, message or "ISA amount mismatch") end
local previous = {require = require, mods = getActivatedMods, client = isClient, server = isServer, sandbox = SandboxVars}
local enabled, conflict = true, false
local savedInfo, version = getModInfoByID, "1.2.15"
function getModInfoByID() return {getModVersion=function() return version end} end
function isClient() return false end
function isServer() return false end
function getActivatedMods() return {contains = function(self, name) return name == "ISA" and enabled or name == "ISA-Fix" and conflict end} end
local banks, sys = {}, {}
function sys:getLuaObjectCount() return #banks end
function sys:getLuaObjectByIndex(index) return banks[index] end
function sys:getLuaObjectOnSquare(square) return square.bank end
function sys:isValidIsoObject(gen) return gen.isISA == true end
function require(name) if name == "ImmersiveSolarArrays/Utilities" then return {PBSystem_Server = sys} end; return previous.require(name) end
SandboxVars = {ISA = {DrainCalc = 2}}
local function list(items) return {size = function() return #items end, get = function(self, index) return items[index + 1] end} end
local function battery(charge, capacity, condition)
    local item = {charge = charge, data = {ISA_maxCapacity = capacity or 100}, condition = condition or 100}
    function item:getModData() return self.data end
    function item:getCondition() return self.condition end
    function item:getCurrentUsesFloat() return self.charge end
    function item:setCurrentUsesFloat(value)
        if self.quantum then value = math.floor(value / self.quantum + 0.5) * self.quantum end
        self.charge = value
        if self.failNext then self.failNext = nil; error("ISA simulated native setter failure") end
    end
    return item
end
local function bank(items)
    local square, gen, pb = {}, {isISA = true, active = true, data = {}}, {on = true, luaSystem = sys}
    local container = {items = items}
    function container:getItems() return list(self.items) end
    function gen:getContainer() return container end
    function gen:getSquare() return square end
    function gen:getModData() return self.data end
    function gen:isActivated() return self.active end
    function gen:isConnected() return true end
    function gen:setActivated(value) self.active = value end
    function square:getGenerator() return gen end
    function pb:getSquare() return square end
    function pb:getIsoObject() return gen end
    function pb:shouldDrain() return not self.backup end
    function pb:updateBatteries(c, ratio)
        for _, item in ipairs(c.items) do if item.data.ISA_maxCapacity then item:setCurrentUsesFloat(ratio) end end
    end
    function pb:updateSprite(ratio) self.lastSprite = ratio end
    function pb:saveData()
        self.saves = (self.saves or 0) + 1
        if self.failSave then self.failSave = nil; error("ISA simulated save failure") end
    end
    square.bank = pb
    pb.charge, pb.maxcapacity, pb.batteries = 0, 0, #items
    for _, item in ipairs(items) do
        local cap = item.data.ISA_maxCapacity * (1 - (1 - item.condition / 100) ^ 6)
        pb.charge, pb.maxcapacity = pb.charge + cap * item.charge, pb.maxcapacity + cap
    end
    banks[#banks + 1] = pb
    return pb, gen, container
end

check(A.isSupported(), "active compatible ISA detected")
enabled = false; check(not A.isSupported() and #A.banks() == 0, "absent ISA optional")
enabled, conflict = true, true; check(not A.isSupported(), "different ISA-Fix refused")
conflict = false
near(A.costPerEquivalent(0.1, 2), 160, "vanilla mode follows native fuel multiplier")
SandboxVars.ISA.DrainCalc = 1; near(A.costPerEquivalent(0.1, 2), 92, "ISA scan conversion ignores generator multiplier")
SandboxVars.ISA.DrainCalc = 3; check(A.costPerEquivalent(0.1, 1) == nil, "unknown calculation mode rejected")
SandboxVars.ISA.DrainCalc = 2
check(A.costPerEquivalent(0/0, 1) == nil and A.costPerEquivalent(0.1, -1) == nil, "invalid cost cannot become free")

local b1, b2 = battery(0.2), battery(0.8)
local pb, gen = bank({b1, b2})
check(#A.banks() == 1 and A.banks()[1].generator == gen, "canonical loaded ISA bank enumerated")
local r, approved = A.begin(pb, 0.5, 0.1, 1)
check(r ~= nil, "ISA debit creates receipt"); near(approved, 0.5); near(pb.charge, 60)
near(b1.charge, 0.3); near(b2.charge, 0.3)
check(A.begin(pb, 1, 0.1, 1) == nil, "unsettled bank receipt excludes duplicate debit")
check(A.rollback(r), "ISA exact rollback succeeds")
near(b1.charge, 0.2); near(b2.charge, 0.8); near(pb.charge, 100)
check(A.rollback(r), "ISA rollback idempotent")
r, approved = A.begin(pb, 2, 0.1, 1)
near(approved, 1.25, "ISA amount capped by actual battery energy")
near(pb.charge, 0); check(not gen.active, "depleted ISA bank disconnects native supply")
check(A.finish(r, 0.5), "unused debit refunded on partial portal charge")
near(pb.charge, 60); near(b1.charge, 0.3); near(b2.charge, 0.3)
check(A.finish(r, 0.5), "ISA finish idempotent")
check(not A.rollback(r), "finished debit cannot be refunded again")

gen.active = true
r = A.begin(pb, 0.2, 0.1, 1)
check(r and A.finish(r, 0), "zero successful portal charge refunds all ISA energy")
near(pb.charge, 60)
b1.failNext = true
local failed, _, code = A.begin(pb, 0.2, 0.1, 1)
check(failed == nil and code == "isa_write_failed", "partial upstream battery write fails safely")
near(b1.charge, 0.3); near(b2.charge, 0.3); near(pb.charge, 60)
pb.failSave = true
failed, _, code = A.begin(pb, 0.2, 0.1, 1)
check(failed == nil and code == "isa_write_failed", "save exception causes exact refund")
near(pb.charge, 60)
pb.backup = true; check(A.begin(pb, 0.2, 0.1, 1) == nil, "active backup excludes ISA charge source")
pb.backup = nil; pb.on = false; check(A.begin(pb, 0.2, 0.1, 1) == nil, "bank off excludes ISA charge source")
pb.on = true; pb.charge = 9999
r, approved = A.begin(pb, 1, 0.1, 1)
near(approved, 0.75, "stale bank counter cannot mint energy")
check(A.rollback(r), "stale-counter debit can restore exact prior native batteries")
pb.charge = 60
gen.active = true
r = A.begin(pb, 0.2, 0.1, 1)
b1.charge = 0.99
check(not A.rollback(r), "unrelated external battery mutation is not overwritten")
local unknown = battery(0.5)
local invalid = bank({unknown}); unknown.data.ISA_maxCapacity = "bad"
check(A.begin(invalid, 1, 0.1, 1) == nil, "unknown battery metadata fails closed")

local q = battery(0.5, 10000); q.quantum = 0.00001
local quantized, qgen = bank({q})
local initial = quantized.charge
for index = 1, 25 do
    local transaction = A.begin(quantized, 0.00001, 0.1, 1)
    check(transaction and A.finish(transaction, 0.00001), "small debits retain quantized energy carry")
end
near(initial - quantized.charge + (qgen.data.SuQingPortalsISAEnergyCarry or 0), 25 * 0.00001 * 80,
    "physical energy plus persisted carry equals ideal small-step consumption")
local carryBefore, exactBefore = qgen.data.SuQingPortalsISAEnergyCarry, q.charge
local qr = A.begin(quantized, 0.001, 0.1, 1)
check(qr and A.rollback(qr), "quantized debit refunds")
check(qgen.data.SuQingPortalsISAEnergyCarry == carryBefore and q.charge == exactBefore, "rollback restores exact carry and native charge")
check(A.costPerEquivalent(1e308, 1e308) == nil, "overflow cost rejected")

version="1.2.16";check(not A.isSupported() and #A.banks()==0,"unknown ISA version fails closed")
getModInfoByID=savedInfo
require, getActivatedMods, isClient, isServer, SandboxVars = previous.require, previous.mods, previous.client, previous.server, previous.sandbox
print("PORTAL_ISA_POWER_SETTLEMENT checks=" .. checks .. " failures=0")
