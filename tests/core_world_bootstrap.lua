-- Standalone Kahlua mocks only. Never creates/loads a Project Zomboid world.
function require(name) return true end
function isClient() return false end
function isServer() return false end
local saved = {}
ModData = { getOrCreate = function(name) saved[name] = saved[name] or {}; return saved[name] end }
TEST = { hours = 100, squares = {}, players = {}, itemId = 100, checks = 0 }
TEST.generators = {}
function getGameTime() return { getWorldAgeHours = function() return TEST.hours end } end
function getCell() return { getGridSquare = function(self, x, y, z) return TEST.squares[x .. ":" .. y .. ":" .. z] end,
    getProcessIsoObjects = function() return TEST.list(TEST.generators) end } end
function instanceof(object, class) return object and object.class == class end
IsoGenerator = { isPoweringSquare = function(gx,gy,gz,x,y,z) return (gx-x)^2+(gy-y)^2<=400 and math.abs(gz-z)<=3 end }
function getSpecificPlayer(index) return TEST.players[index] end
Events = {}
for _, name in ipairs({ "OnTick", "LoadGridsquare", "OnObjectAboutToBeRemoved", "OnCreatePlayer", "OnGameStart" }) do
    local event = { callbacks = {} }
    event.Add = function(fn) event.callbacks[#event.callbacks + 1] = fn end
    event.run = function(...)
        for _, fn in ipairs(event.callbacks) do fn(...) end
    end
    Events[name] = event
end

function TEST.assert(value, message)
    TEST.checks = TEST.checks + 1
    if not value then error(message or "assertion failed") end
end

function TEST.near(actual, expected, message)
    TEST.assert(math.abs(actual - expected) < 0.0001, (message or "number mismatch") .. ": " .. tostring(actual) .. " ~= " .. tostring(expected))
end

function TEST.list(values)
    local result = { values = values or {} }
    function result:size() return #self.values end
    function result:get(index) return self.values[index + 1] end
    return result
end

function TEST.container(parent)
    local container = { list = TEST.list(), parent = parent }
    function container:getItems() return self.list end
    function container:getParent() return self.parent end
    function container:getType() return self.type end
    function container:setType(value) self.type = value end
    function container:setCapacity(value) self.capacity = value end
    function container:setExplored(value) end
    function container:setAcceptItemFunction(value) self.accept = value end
    function container:setDrawDirty(value) end
    function container:contains(item)
        for _, candidate in ipairs(self.list.values) do if candidate == item then return true end end
        return false
    end
    function container:containsRecursive(item) return self:contains(item) end
    function container:AddItem(item)
        if not self:contains(item) then self.list.values[#self.list.values + 1] = item end
        item.container = self
        return item
    end
    function container:Remove(item)
        self.removeCount = (self.removeCount or 0) + 1
        if self.failOnRemoveOrdinal == self.removeCount then error("simulated second native Remove failure") end
        for index, candidate in ipairs(self.list.values) do
            if candidate == item then table.remove(self.list.values, index); item.container = nil; return end
        end
    end
    function container:getItemWithIDRecursiv(id)
        for _, item in ipairs(self.list.values) do if item:getID() == id then return item end end
    end
    return container
end
ItemContainer = { new = function(name, square, parent) return TEST.container(parent) end }

function TEST.battery(charge, kind, condition)
    TEST.itemId = TEST.itemId + 1
    local item = { charge = charge, kind = kind or "Base.CarBattery1", condition = condition or 80, id = TEST.itemId }
    function item:getFullType() return self.kind end
    function item:getCurrentUsesFloat() return self.charge end
    function item:setUsedDelta(value)
        if self.failNext then self.failNext = false; self.charge = value; error("simulated native setter exception") end
        if self.silentFailNext then self.silentFailNext = false; return end
        if self.quantize then value = math.floor(value / 0.00001 + 0.5) * 0.00001 end
        self.charge = nativeFloat32 and nativeFloat32(value) or value
    end
    function item:getCondition() return self.condition end
    function item:getConditionMax() return 100 end
    function item:getID() return self.id end
    function item:getContainer() return self.container end
    function item:getName() return self.kind end
    return item
end

function TEST.square(x, y, z, powered)
    local square = { x = x, y = y, z = z, powered = powered or false, objects = TEST.list(), dropped = {} }
    function square:getX() return self.x end
    function square:getY() return self.y end
    function square:getZ() return self.z end
    function square:getObjects() return self.objects end
    function square:haveElectricity() return self.powered end
    function square:hasGridPower() return self.grid or false end
    function square:getRoom() return self.room end
    function square:getChunk() return self.chunk end
    function square:AddWorldInventoryItem(item, x, y, z) self.dropped[#self.dropped + 1] = item end
    TEST.squares[x .. ":" .. y .. ":" .. z] = square
    if powered then TEST.generator(square, 10) end
    return square
end

function TEST.generator(square, fuel)
    local gen = {class="IsoGenerator", square=square, fuel=fuel or 10, activated=true, connected=true, condition=100}
    function gen:getSquare() return self.square end
    function gen:getFuel() return self.fuel end
    function gen:setFuel(value) self.fuel=nativeFloat32 and nativeFloat32(math.max(0,value)) or math.max(0,value); if self.failWrite then self.failWrite=false;error('fuel setter failed') end end
    function gen:isActivated() return self.activated end
    function gen:setActivated(value) self.activated=value end
    function gen:isConnected() return self.connected end
    function gen:getCondition() return self.condition end
    function gen:getTextureName() return 'appliances_misc_01_0' end
    function gen:getTotalPowerUsing() return 0.002 end
    TEST.generators[#TEST.generators+1]=gen
    return gen
end

function TEST.object(square, sprite)
    local object = { square = square, data = {}, sprite = sprite or "suqing_portal_01_0" }
    function object:getSquare() return self.square end
    function object:getModData() return self.data end
    function object:getContainer() return self.container end
    function object:setContainer(value) if value == nil then error("native setContainer rejects null") end; self.container = value end
    function object:getContainerCount() return (self.container and 1 or 0) + #(self.secondaries or {}) end
    function object:getContainerByIndex(index)
        if self.container then if index == 0 then return self.container end; index = index - 1 end
        return (self.secondaries or {})[index + 1]
    end
    function object:removeAllContainers()
        if self.failDetach then error("simulated native detach failure") end
        self.container = nil; self.secondaries = {}
    end
    function object:getObjectIndex() return self.removed and -1 or 0 end
    function object:getSprite() return { getName = function() return self.sprite end } end
    function object:setSprite(value) self.sprite = value end
    function object:setSpriteFromName(value) self.sprite = value; self.usedRegisteredSprite = true end
    function object:transmitModData() end
    square.objects.values[#square.objects.values + 1] = object
    return object
end

function TEST.player(square, index)
    local player = { square = square, index = index or 0, data = {}, inventory = TEST.container() }
    function player:getSquare() return self.square end
    function player:getX() return self.square.x + 0.5 end
    function player:getY() return self.square.y + 0.5 end
    function player:getZ() return self.square.z end
    function player:getPlayerNum() return self.index end
    function player:getModData() return self.data end
    function player:getInventory() return self.inventory end
    function player:isDead() return false end
    TEST.players[player.index] = player
    return player
end
