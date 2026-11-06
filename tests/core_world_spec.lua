local Core, World, T = SuQingPortals.Core, SuQingPortals.World, TEST
local function check(value, message) T.assert(value, message) end
local function near(actual, expected, message) T.near(actual, expected, message) end

local initialSandbox=SandboxVars
SandboxVars=nil;near(Core.getTransferCost(),2,"missing sandbox defaults to two")
SandboxVars={};near(Core.getTransferCost(),2,"missing portal settings default to two")
SandboxVars={SuQingPortals={}};near(Core.getTransferCost(),2,"missing cost defaults to two")
for _,row in ipairs({{0.5,0.5},{4,4},{2.35,2.35},{-20,0.5},{900,4},{0,0.5}}) do
    SandboxVars.SuQingPortals.TransferCost=row[1]
    near(Core.getTransferCost(),row[2],"finite transfer cost boundary")
end
for _,value in ipairs({1/0,-1/0,0/0,"invalid"}) do
    SandboxVars.SuQingPortals.TransferCost=value
    near(Core.getTransferCost(),2,"nonfinite or invalid cost defaults to two")
end
check(Core.TRANSFER_COST==2,"legacy constant remains the default value")
SandboxVars=initialSandbox

local halves = { T.battery(0.5), T.battery(0.5), T.battery(0.5), T.battery(0.5) }
local receipt = Core.debit(halves)
check(receipt and #receipt == 4, "four half-full original batteries fund one transfer")
near(Core.totalCharge(halves), 0, "cost is 2.0 across slots")
check(Core.refund(halves, receipt), "refund succeeds")
check(Core.refund(halves, receipt), "refund idempotent")
near(Core.totalCharge(halves), 2)
check(halves[1]:getCondition() == 80, "condition untouched")
local quantized = { T.battery(0.71234), T.battery(0.81234), T.battery(0.51234) }
for _, item in ipairs(quantized) do item.quantize = true end
check(Core.debit(quantized), "native UseDelta quantized charge accepted within tolerance")
near(Core.totalCharge(quantized), 0.03702)
local silent = { T.battery(1), T.battery(1) }
silent[2].silentFailNext = true
local silentReceipt, silentCode = Core.debit(silent)
check(not silentReceipt and silentCode == "battery_write_failed", "silent native no-op caught by readback")
near(Core.totalCharge(silent), 2, "readback failure rolls back previous battery")

local low = { T.battery(0.2), T.battery(0.3) }
local absent, lowCode = Core.debit(low)
check(not absent and lowCode == "insufficient_charge", "insufficient charge rejected before writes")
near(Core.totalCharge(low), 0.5)
check(not Core.isBattery(T.battery(1, "Base.Battery")), "handheld battery rejected")
near(Core.totalCharge({ T.battery(1, nil, 0), T.battery(1) }), 1, "destroyed battery unavailable")
local repeated = T.battery(1)
local repeatedReceipt, repeatedCode = Core.debit({ repeated, repeated })
check(not repeatedReceipt and repeatedCode == "duplicate_battery_id", "duplicate instance cannot fund two slots")
near(repeated.charge, 1, "duplicate check precedes writes")

local broken = { T.battery(1), T.battery(1) }
broken[2].failNext = true
local failure, failureCode = Core.debit(broken)
check(not failure and failureCode == "battery_write_failed", "native setter failure surfaced")
near(broken[1].charge, 1, "earlier writes rolled back")
near(broken[2].charge, 1, "throwing setter's partial write rolled back")
broken[2].failNext = true
local charged = Core.charge({ T.battery(0), broken[2] }, 2)
-- Full batteries do not call the setter; verify a genuinely partial charge.
broken[1].charge, broken[2].charge = 0, 0
broken[2].failNext = true
local chargeFailure = Core.charge(broken, 2)
check(chargeFailure == nil, "charging native failure surfaced")
near(Core.totalCharge(broken), 0, "charging rollback atomic")

local Slots = SuQingPortals.BatterySlots
check(SuQingPortalCodec == nil, "pure Lua runtime has no codec global")
local powerSquare=T.square(600,600,0,false)
local powerObject=T.object(powerSquare)
World.register(powerObject)
local power=World.powerInfo(powerObject)
check(power.loaded and power.powered==false and power.source=="none","loaded disconnected gate reports no local power")
powerSquare.grid=true
power=World.powerInfo(powerObject)
check(power.grid==false and power.powered==false and power.source=="none","outdoor grid availability never claims a usable connection")
powerSquare.room={}
power=World.powerInfo(powerObject)
check(power.grid and power.powered and power.source=="grid","indoor grid power positively identified")
powerSquare.grid,powerSquare.room,powerSquare.powered=false,nil,true
power=World.powerInfo(powerObject)
check(power.powered and power.generator==nil and power.source=="area","regional power without coverage evidence has unknown source")
function powerSquare:getGenerator() error("same-tile generator lookup must never identify coverage") end
local coverageCalls=0
powerSquare.chunk={isGeneratorPoweringSquare=function(self,x,y,z)
    coverageCalls=coverageCalls+1
    check(x==600 and y==600 and z==0,"native coverage query only inspects the current portal square")
    return true
end}
power=World.powerInfo(powerObject)
check(power.generator and power.source=="generator" and coverageCalls==1,"native chunk coverage positively identifies generator supply from any covered tile")
powerSquare.grid,powerSquare.room=true,{}
power=World.powerInfo(powerObject)
check(power.grid and power.generator and power.source=="grid_generator","simultaneous eligible grid and generator supplies remain visible")
powerSquare.chunk.isGeneratorPoweringSquare=function() return false end
power=World.powerInfo(powerObject)
check(power.powered and power.grid and power.generator==false and power.area and power.source=="grid_area","grid plus unconfirmed regional source is not mislabelled as generator")
powerSquare.grid,powerSquare.room=false,nil
power=World.powerInfo(powerObject)
check(power.powered and power.generator==false and power.source=="area","haveElectricity alone cannot override a negative native generator coverage result")
powerSquare.chunk.isGeneratorPoweringSquare=function() error("optional API unavailable") end
power=World.powerInfo(powerObject)
check(power.powered and power.source=="area" and power.generator==nil,"coverage API failure safely keeps unknown regional source")
check(World.localPower(powerObject)==true and World.State(powerObject).powerInfo.source=="area","display inspection never changes the legacy charging predicate")
powerSquare.powered=false
power=World.powerInfo(powerObject)
check(power.powered==false and power.generator==false and power.source=="none","power loss updates connection without stale generator guesses")
T.squares["600:600:0"]=nil
power=World.powerInfo(powerObject)
check(not power.loaded and power.powered==nil and power.source=="unknown","unloaded square reports unknown without reusing cached power")
check(World.powerInfo(nil).source=="unknown","missing square power remains unknown")
T.squares["600:600:0"]=powerSquare
local sourceSquare,targetSquare=T.square(100,100,0,true),T.square(10000,9000,0,false)
local source,target=T.object(sourceSquare),T.object(targetSquare,"suqing_portal_01_3")
local sourceRecord,targetRecord=World.register(source),World.OnCreate({thumpable=target})
check(sourceRecord and targetRecord and sourceRecord.id~=targetRecord.id,"unique stable portal IDs")
local internal=source:getContainer()
check(internal~=nil and source:getContainerCount()==1 and Slots.isInternalContainer(internal),"new gate has exactly one correctly marked native internal store")
check(internal.accept=="SuQingPortals.BatterySlots.AcceptItem" and not Slots.AcceptItem(internal,T.battery(1)),"all native external input rejected")
local impostor=T.container(source);impostor.type=Slots.CONTAINER_TYPE
check(not Slots.isInternalContainer(impostor),"same named unrelated container never filtered")
local alien=T.object(T.square(200,200,0,false));alien:setContainer(T.container(alien));alien.container.type=Slots.CONTAINER_TYPE
check(not Slots.isInternalContainer(alien.container),"type without exact portal marker insufficient")
local player=T.player(sourceSquare)
check(World.Pair(player,source,targetRecord.id),"pair gates")
local originals={}
for slot=1,4 do
    originals[slot]=T.battery(0.5,"Base.CarBattery"..tostring((slot-1)%3+1))
    originals[slot].customState="unique-original-"..slot
    player.inventory:AddItem(originals[slot])
    check(World.Install(player,source,originals[slot]:getID(),slot),"backend installs original")
    check(originals[slot]:getContainer()==internal and World.batteries(source)[slot]==originals[slot],"native container owns same original instance")
end
check(player.inventory:getItems():size()==0 and internal:getItems():size()==4,"one owner per original")
function internal:getAcceptItemFunction() return self.accept end
internal.accept=nil -- Native reload may omit the admission callback string.
local afterReload=Slots.ensure(source)
check(afterReload~=nil and internal.accept=="SuQingPortals.BatterySlots.AcceptItem","ensure rebinds missing native admission hook after reload")
check(afterReload[1]==originals[1] and afterReload[4]==originals[4] and internal:getItems():size()==4,"admission rebind preserves exact original instances")
local admissionSetter=internal.setAcceptItemFunction
internal.accept=nil;internal.setAcceptItemFunction=function() error("simulated admission binding failure") end
local protected,admissionError=Slots.ensure(source)
check(not protected and admissionError=="storage_conflict" and not World.State(source).storageReady,"failed admission rebind blocks storage management")
check(originals[1]:getContainer()==internal and internal:getItems():size()==4,"failed admission rebind cannot move or recreate originals")
internal.setAcceptItemFunction=admissionSetter
check(Slots.ensure(source)~=nil and internal.accept=="SuQingPortals.BatterySlots.AcceptItem","admission binding can retry without resetting storage")
check(World.State(source).slotMask==15 and source.sprite=="suqing_portal_01_60","four occupied positions")
check(World.Remove(player,source,2) and player.inventory:contains(originals[2]),"exclusive UI removes exact original")
check(World.State(source).slotMask==13 and originals[2]:getContainer()==player.inventory,"hole and owner readback")
check(World.Install(player,source,originals[2],2),"same original reinstalls")
local fifth=T.battery(1);player.inventory:AddItem(fifth)
check(not World.Install(player,source,fifth) and fifth:getContainer()==player.inventory,"fifth battery cannot enter")
local ticket=World.BeginTransfer(player,source)
check(ticket and World.State(target).batteryCount==0 and not World.State(target).powered,"arrival has no power requirement")
near(World.State(source).totalCharge,0)
check(not World.Remove(player,source,1),"busy source cannot remove batteries")
World.chargeTick();T.hours=T.hours+1;World.chargeTick()
near(World.State(source).totalCharge,0,"busy source cannot charge")
check(World.FinishTransfer(player,ticket.token,false,"cancelled"),"refund original native items")
near(World.State(source).totalCharge,2)
check(World.FinishTransfer(player,ticket.token,false),"refund idempotent")
near(World.State(source).totalCharge,2)
local realPersist=Slots.persist
Slots.persist=function() return false,"storage_conflict" end
local failed,failedCode=World.BeginTransfer(player,source)
Slots.persist=realPersist
check(not failed and failedCode=="storage_conflict","storage failure surfaced")
near(World.State(source).totalCharge,2,"storage failure rolls actual native charge back")
local pending=World.getPending(player)
check(pending and World.FinishTransfer(player,pending.token,false,"recovered"),"pending journal retained for recovery")
World.chargeTick();T.hours=T.hours+2;World.chargeTick()
near(World.State(source).totalCharge,3,"total native charge increases 0.5 per hour")
T.squares["100:100:0"]=nil;T.hours=T.hours+10;World.chargeTick()
T.squares["100:100:0"]=sourceSquare;T.hours=T.hours+10;World.chargeTick()
near(World.State(source).totalCharge,3,"unloaded time not charged")
Events.OnGameStart.run();T.hours=T.hours+20;World.chargeTick()
near(World.State(source).totalCharge,3,"restart not charged retroactively")
sourceSquare.powered,sourceSquare.grid,sourceSquare.room=false,true,nil
World.chargeTick();T.hours=T.hours+1;World.chargeTick()
near(World.State(source).totalCharge,3,"outdoor grid power alone rejected")
sourceSquare.room={};World.chargeTick();T.hours=T.hours+1;World.chargeTick()
near(World.State(source).totalCharge,3.5,"indoor grid power charges")
sourceSquare.powered,sourceSquare.grid,sourceSquare.room=true,false,nil

-- Even a non-UI bypass may not silently adopt or discard unexpected items.
player.inventory:Remove(fifth);internal:AddItem(fifth)
check(World.State(source).reason=="container_overflow" and not World.State(source).canTeleport,"fifth original readback fail-closed")
check(internal:contains(fifth),"overflow original never deleted")
internal:Remove(fifth);player.inventory:AddItem(fifth)
local foreign=T.battery(1,"Base.Nails");internal:AddItem(foreign)
check(World.State(source).reason=="container_overflow" or World.State(source).reason=="container_foreign_item","foreign original blocks source")
internal:Remove(foreign)
local removedOriginal=originals[1];internal:Remove(removedOriginal);player.inventory:AddItem(removedOriginal)
check(not World.State(source).storageReady,"missing mapped original never recreated")
player.inventory:Remove(removedOriginal);internal:AddItem(removedOriginal)
check(World.State(source).storageReady,"return exact original recovers slot mapping")

local legacySquare=T.square(300,300,0,false)
local legacy=T.object(legacySquare,"suqing_portal_01_11")
legacy.data.SuQingPortals={schema=1,id="legacy-existing",facing=3,slots={}}
legacy:setContainer(T.container(legacy));local oldContainer=legacy.container
local legacyOriginals={}
for slot=1,4 do
    legacyOriginals[slot]=T.battery(slot/4);legacyOriginals[slot].customState="old-original-"..slot
    oldContainer:AddItem(legacyOriginals[slot]);legacy.data.SuQingPortals.slots[slot]=legacyOriginals[slot]:getID()
end
local record=World.register(legacy)
check(record.id=="legacy-existing" and record.x==300 and record.facing==3,"legacy ID/coordinate/direction preserved")
check(legacy:getContainer()==oldContainer and oldContainer.removeCount==nil,"schema1 native storage adopted in place without moving any item")
check(legacy.data.SuQingPortals.schema==3 and Slots.isInternalContainer(oldContainer),"legacy native container now exclusive internal storage")
for slot=1,4 do check(World.batteries(legacy)[slot]==legacyOriginals[slot] and legacyOriginals[slot].customState=="old-original-"..slot,"legacy full originals unchanged") end

local badSquare=T.square(310,310,0,false);local bad=T.object(badSquare)
bad.data.SuQingPortals={schema=1,id="legacy-invalid",facing=0,slots={}}
bad:setContainer(T.container(bad))
for index=1,5 do bad.container:AddItem(T.battery(0.4)) end
bad.container:AddItem(foreign)
check(World.register(bad),"invalid old gate still discoverable for recovery")
check(World.State(bad).migrationError=="migration_legacy_invalid" and bad.container:getItems():size()==6,"invalid old originals retained")
local recoveryPlayer=T.player(badSquare,2)
check(World.command(recoveryPlayer,bad,"recoverLegacy",{}),"dedicated recovery takes actual old originals")
check(recoveryPlayer.inventory:getItems():size()==6 and recoveryPlayer.inventory:contains(foreign),"all old originals returned exactly once")
check(Slots.isInternalContainer(bad.container) and not World.State(bad).migrationRequired,"empty old container safely adopted")
check(not World.command(recoveryPlayer,bad,"recoverLegacy",{}),"repeat recovery cannot generate items")

local blobObject=T.object(T.square(340,340,0,false))
local opaque={schema=2,revision=7,slots={[2]={itemId=90001,payload="opaque-old-native-full-state"}}}
blobObject.data.SuQingPortals={schema=2,id="old-java-nonempty",facing=0,batteryStorage=opaque}
World.register(blobObject)
check(World.State(blobObject).reason=="legacy_java_storage" and blobObject:getContainer()==nil,"nonempty old Java storage not replaced by an empty native container")
check(blobObject.data.SuQingPortals.batteryStorage==opaque and opaque.slots[2].payload=="opaque-old-native-full-state","old opaque bytes retained intact")
local blockedPlayer=T.player(blobObject.square,3)
check(not World.command(blockedPlayer,blobObject,"recoverLegacy",{}),"pure Lua never pretends to decode old Java bytes")
local emptyJava=T.object(T.square(341,340,0,false))
emptyJava.data.SuQingPortals={schema=2,id="old-java-empty",facing=0,batteryStorage={schema=2,revision=0,slots={}}}
check(World.register(emptyJava) and emptyJava.data.SuQingPortals.schema==3 and Slots.isInternalContainer(emptyJava.container),"empty schema2 may adopt native storage")
local journalJava=T.object(T.square(342,340,0,false))
journalJava.data.SuQingPortals={schema=2,id="old-java-journal",facing=0,batteryStorage={schema=2,slots={}},migrationJournal={phase="prepared"}}
World.register(journalJava)
check(journalJava.data.SuQingPortals.schema==2 and journalJava.data.SuQingPortals.migrationJournal~=nil and journalJava:getContainer()==nil,"schema2 journal never cleared or assigned phantom originals")
local pendingJava=T.object(T.square(343,340,0,false))
pendingJava.data.SuQingPortals={schema=2,id="old-java-pending",facing=0,batteryStorage={schema=2,slots={}},pendingToken="opaque-ticket"}
World.register(pendingJava)
check(World.State(pendingJava).reason=="legacy_java_storage" and pendingJava.data.SuQingPortals.pendingToken=="opaque-ticket"
    and pendingJava:getContainer()==nil,"schema2 pending record preserved without creating an empty replacement")

local pendingSquare=T.square(320,320,0,false);local old=T.object(pendingSquare)
local oldData={schema=1,id="legacy-pending",facing=1,slots={},pendingToken="SQPT-legacy"}
old.data.SuQingPortals=oldData;old:setContainer(T.container(old));local oldPendingContainer=old.container
local a,b=T.battery(0),T.battery(0);old.container:AddItem(a);old.container:AddItem(b)
oldData.slots[1],oldData.slots[2]=a:getID(),b:getID()
local database=ModData.getOrCreate(World.STORE_KEY)
local oldTicket={token="SQPT-legacy",sourceId="legacy-pending",targetId=targetRecord.id,playerKey=player.data.SuQingPortalsPlayerId,playerNum=0,
    origin={x=320,y=320,z=0},target=targetRecord,receipt={{slot=1,itemId=a:getID(),before=1,after=0},{slot=2,itemId=b:getID(),before=1,after=0}}}
oldData.pendingTransfer=oldTicket;World.register(old)
check(oldData.schema==1 and database.pending[oldTicket.token]==oldTicket,"old pending ticket restored before migration")
player.square=pendingSquare
check(World.FinishTransfer(player,oldTicket.token,false,"returned"),"old pending settles real old batteries")
check(oldData.schema==3 and old.container==oldPendingContainer and World.batteries(old)[1]==a,"old pending container adopted only after settlement")
near(World.State(old).totalCharge,2)

player.square=sourceSquare;ticket=World.BeginTransfer(player,source)
check(ticket~=nil,"long-distance source reserves native charge")
player.square=targetSquare;T.squares["100:100:0"]=nil
check(World.FinishTransfer(player,ticket.token,true,"arrived"),"source unload still permits committed travel")
T.squares["100:100:0"]=sourceSquare
check(World.register(source) and not World.State(source).pending,"source reload settles exactly once")
near(World.State(source).totalCharge,1.5)
check(World.FinishTransfer(player,ticket.token,true,"repeat"),"repeat source settlement idempotent")
near(World.State(source).totalCharge,1.5)
player.square=sourceSquare
World.chargeTick();T.hours=T.hours+1;World.chargeTick()
near(World.State(source).totalCharge,2)
local failedTicket=World.BeginTransfer(player,source)
check(failedTicket~=nil,"failure-recovery source debited once")
T.squares["100:100:0"]=nil
local refunded,refundCode=World.FinishTransfer(player,failedTicket.token,false,"returning")
check(not refunded and refundCode=="source_not_loaded" and World.getPending(player)~=nil,"unloaded source retains original refund receipt")
T.squares["100:100:0"]=sourceSquare
check(World.FinishTransfer(player,failedTicket.token,false,"returned"),"returned source refunds original native batteries")
near(World.State(source).totalCharge,2)
check(World.FinishTransfer(player,failedTicket.token,false,"repeat"),"unload refund retry idempotent")
near(World.State(source).totalCharge,2)
local costSourceSquare,costTargetSquare=T.square(700,700,0,false),T.square(900,900,0,false)
local costSource,costTarget=T.object(costSourceSquare),T.object(costTargetSquare)
World.register(costSource);local costTargetRecord=World.register(costTarget)
local costPlayer=T.player(costSourceSquare,1)
check(World.Pair(costPlayer,costSource,costTargetRecord.id),"cost regression gates paired")
for slot=1,4 do
    local battery=T.battery(1);costPlayer.inventory:AddItem(battery)
    check(World.Install(costPlayer,costSource,battery,slot),"cost regression full native battery installed")
end
SandboxVars={SuQingPortals={TransferCost=0.5}}
near(World.State(costSource).cost,0.5,"snapshot exposes actual configured cost")
check(World.State(costSource).canTeleport,"half-unit trip available")
local lowCostTicket=World.BeginTransfer(costPlayer,costSource)
check(lowCostTicket and lowCostTicket.cost==0.5,"ticket freezes half-unit reservation cost")
near(World.State(costSource).totalCharge,3.5,"half-unit cost charged only once")
SandboxVars.SuQingPortals.TransferCost=4
check(World.FinishTransfer(costPlayer,lowCostTicket.token,false,"cost_changed"),"refund settles reserved receipt after config changes")
near(World.State(costSource).totalCharge,4,"refund restores original half unit, not the new four-unit price")
check(World.FinishTransfer(costPlayer,lowCostTicket.token,false,"repeat"),"changed-price refund remains idempotent")
near(World.State(costSource).totalCharge,4)
local fullCostTicket=World.BeginTransfer(costPlayer,costSource)
check(fullCostTicket and fullCostTicket.cost==4,"maximum cost reservation freezes four units")
near(World.State(costSource).totalCharge,0,"maximum cost consumes four full originals across slots")
SandboxVars.SuQingPortals.TransferCost=0.5
check(World.FinishTransfer(costPlayer,fullCostTicket.token,true,"cost_changed"),"completion does not recalculate a pending price")
near(World.State(costSource).totalCharge,0,"lowering cost does not refund or recharge a successful old ticket")
check(World.FinishTransfer(costPlayer,fullCostTicket.token,true,"repeat"),"changed-price commit remains idempotent")
near(World.State(costSource).totalCharge,0)
Core.charge(World.batteries(costSource),0.5)
check(Slots.persist(costSource,World.batteries(costSource)),"half-unit threshold fixture retains native ownership")
check(World.State(costSource).canTeleport,"half-unit balance satisfies configured half-unit trip")
SandboxVars.SuQingPortals.TransferCost=4
check(not World.State(costSource).canTeleport,"same balance insufficient at four-unit setting")
local rejectedCost,rejectedCode=World.BeginTransfer(costPlayer,costSource)
check(not rejectedCost and rejectedCode=="insufficient_charge","reservation enforces the same configured cost as snapshot")
near(World.State(costSource).totalCharge,0.5,"insufficient charge never mutates originals")
SandboxVars=initialSandbox
recoveryPlayer.inventory:Remove(foreign);internal:AddItem(foreign)
Events.OnObjectAboutToBeRemoved.run(source)
check(#sourceSquare.dropped==5 and internal:getItems():size()==0,"destruction returns all actual originals even if external contents invalidated slots")
check(World.State(target).pairId==nil,"removed source clears opposite pairing")
print("Core/World pure-Lua internal-slot assertions passed: "..tostring(T.checks))
