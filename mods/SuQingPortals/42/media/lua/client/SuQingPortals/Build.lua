require "SuQingPortals/Core"

local P = SuQingPortals
P.Build = P.Build or {}
local B = P.Build

function B.isPortal(object)
    if not object or not object.getSprite then return false end
    local sprite = object:getSprite()
    local name = sprite and sprite:getName()
    return type(name) == "string" and string.match(name, "^suqing_portal_01_%d+$") ~= nil
end

return B
