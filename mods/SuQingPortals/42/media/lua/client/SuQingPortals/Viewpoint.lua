-- Optional independent model pack. No replacement of Viewpoint's own resources.
require "SuQingPortals/VisualData"
SuQingPortals = SuQingPortals or {}
SuQingPortals.Visual = SuQingPortals.Visual or {}
local V = SuQingPortals.Visual
local facingIndex = { S = 0, E = 1, N = 2, W = 3 }
local registered = false

function V.spriteFor(facing, slotMask)
    local direction = tonumber(facing)
    if direction then direction = math.floor(direction) % 4
    else direction = facingIndex[tostring(facing)] or 0 end
    local mask = math.max(0, math.min(15, math.floor(tonumber(slotMask) or 0)))
    return "suqing_portal_01_" .. tostring(mask * 4 + direction)
end

function V.apply(object, slotMask, facing)
    if not object or not object.getSprite then return false end
    local sprite = object:getSprite()
    if not sprite or not sprite.getName then return false end
    local old = sprite:getName()
    local index = old and string.match(old, "^suqing_portal_01_(%d+)$")
    if not index then return false end
    local directions = { "S", "E", "N", "W" }
    local desired = V.spriteFor(facing or directions[(tonumber(index) % 4) + 1], slotMask)
    -- String setSprite creates a fresh texture-only sprite in the current PZ
    -- build. Keep the registered tiledef's collision/facing properties instead.
    if old ~= desired then
        if not object.setSpriteFromName then return false end
        object:setSpriteFromName(desired)
    end
    return true
end

-- All data is expressed in native 128x256 texture pixels before camera zoom.
-- The caller owns screen projection and must reverse that projection first.
function V.getMetadata(spriteName)
    local data = SuQingPortals.VisualData
    local record = data and data.sprites[spriteName]
    if not record then return nil end
    record.width, record.height = data.width, data.height
    record.anchorX, record.anchorY = data.anchorX, data.anchorY
    record.groundX, record.groundY = data.groundX, data.groundY
    record.alphaThreshold = data.alphaThreshold
    return record
end

function V.hitPixel(spriteName, localX, localY)
    local record = V.getMetadata(spriteName)
    local x, y = tonumber(localX), tonumber(localY)
    if not record or not x or not y or x ~= x or y ~= y then return false end
    if x < 0 or y < 0 or x >= record.width or y >= record.height then return false end
    x, y = math.floor(x), math.floor(y)
    local row = record.rows[y]
    if not row then return false end
    for offset = 1, #row, 2 do
        local left, right = string.byte(row, offset, offset + 1)
        if x >= left and x < right then return true end
    end
    return false
end

local function registerModels()
    if registered or not Viewpoint or not Viewpoint.ModelPacks then return end
    local ok, result = pcall(Viewpoint.ModelPacks.register,
        "SuQingPortals", "media/viewpoint/package.properties")
    if ok and result then
        registered = true
        print("[SuQingPortals] optional Viewpoint portal models registered")
    else
        print("[SuQingPortals] Viewpoint model registration failed: " .. tostring(result))
    end
end
registerModels()
Events.OnGameBoot.Add(registerModels)
Events.OnGameStart.Add(registerModels)
