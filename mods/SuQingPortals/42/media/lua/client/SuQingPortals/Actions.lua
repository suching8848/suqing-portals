require "TimedActions/ISBaseTimedAction"
require "TimedActions/ISTimedActionQueue"
require "SuQingPortals/Core"
require "luautils"

local P = SuQingPortals
P.Actions = P.Actions or {}
local A = P.Actions
A.pending = A.pending or {}
local BatteryAction = ISBaseTimedAction:derive("SuQingPortalBatteryAction")
A.BatteryAction = BatteryAction

local function key(player) return player:getPlayerNum() end
function A.isBusy(player)
    local action = player and A.pending[key(player)]
    return action ~= nil and action.character == player
end

function A.adjacent(player, object)
    local square = object and object:getSquare()
    local current = player and player:getSquare()
    if not square or not current or math.floor(player:getZ()) ~= square:getZ() then return false end
    if math.abs(player:getX() - square:getX() - 0.5) > 1.8 or
        math.abs(player:getY() - square:getY() - 0.5) > 1.8 then return false end
    return current:canReachTo(square)
end

local function release(action)
    if A.pending[key(action.character)] == action then A.pending[key(action.character)] = nil end
end

function BatteryAction:isValid()
    if not self.object or self.object:getObjectIndex() == -1 or self.character:isDead() or
        self.character:getVehicle() or not A.adjacent(self.character, self.object) then return false end
    if P.Transfer and P.Transfer.isBusy(self.character) then return false end
    local state = P.World.getSnapshot(self.object)
    if not state or state.pending then return false end
    if self.command == "recoverLegacy" then return state.migrationRequired == true end
    if not state.storageReady or state.migrationRequired then return false end
    local slot = state.slots and state.slots[self.args.slot]
    if self.command == "install" then
        local item = self.character:getInventory():getItemWithIDRecursiv(self.args.itemId)
        return slot and slot.empty == true and P.Core.isBattery(item)
    end
    return slot and slot.itemId ~= nil and slot.itemId == self.args.itemId
end

function BatteryAction:waitToStart()
    self.character:faceThisObject(self.object)
    return self.character:shouldBeTurning()
end

function BatteryAction:start()
    self:setActionAnim("Loot")
    self.character:SetVariable("LootPosition", "Low")
end

function BatteryAction:update() self.character:faceThisObject(self.object) end

function BatteryAction:complete()
    if self.executed then return self.result == true end
    self.executed = true
    local ok, code
    if not self:isValid() then ok, code = false, "action_cancelled"
    else ok, code = P.World.command(self.character, self.object, self.command, self.args) end
    self.result = ok
    release(self)
    if self.onResult then self.onResult(ok, code) end
    return ok == true
end

function BatteryAction:perform()
    -- B42 calls complete for native world mutation. The SP fallback is guarded
    -- so either callback order still moves the original item exactly once.
    if not self.executed then self:complete() end
    release(self)
    ISBaseTimedAction.perform(self)
end

function BatteryAction:stop()
    release(self)
    if not self.executed and self.onResult then self.onResult(false, "action_cancelled") end
    ISBaseTimedAction.stop(self)
end

function BatteryAction:forceCancel() release(self) end

function BatteryAction:new(player, object, command, args, onResult)
    local o = ISBaseTimedAction.new(self, player)
    o.object, o.command, o.args, o.onResult = object, command, args, onResult
    o.stopOnWalk, o.stopOnRun = true, true
    o.maxTime = 45
    return o
end

function A.queue(player, object, command, args, onResult)
    if not player or player:isDead() then return false, "player_unavailable" end
    if isClient() or isServer() then return false, "singleplayer_only" end
    if A.isBusy(player) or (P.Transfer and P.Transfer.isBusy(player)) then return false, "player_busy" end
    if player:getVehicle() then return false, "in_vehicle" end
    if not object or not object:getSquare() then return false, "missing_portal" end
    if not luautils.walkAdjObject(player, object, true, true) then return false, "no_path" end
    local action = BatteryAction:new(player, object, command, args or {}, onResult)
    A.pending[key(player)] = action
    ISTimedActionQueue.add(action)
    return true, "action_queued"
end

return A
