require "ISUI/ISGeneratorInfoWindow"

SuQingPortals = SuQingPortals or {}
local P = SuQingPortals
P.PowerDisplay = P.PowerDisplay or {}
local D = P.PowerDisplay
D.depth = D.depth or 0

local function finite(value)
    value = tonumber(value)
    if value and value - value == 0 and value >= 0 then return value end
end

local function extraText(object, displayStats)
    if not displayStats or not P.Power or type(P.Power.loadForGenerator) ~= "function" then return nil end
    local load = P.Power.loadForGenerator(object)
    -- ISA's power-bank panel uses electrical units; the gas-generator panel
    -- must not label solar consumption as litres of fuel.
    if type(load) ~= "table" or load.solar then return nil end
    local count, fuel = finite(load.count), finite(load.fuelPerHour)
    if not count or count < 1 or not fuel then return nil end
    if not object or not object.getTotalPowerUsing then return nil end
    local native = finite(object:getTotalPowerUsing())
    if not native then return nil end
    -- The native getter already applies GeneratorFuelConsumption. The bridge
    -- reports the same multiplier in fuelPerHour; neither is multiplied here.
    return " <LINE> <RGB:1,1,1> " .. getText("IGUI_SQP_GeneratorLoad",
        tostring(math.floor(count)), string.format("%.4f", fuel)) .. " <LINE> " ..
        getText("IGUI_SQP_GeneratorTotal", string.format("%.4f", native + fuel)) .. " <LINE> "
end

function D.install()
    if not ISGeneratorInfoWindow or type(ISGeneratorInfoWindow.getRichText) ~= "function" then return false end
    if ISGeneratorInfoWindow.getRichText == D.wrapper then return true end
    local previous = ISGeneratorInfoWindow.getRichText
    local function wrapper(object, displayStats, ...)
        -- A later UI mod may wrap our previous wrapper. Reinstalling on that
        -- final function keeps its output, while only the outermost layer adds
        -- our two lines. Native errors still propagate and cannot poison depth.
        local outermost = D.depth == 0
        D.depth = D.depth + 1
        local ok, result = pcall(previous, object, displayStats, ...)
        D.depth = D.depth - 1
        if not ok then error(result) end
        if not outermost or type(result) ~= "string" then return result end
        local added, text = pcall(extraText, object, displayStats)
        if not added then
            local reason = tostring(text)
            if D.lastError ~= reason then
                D.lastError = reason
                print("[SuQingPortals] generator power display unavailable: " .. reason)
            end
            return result
        end
        return text and result .. text or result
    end
    D.previous, D.wrapper = previous, wrapper
    ISGeneratorInfoWindow.getRichText = wrapper
    return true
end

if Events and Events.OnGameStart and not D.startRegistered then
    Events.OnGameStart.Add(D.install)
    D.startRegistered = true
end

return D
