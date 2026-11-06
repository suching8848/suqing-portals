require "SuQingPortals/Core"
require "TimedActions/ISTimedActionQueue"

local P = SuQingPortals
P.Transfer = P.Transfer or {}
local T = P.Transfer
T.active = T.active or {}
T.LOAD_TIMEOUT_MS = 20000

local function now() return getTimestampMs() end
local function key(player) return player:getPlayerNum() end
local function travelData(player) return player:getModData().SuQingPortalsTravel end
local function message(player, code)
    if P.UI and P.UI.resultText and player and not player:isDead() then player:Say(P.UI.resultText(code)) end
end

function T.isBusy(player)
    return player and (T.active[key(player)] ~= nil or travelData(player) ~= nil or
        (P.World and P.World.getPending and P.World.getPending(player) ~= nil)) or false
end

-- Verified against the local B42.21 jar: the true second argument writes the
-- existing cheat flag directly. No god mode, body-damage reset or healing.
local function captureFlags(player)
    return { ghost = player:isGhostMode(), noClip = player:isNoClip(), blockMovement = player:isBlockMovement() }
end

local function applyProtection(player)
    player:setNoClip(true, true)
    player:setGhostMode(true, true)
    player:setBlockMovement(true)
    return player:isNoClip() and player:isGhostMode() and player:isBlockMovement()
end

local function restoreFlags(player, flags)
    if not flags then return true end
    local allOK = true
    local operations = {
        function() player:setNoClip(flags.noClip == true, true) end,
        function() player:setGhostMode(flags.ghost == true, true) end,
        function() player:setBlockMovement(flags.blockMovement == true) end,
    }
    for _, operation in ipairs(operations) do
        local ok, errorText = pcall(operation)
        if not ok then
            allOK = false
            print("[SuQingPortals] protection restoration failed: " .. tostring(errorText))
        end
    end
    if player:isNoClip() ~= (flags.noClip == true) or player:isGhostMode() ~= (flags.ghost == true)
        or player:isBlockMovement() ~= (flags.blockMovement == true) then allOK = false end
    return allOK
end

local offsets = { { 0, 1 }, { 1, 0 }, { 0, -1 }, { -1, 0 } }
function T.front(record)
    local facing = (tonumber(record.facing) or 0) % 4
    local offset = offsets[facing + 1]
    return { x = math.floor(record.x) + offset[1], y = math.floor(record.y) + offset[2], z = math.floor(record.z) }
end

function T.safeSquare(square, player)
    if not square then return false, "destination_loading" end
    if not square:TreatAsSolidFloor() or not square:isFree(false) then return false, "unsafe_destination" end
    if square:isVehicleIntersecting() or square:haveFire() then return false, "unsafe_destination" end
    local moving = square:getMovingObjects()
    for index = 0, moving:size() - 1 do
        if moving:get(index) ~= player then return false, "destination_occupied" end
    end
    return true
end

function T.targetSquare(ticket, player)
    local target = ticket.target
    local cell = getCell()
    local anchor = cell:getGridSquare(target.x, target.y, target.z)
    if not anchor then return nil, "destination_loading" end
    local object = P.World.findObject(target)
    if not object then return nil, "missing_target" end
    local data = object:getModData().SuQingPortals
    if not data or data.id ~= ticket.targetId then return nil, "missing_target" end
    -- Revalidate the live identity and pairing, never just the saved position.
    local snapshot = P.World.getSnapshot(object)
    if not snapshot or snapshot.id ~= ticket.targetId or snapshot.pairId ~= ticket.sourceId then
        return nil, "missing_target"
    end
    local exit = T.front(target)
    local square = cell:getGridSquare(exit.x, exit.y, exit.z)
    local safe, code = T.safeSquare(square, player)
    if not safe then return nil, code end
    return square
end

local function move(player, position)
    player:teleportTo(math.floor(position.x), math.floor(position.y), math.floor(position.z))
end

local function cleanup(active, code, retainMarker)
    local player = active.player
    local restored = restoreFlags(player, active.marker.flags)
    if restored and not retainMarker then player:getModData().SuQingPortalsTravel = nil end
    T.active[key(player)] = nil
    if not restored then
        active.marker.phase = "flags_recovery_required"
        message(player, "flags_recovery_required")
    else message(player, code) end
end

local function beginReturn(active, code)
    active.failure = code or "transfer_failed"
    active.marker.phase = "returning"
    active.phase = "returning"
    active.deadline = now() + T.LOAD_TIMEOUT_MS
    move(active.player, active.ticket.origin)
end

local function waitForRecovery(active, code)
    active.failure = code or active.failure or "return_recovery_required"
    active.phase, active.marker.phase = "recovery_wait", "recovery_wait"
    active.nextCheck = now() + 1000
    if not active.recoveryNotice then
        active.recoveryNotice = true
        message(active.player, "recovery_wait")
    end
end

local function sourceSquare(active)
    local origin = active.ticket.origin
    local cell = getCell()
    local candidates = { {0,0}, {1,0}, {-1,0}, {0,1}, {0,-1}, {1,1}, {-1,-1}, {1,-1}, {-1,1} }
    for _, offset in ipairs(candidates) do
        local square = cell:getGridSquare(math.floor(origin.x) + offset[1], math.floor(origin.y) + offset[2], math.floor(origin.z))
        if T.safeSquare(square, active.player) then return square end
    end
    return nil
end

function T.begin(player, object)
    if isClient() or isServer() then return false, "singleplayer_only" end
    if not player or player:isDead() then return false, "player_unavailable" end
    if T.isBusy(player) then return false, "transfer_pending" end
    if P.Actions and P.Actions.isBusy(player) then return false, "player_busy" end
    if player:getVehicle() then return false, "in_vehicle" end
    if player:isOnFire() then return false, "player_on_fire" end
    if player:isBlockMovement() then return false, "player_busy" end
    if not P.World or not P.World.reserveTeleport then return false, "not_ready" end
    local square = object and object:getSquare()
    if not square then return false, "source_not_loaded" end
    local dx, dy = player:getX() - square:getX(), player:getY() - square:getY()
    if dx * dx + dy * dy > 9 or math.floor(player:getZ()) ~= square:getZ() then return false, "too_far" end
    if not T.safeSquare(player:getSquare(), player) then return false, "unsafe_origin" end
    local snapshot = P.World.getSnapshot(object)
    if not snapshot or not snapshot.canTeleport then
        return false, snapshot and (snapshot.reason or snapshot.migrationError or snapshot.containerError or (snapshot.pending and "portal_busy") or
            (snapshot.pairId and "insufficient_charge" or "unpaired")) or "not_ready"
    end
    local queue = ISTimedActionQueue.getTimedActionQueue(player)
    if queue and #queue.queue > 0 then return false, "player_busy" end
    local marker = { schema = 1, flags = captureFlags(player), phase = "protecting" }
    player:getModData().SuQingPortalsTravel = marker
    local protected, protectionResult = pcall(applyProtection, player)
    if not protected or not protectionResult then
        print("[SuQingPortals] protection could not be enabled: " .. tostring(protectionResult))
        local restored = restoreFlags(player, marker.flags)
        if restored then player:getModData().SuQingPortalsTravel = nil end
        return false, "protection_failed"
    end
    local reserved, ticket, code = pcall(P.World.reserveTeleport, player, object)
    if not reserved then
        print("[SuQingPortals] reservation failed: " .. tostring(ticket))
        ticket, code = nil, "transfer_failed"
    end
    if not ticket then
        local pending = P.World.getPending(player)
        if pending then
            marker.token = pending.token
            pending.clientFlags = marker.flags
            local active = { player = player, ticket = pending, marker = marker }
            T.active[key(player)] = active
            beginReturn(active, code)
            return true, "transfer_started"
        end
        local restored = restoreFlags(player, marker.flags)
        if restored then player:getModData().SuQingPortalsTravel = nil end
        return false, code
    end
    ticket.clientFlags = marker.flags
    marker.token, marker.phase = ticket.token, "loading_target"
    local active = { player = player, ticket = ticket, marker = marker, phase = "loading_target", deadline = now() + T.LOAD_TIMEOUT_MS }
    T.active[key(player)] = active
    local moved, errorText = pcall(move, player, T.front(ticket.target))
    if not moved then
        print("[SuQingPortals] teleport request failed: " .. tostring(errorText))
        beginReturn(active, "transfer_failed")
    end
    return true, "transfer_started"
end

function T.step(active)
    local player, ticket = active.player, active.ticket
    if not ticket then
        -- A saved temporary flag marker may outlive its completed journal.
        -- Recover flags independently; never invent a reservation or origin.
        if player:isDead() or T.safeSquare(player:getSquare(), player) then
            return cleanup(active, "protection_restored", false)
        end
        if not player:isNoClip() or not player:isGhostMode() or not player:isBlockMovement() then
            local protected = applyProtection(player)
            if not protected and not active.protectionNotice then
                active.protectionNotice = true
                message(player, "protection_failed")
            end
        end
        return
    end
    if player:isDead() then
        P.World.FinishTransfer(player, ticket.token, false, "player_died")
        return cleanup(active, "player_unavailable", false)
    end
    if not player:isNoClip() or not player:isGhostMode() or not player:isBlockMovement() then
        if not applyProtection(player) then return beginReturn(active, "protection_failed") end
    end
    if active.phase == "loading_target" then
        local square, code = T.targetSquare(ticket, player)
        if square then
            active.marker.phase = "target_validated"
            move(player, { x = square:getX(), y = square:getY(), z = square:getZ() })
            local ok, failure = P.World.FinishTransfer(player, ticket.token, true, "arrived")
            if ok then return cleanup(active, "arrived", false) end
            return beginReturn(active, failure)
        end
        if code ~= "destination_loading" then return beginReturn(active, code) end
        if now() >= active.deadline then return beginReturn(active, "destination_timeout") end
    elseif active.phase == "returning" then
        local square = sourceSquare(active)
        if square then
            move(player, { x = square:getX(), y = square:getY(), z = square:getZ() })
            local ok, failure = P.World.FinishTransfer(player, ticket.token, false, active.failure)
            if ok then return cleanup(active, "returned_refunded", false) end
            active.marker.phase = "refund_recovery_required"
            print("[SuQingPortals] returned but refund remains pending: " .. tostring(failure))
            return cleanup(active, "refund_recovery_required", true)
        end
        if now() >= active.deadline then
            print("[SuQingPortals] return loading timed out; retained travel protection and recovery journal")
            return waitForRecovery(active, "return_recovery_required")
        end
    elseif active.phase == "recovery_wait" then
        if now() < (active.nextCheck or 0) then return end
        active.nextCheck = now() + 1000
        local square = sourceSquare(active)
        if square then
            move(player, { x = square:getX(), y = square:getY(), z = square:getZ() })
            local ok, failure = P.World.FinishTransfer(player, ticket.token, false, active.failure)
            if ok then return cleanup(active, "returned_refunded", false) end
            print("[SuQingPortals] safe return found but charge recovery remains: " .. tostring(failure))
            return cleanup(active, "refund_recovery_required", true)
        end
    end
end

function T.tick()
    for _, active in pairs(T.active) do
        local ok, errorText = pcall(T.step, active)
        if not ok then
            print("[SuQingPortals] transfer interrupted: " .. tostring(errorText))
            local returned, returnError
            if active.phase == "returning" or active.phase == "recovery_wait" or active.phase == "flags_recovery" then
                returned = true
                if active.ticket then waitForRecovery(active, "return_recovery_required")
                else active.phase, active.marker.phase = "flags_recovery", "flags_recovery" end
            else returned, returnError = pcall(beginReturn, active, "transfer_failed") end
            if not returned then
                print("[SuQingPortals] return request also failed: " .. tostring(returnError))
                waitForRecovery(active, "return_recovery_required")
            end
        end
    end
end

function T.recover(player)
    if not player or isClient() or isServer() or T.active[key(player)] then return end
    local marker = travelData(player)
    local ticket = P.World and P.World.getPending and P.World.getPending(player)
    if not ticket then
        if marker then
            if T.safeSquare(player:getSquare(), player) then
                if restoreFlags(player, marker.flags) then player:getModData().SuQingPortalsTravel = nil end
            else
                applyProtection(player)
                marker.phase = "flags_recovery"
                T.active[key(player)] = { player = player, marker = marker, phase = "flags_recovery" }
                message(player, "recovery_wait")
            end
        end
        return
    end
    marker = marker or { schema = 1, flags = ticket.clientFlags or captureFlags(player) }
    marker.token = ticket.token
    player:getModData().SuQingPortalsTravel = marker
    if not applyProtection(player) then
        restoreFlags(player, marker.flags)
        return message(player, "protection_failed")
    end
    local atTarget = math.abs(player:getX() - ticket.target.x) <= 4 and
        math.abs(player:getY() - ticket.target.y) <= 4 and math.floor(player:getZ()) == math.floor(ticket.target.z)
    local active = { player = player, ticket = ticket, marker = marker, deadline = now() + T.LOAD_TIMEOUT_MS }
    T.active[key(player)] = active
    if atTarget then
        active.phase, marker.phase = "loading_target", "loading_target"
    else beginReturn(active, "interrupted_transfer") end
end

function T.retryRecovery(player)
    local active = T.active[key(player)]
    if active and active.ticket then
        active.recoveryNotice = nil
        beginReturn(active, "interrupted_transfer")
        return true
    end
    if active then return true end
    T.recover(player)
    return true
end

function T.onGameStart()
    for index = 0, 3 do
        local player = getSpecificPlayer(index)
        if player then
            local ok, errorText = pcall(T.recover, player)
            if not ok then
                print("[SuQingPortals] pending recovery failed: " .. tostring(errorText))
                local marker = travelData(player)
                local ticket = P.World and P.World.getPending and P.World.getPending(player)
                if marker then
                    local active = { player = player, marker = marker, ticket = ticket }
                    T.active[key(player)] = active
                    if ticket then waitForRecovery(active, "return_recovery_required")
                    else active.phase, marker.phase = "flags_recovery", "flags_recovery" end
                end
            end
        end
    end
end

if not T.eventsInstalled then
    T.eventsInstalled = true
    Events.OnTick.Add(T.tick)
    Events.OnGameStart.Add(T.onGameStart)
end

return T
