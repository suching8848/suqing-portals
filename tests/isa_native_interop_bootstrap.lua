-- Load the installed ISA PowerBankObject_Server.lua between this file and the spec.
-- Only minimal global-object/native-object substitutes; no world is initialized.
ISA_NATIVE = {checks = 0, banks = {}, isa = {}}
function isClient() return false end
function isServer() return false end
function getActivatedMods() return {contains = function(self, name) return name == "ISA" end} end
function getModInfoByID() return {getModVersion=function() return "1.2.15" end} end
SandboxVars = {ISA = {DrainCalc = 2, ChargeFreq = 1, batteryDegradeChance = 0}}
function getWorld() return {isHydroPowerOn = function() return false end} end
SGlobalObject = {}
function SGlobalObject:derive(name)
    local class = {}
    class.__index = class
    setmetatable(class, {__index = self})
    ISA_NATIVE.class = class
    return class
end
function SGlobalObject:getIsoObject() return self.isoObject end
function SGlobalObject:getSquare() return self.square end
function require(name)
    if name == "ImmersiveSolarArrays/Utilities" then return ISA_NATIVE.isa end
    if name == "Map/SGlobalObject" then return SGlobalObject end
    if name == "ImmersiveSolarArrays/PowerBank/SolarScan" then return function() return 0 end end
    error("Unexpected ISA fixture dependency: " .. name)
end
local sys = {savedObjectModData = {'on','batteries','charge','maxcapacity','drain','npanels','panels','lastHour','conGenerator'}}
ISA_NATIVE.isa.PBSystem_Server = sys
function sys:getLuaObjectCount() return #ISA_NATIVE.banks end
function sys:getLuaObjectByIndex(index) return ISA_NATIVE.banks[index] end
function sys:getLuaObjectOnSquare(square) return square.bank end
function sys:isValidIsoObject(generator) return generator.isISA == true end
function ISA_NATIVE.battery(charge, maximum, condition)
    local item = {charge = charge, data = {ISA_maxCapacity = maximum}, condition = condition}
    function item:getModData() return self.data end
    function item:getCondition() return self.condition end
    function item:getCurrentUsesFloat() return self.charge end
    function item:setCurrentUsesFloat(value)
        self.charge = value
        if self.failNext then self.failNext = nil; error("ISA native fixture setter failure") end
    end
    function item:getFullType() return "ISA.WiredCarBattery" end
    return item
end
function ISA_NATIVE.makeBank(items)
    local container, square = {}, {}
    local list = {size = function() return #items end, get = function(self, index) return items[index + 1] end}
    function container:getItems() return list end
    function container:setDrawDirty(value) self.dirty = value end
    local generator = {isISA = true, data = {}, active = true, sends = 0}
    function generator:getSquare() return square end
    function generator:getContainer() return container end
    function generator:getModData() return self.data end
    function generator:isActivated() return self.active end
    function generator:isConnected() return true end
    function generator:setActivated(value) self.active = value end
    function generator:transmitModData() self.sends = self.sends + 1 end
    function generator:getAttachedAnimSprite() return nil end
    function generator:addAttachedAnimSpriteByName(name) self.overlay = name end
    function square:getGenerator() return generator end
    local pb = setmetatable({luaSystem = sys, isoObject = generator, square = square}, ISA_NATIVE.class)
    square.bank = pb
    pb:initNew()
    pb.on = true
    -- This is the installed upstream capacity formula, not a copy in the fixture.
    pb:calculateBatteryStats(container)
    pb:saveData(true)
    ISA_NATIVE.banks[#ISA_NATIVE.banks + 1] = pb
    return pb, generator, container
end
function ISA_NATIVE.check(value, message)
    ISA_NATIVE.checks = ISA_NATIVE.checks + 1
    if not value then error(message) end
end
function ISA_NATIVE.near(actual, expected, message)
    ISA_NATIVE.check(math.abs(actual - expected) < 0.000001, message or "ISA upstream amount mismatch")
end
