-- Run after core_world_bootstrap.lua and the client PowerDisplay.lua module.
-- No game main, world, renderer or native generator is created.
local P, D = SuQingPortals, SuQingPortals.PowerDisplay
local checks = 0
local function check(value, label)
    checks = checks + 1
    if not value then error(label) end
end
local function occurrences(text, needle)
    local count, at = 0, 1
    while true do
        local found = string.find(text, needle, at, true)
        if not found then return count end
        count, at = count + 1, found + #needle
    end
end

check(D ~= nil, "display module loaded")
check(Events.OnGameStart and #Events.OnGameStart.callbacks > 0, "installation waits for final loaded UI mods")
local originalText = "BGI: fuel and remaining time <LINE> Native total <LINE> <RED> toxic warning"
local originalCalls, nativeReads, sourceReads = 0, 0, 0
local load = {count=0, rawPerHour=0, fuelPerHour=0, solar=false}
local generator = {}
function generator:getTotalPowerUsing() nativeReads=nativeReads+1;return 0.4 end
function generator:setTotalPowerUsing() error("display must not mutate native load") end
function generator:setFuel() error("display must not mutate fuel") end
P.Power = {loadForGenerator=function(object)
    check(object == generator, "source query keeps the inspected generator")
    sourceReads=sourceReads+1
    return load
end}
ISGeneratorInfoWindow = {getRichText=function(object, displayStats, suffix)
    originalCalls=originalCalls+1
    check(object == generator, "original UI receives same object")
    return originalText .. (suffix or "")
end}
function getText(key, first, second)
    if key == "IGUI_SQP_GeneratorLoad" then return "PORTAL_LOAD(" .. tostring(first) .. "," .. tostring(second) .. ")" end
    if key == "IGUI_SQP_GeneratorTotal" then return "PORTAL_TOTAL(" .. tostring(first) .. ")" end
    error("unexpected translation key: " .. tostring(key))
end

Events.OnGameStart.run()
local firstWrapper=ISGeneratorInfoWindow.getRichText
check(type(firstWrapper) == "function", "game-start installation succeeds")
check(D.install() and ISGeneratorInfoWindow.getRichText == firstWrapper, "same final function is not wrapped twice")
check(firstWrapper(generator,true)==originalText, "no active charging leaves BGI text byte-for-byte unchanged")
check(nativeReads==0, "no active charging does not query native totals")
load={count=2,rawPerHour=0.15,fuelPerHour=0.3,solar=false}
local rendered=firstWrapper(generator,true," EXTRA")
check(string.sub(rendered,1,#originalText+6)==originalText.." EXTRA", "existing BGI details, warning and extra arguments are retained")
check(occurrences(rendered,"PORTAL_LOAD(2,0.3000)")==1, "portal count and already-scaled extra fuel are displayed once")
check(occurrences(rendered,"PORTAL_TOTAL(0.7000)")==1, "scaled native and bridge rates are added without multiplying again")
local beforeReads=sourceReads
check(firstWrapper(generator,false)==originalText, "stats-hidden text remains unchanged")
check(sourceReads==beforeReads, "stats-hidden panel never queries bridge")
load={count=1,rawPerHour=0.15,fuelPerHour=0,solar=false}
rendered=firstWrapper(generator,true)
check(string.find(rendered,"PORTAL_LOAD(1,0.0000)",1,true)~=nil, "zero-fuel sandbox multiplier remains zero")
check(string.find(rendered,"PORTAL_TOTAL(0.4000)",1,true)~=nil, "zero extra rate does not alter native subtotal")
load={count=1,rawPerHour=0.15,fuelPerHour=0.3,solar=true}
check(firstWrapper(generator,true)==originalText, "solar power bank is never labelled gas consumption")

-- A UI replacement may itself chain the previous wrapper. Reinstall once and
-- verify that the previous wrapper does not append a duplicate inside it.
ISGeneratorInfoWindow.getRichText=function(object,displayStats,...)
    return firstWrapper(object,displayStats,...).." LATER_BGI"
end
load={count=3,rawPerHour=0.2,fuelPerHour=0.6,solar=false}
check(D.install(), "later chained UI function can be wrapped")
local secondWrapper=ISGeneratorInfoWindow.getRichText
check(D.install() and ISGeneratorInfoWindow.getRichText==secondWrapper, "reinstallation is idempotent after another UI mod")
rendered=secondWrapper(generator,true)
check(string.find(rendered,"LATER_BGI",1,true)~=nil, "later UI wrapper output remains")
check(occurrences(rendered,"PORTAL_LOAD(")==1 and occurrences(rendered,"PORTAL_TOTAL(")==1, "nested old wrappers do not duplicate bridge rows")
check(string.find(rendered,"PORTAL_TOTAL(1.0000)",1,true)~=nil, "reinstalled chain reads current bridge rates")

-- Optional UI extensions fail open with a diagnostic; original errors remain
-- visible and do not leave a stale recursion guard on following renders.
P.Power.loadForGenerator=function() error("fixture bridge unavailable") end
check(secondWrapper(generator,true)==originalText.." LATER_BGI", "bridge failure preserves original and later UI text")
ISGeneratorInfoWindow.getRichText=function() error("fixture native UI failed") end
check(D.install(), "an independent replacement can be wrapped")
local succeeded=pcall(ISGeneratorInfoWindow.getRichText,generator,true)
check(not succeeded, "native UI failures propagate")
check(D.depth==0, "native UI failure restores wrapper depth")
ISGeneratorInfoWindow.getRichText=function() return originalText end
check(D.install(), "render chain can recover after native UI failure")
P.Power.loadForGenerator=function() return {count=1,fuelPerHour=0.15,solar=false} end
rendered=ISGeneratorInfoWindow.getRichText(generator,true)
check(string.find(rendered,"PORTAL_TOTAL(0.5500)",1,true)~=nil, "next healthy render adds display after an original failure")
for _, invalid in ipairs({{count=-1,fuelPerHour=0.1},{count=1,fuelPerHour=-0.1},{count=0/0,fuelPerHour=0.1},{count=1,fuelPerHour=0/0}}) do
    P.Power.loadForGenerator=function() return invalid end
    check(ISGeneratorInfoWindow.getRichText(generator,true)==originalText,"invalid bridge rate/count leaves original text")
end
P.Power=nil
check(ISGeneratorInfoWindow.getRichText(generator,true)==originalText,"absent optional bridge preserves the panel")
check(originalCalls>0 and nativeReads>0,"fixture exercised original UI and native total reads")
print("Power display checks="..tostring(checks).." failures=0")
