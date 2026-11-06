local P,W,C,T=SuQingPortals,SuQingPortals.World,SuQingPortals.Core,SuQingPortals.Transfer
local function check(value,label) TEST.assert(value,label) end
local function near(actual,expected,label) TEST.near(actual,expected,label) end
local function charge(object) return W.getSnapshot(object).totalCharge end
local function fixture()
    TEST.reset()
    local origin=TEST.square(0,0,0,false)
    local sourceSquare=TEST.square(1,0,0,false);sourceSquare.free=false
    local targetSquare=TEST.square(10000,10000,0,false);targetSquare.free=false
    local exit=TEST.square(10000,10001,0,false)
    local source,target=TEST.object(sourceSquare),TEST.object(targetSquare)
    local sourceRecord,targetRecord=W.register(source),W.register(target)
    local player=TEST.player(origin)
    for slot=1,4 do
        local battery=TEST.battery(1)
        player:getInventory():AddItem(battery)
        check(W.Install(player,source,battery,slot),"fixture installs original battery")
    end
    check(W.Pair(player,source,targetRecord.id),"fixture pairs empty unpowered arrival")
    return player,source,target,origin,exit,targetSquare
end

-- Destination loading is genuinely pending, then validates the real gate.
local player,source,target,origin,exit,anchor=fixture()
TEST.squares['10000:10000:0'],TEST.squares['10000:10001:0']=nil,nil
local started,code=T.begin(player,source)
check(started and code=='transfer_started',"long-range trip can begin without loaded target")
near(charge(source),2,"two full-battery equivalents reserved at source only")
check(player.noClip and player.ghost and player.block,"streaming protection enabled")
T.tick()
check(T.isBusy(player) and W.getPending(player),"unloaded square is unknown, not successful arrival")
TEST.squares['10000:10000:0'],TEST.squares['10000:10001:0']=anchor,exit
T.tick()
check(not T.isBusy(player) and not W.getPending(player),"safe live target commits trip")
check(not player.noClip and not player.ghost and not player.block,"original flags restored after arrival")
near(charge(source),2,"successful trip does not debit twice")
near(W.getSnapshot(target).totalCharge,0,"arrival battery bank remains empty")
check(not W.getSnapshot(target).powered,"arrival is permitted without power")

-- A live obstruction returns the same character and refunds its original items.
player,source,target,origin,exit=fixture()
exit.vehicle=true
check(T.begin(player,source),"trip starts before final live obstruction check")
T.tick();T.tick()
near(player:getX(),0,"unsafe destination returns to original tile")
near(charge(source),4,"failed arrival refunds exact original battery charges")
check(not T.isBusy(player) and not player.noClip,"successful return releases protection and lock")

-- A replacement object at the right position is not the registered endpoint.
player,source,target,origin,exit=fixture()
check(T.begin(player,source),"identity test begins")
target:getModData().SuQingPortals.id='foreign-copy'
T.tick();T.tick()
near(charge(source),4,"wrong live gate ID cannot commit")
check(player:getX()==0 and not T.isBusy(player),"identity mismatch returns and unlocks")

-- A target timeout and unsafe/unloaded origin must retain the journal/flags.
player,source,target,origin,exit=fixture()
TEST.squares['10000:10000:0'],TEST.squares['10000:10001:0']=nil,nil
check(T.begin(player,source),"timeout test begins")
TEST.clock=21000;T.tick()
origin.floor=false
TEST.clock=42000;T.tick()
check(T.active[0] and T.active[0].phase=='recovery_wait',"unsafe return enters persistent recovery wait")
check(player.noClip and player.ghost and player.block,"unverified floor never loses protection")
check(player:getModData().SuQingPortalsTravel~=nil and W.getPending(player)~=nil,"return fault retains both recovery records")
local attempts=player.moveCount
TEST.clock=45000;T.tick()
check(player.moveCount==attempts,"waiting does not spam native teleports")
origin.floor=true
TEST.clock=47000;T.tick()
near(charge(source),4,"later safe origin settles the same refund")
check(not T.isBusy(player) and not player.noClip,"later safe origin releases original flags")

-- Save/reload resumes a reserved trip without another debit.
player,source,target,origin,exit=fixture()
check(T.begin(player,source),"reload test begins")
T.active={}
T.onGameStart();T.tick()
check(not T.isBusy(player),"saved pending trip revalidates loaded target")
near(charge(source),2,"reload recovery never pays another trip cost")
check(not player.ghost and not player.noClip and not player.block,"reload restores pre-trip flags")

-- Pre-existing user flags remain unchanged.
player,source,target,origin,exit=fixture()
player.noClip,player.ghost=true,true
check(T.begin(player,source),"existing-flags test begins")
T.tick()
check(player.noClip and player.ghost and not player.block,"existing user flags are preserved exactly")

-- Readback failure prevents payment and any native movement.
player,source,target,origin,exit=fixture()
player.rejectProtection=true
local ok,failure=T.begin(player,source)
check(not ok and failure=='protection_failed',"protection readback failure is visible")
near(charge(source),4,"failed protection pays nothing")
check(not player.moveCount and not T.isBusy(player),"failed protection leaves original position and no stale lock")

-- No-ticket flags recovery handles death and failed restoration independently.
player,source,target,origin,exit=fixture()
player.noClip,player.ghost,player.block=true,true,true
player:getModData().SuQingPortalsTravel={flags={noClip=false,ghost=false,blockMovement=false},phase='flags_recovery'}
origin.floor=false
T.recover(player)
check(T.active[0] and T.active[0].ticket==nil,"marker-only unsafe recovery needs no invented ticket")
player.dead=true;T.tick()
check(not T.active[0] and not player.noClip,"marker-only death cleanup does not dereference a ticket")
player,source,target,origin,exit=fixture()
player.noClip=true;player.rejectRestore=true
player:getModData().SuQingPortalsTravel={flags={noClip=false,ghost=false,blockMovement=false},phase='flags_recovery'}
T.recover(player)
check(player:getModData().SuQingPortalsTravel~=nil,"failed flag restoration retains original values for retry")
player.rejectRestore=false;T.retryRecovery(player)
check(player:getModData().SuQingPortalsTravel==nil and not player.noClip,"manual retry restores original flags")

-- A native teleport exception returns/refunds rather than leaking flags.
player,source,target,origin,exit=fixture()
player.failMoveOnce=true
check(T.begin(player,source),"native move failure starts a bounded return")
T.tick()
near(charge(source),4,"native movement exception refunds source")
check(not player.noClip and not T.isBusy(player),"native movement exception restores original flags")

-- Active pending transfers reject duplicate button clicks.
player,source,target,origin,exit=fixture()
check(T.begin(player,source),"duplicate click test begins")
local again,againCode=T.begin(player,source)
check(not again and againCode=='transfer_pending',"duplicate teleport button click rejected")
near(charge(source),2,"duplicate click never debits again")
T.tick()



-- Real schema-2 slots plus native-action mocks: no ordinary loot container.
player,source,target,origin,exit=fixture()
check(source:getContainerCount()==1 and P.BatterySlots.isInternalContainer(source:getContainer()),'pure Lua portal owns one precisely identified native internal bank')
local removedId=W.getSnapshot(source).slots[4].itemId
check(W.Remove(player,source,4),'prepare an empty dedicated slot')
local original=player:getInventory():getItemWithIDRecursiv(removedId)
local callbackCount=0
check(P.Actions.queue(player,source,'install',{itemId=removedId,slot=4},function() callbackCount=callbackCount+1 end),'queue original battery install')
local action=TEST.queued[#TEST.queued]
check(player:getInventory():contains(original),'queued install does not move item early')
check(not P.Actions.queue(player,source,'install',{itemId=removedId,slot=4}),'duplicate battery action is rejected')
check(action:complete(),'completed adjacent action installs original')
action:perform()
check(callbackCount==1,'native complete/perform callback order mutates and notifies once')
check(P.BatterySlots.read(source)[4]==original,'runtime slot owns the exact original instance')
check(not player:getInventory():contains(original),'original battery leaves the original inventory once')
check(P.BatterySlots.isInternalContainer(source:getContainer()),'dedicated-slot installation retains only its native internal bank')
check(P.Actions.queue(player,source,'remove',{slot=4,itemId=removedId}),'queue removal by current original ID')
action=TEST.queued[#TEST.queued]
action:stop()
check(W.getSnapshot(source).slots[4].itemId==removedId,'cancelled remove keeps the same original battery in its slot')
check(not P.Actions.isBusy(player),'cancelled action releases client operation lock')

-- Final action validity refuses distance, wrong-floor and blocked reach.
player.x=10.5
check(P.Actions.queue(player,source,'remove',{slot=4,itemId=removedId}),'direct menu queues approach before removing')
action=TEST.queued[#TEST.queued]
check(not action:isValid(),'far-away completion is not allowed')
check(not action:complete(),'forced completion at a distance changes no storage')
action:perform()
check(W.getSnapshot(source).slots[4].itemId==removedId,'distant action never removes battery')
player.x,player.y=0.5,0.5
origin.unreachable=true
check(not P.Actions.adjacent(player,source),'closed collision reach refuses remote battery access')
origin.unreachable=false
TEST.pathBlocked=true
local pathOK,pathCode=P.Actions.queue(player,source,'remove',{slot=4,itemId=removedId})
check(not pathOK and pathCode=='no_path','failed approach yields an explicit path reason')
TEST.pathBlocked=false

-- A swapped slot between queue and completion cannot remove a replacement.
check(P.Actions.queue(player,source,'remove',{slot=4,itemId=removedId}),'queue original-slot identity test')
action=TEST.queued[#TEST.queued]
check(W.Remove(player,source,4),'external original removal fixture')
local replacement=TEST.battery(0.25);player:getInventory():AddItem(replacement)
check(W.Install(player,source,replacement,4),'external replacement fixture')
check(not action:complete(),'slot ID mismatch cancels stale remove')
action:perform()
check(W.getSnapshot(source).slots[4].itemId==replacement:getID(),'stale action cannot take the replacement')

-- Exercise the production window against production World.getSnapshot.
player,source,target,origin,exit=fixture()
local window=P.UI.open(player,source)
check(#window.slotButtons==4 and #window.slotCards==4,'management UI exposes exactly four independent slot cards')
check(window.content.scrollHeight<=window.content.height,'default management keeps all four 2x2 slots and pairing controls in view')
check(window.teleportButton.enabled==true and not window.blockReason,'ready paired gate enables the large teleport button')
TEST.drawn={}
window:renderContent(window.content);window:render()
check(#TEST.drawn>12,'management renders slot names, durability, charge and status summary')
check(W.Remove(player,source,3),'empty-slot presentation fixture')
window:refresh(false)
check(window.slotButtons[3].title=='IGUI_SQP_Install','empty=true slot renders Install rather than Remove')
check(window.slotButtons[1].title=='IGUI_SQP_Remove','occupied slot renders Remove')
W.Unpair(player,source);window:refresh(false)
check(window.blockReason=='unpaired' and window.teleportButton.enabled==false,'disabled teleport states its actual unpaired reason')
window:close()

-- Power availability is independent of charging eligibility and stored charge.
player,source,target,origin,exit=fixture()
local sourceSquare=source:getSquare()
window=P.UI.open(player,source)
local label,powered=P.UI.powerText(window.snapshot)
check(powered==false and label=='IGUI_SQP_PowerDisconnected','disconnected gate explicitly states no local power')
check(P.UI.chargingState(window.snapshot)=='ChargingFull','full healthy batteries do not falsely report active charging even when disconnected')
P.BatterySlots.read(source)[1]:setUsedDelta(0.5);window:refresh(false)
check(P.UI.chargingState(window.snapshot)=='ChargingUnpowered','partly discharged batteries need local power to charge')
sourceSquare.powered=true
sourceSquare.chunk={isGeneratorPoweringSquare=function() return true end}
TEST.generator(sourceSquare,10);P.Power.refreshSources()
window:refresh(false)
label,powered=P.UI.powerText(window.snapshot)
check(powered==true and label:find('IGUI_SQP_PowerSource_generator',1,true),'verified native chunk coverage names generator power')
check(P.UI.chargingState(window.snapshot)=='ChargingActive','loaded powered gate with healthy nonfull batteries reports charging')
P.BatterySlots.read(source)[1]:setUsedDelta(1);window:refresh(false)
check(P.UI.chargingState(window.snapshot)=='ChargingFull','connected power and charging stopped because full are separate states')
for slot=1,4 do P.BatterySlots.read(source)[slot].condition=0 end
window:refresh(false)
check(P.UI.chargingState(window.snapshot)=='ChargingDamaged','a powered bank of broken batteries cannot claim active charging')
for slot=1,4 do check(W.Remove(player,source,slot),'remove broken original for empty-bank status') end
window:refresh(false)
check(P.UI.chargingState(window.snapshot)=='ChargingNoBattery','powered empty receiver says no battery rather than charging')
check(select(2,P.UI.powerText(window.snapshot))==true,'empty battery slots do not change local power availability')
local unknown={storageReady=true,slots={{itemId=1,condition=80,charge=0.5}}}
check(select(2,P.UI.powerText(unknown))==nil and P.UI.chargingState(unknown)=='ChargingUnknown','missing power query fails to explicit unknown')
unknown.loaded=false
check(P.UI.chargingState(unknown)=='ChargingUnloaded','an unloaded gate cannot be described as charging')
unknown.loaded=true;unknown.powerInfo={powered=true,source='unverified-vendor'}
check(P.UI.powerText(unknown):find('IGUI_SQP_PowerSource_area',1,true),'unrecognized powered source retains its unconfirmed-area label')
unknown.chargeError='battery_write_failed'
check(P.UI.chargingState(unknown)=='ChargingFault','charge errors remain visible instead of promising active charging')
unknown.pending=true
check(P.UI.chargingState(unknown)=='TravelBusy','pending travel states its charging lock')
check(P.UI.chargingState({migrationRequired=true,storageReady=false})=='MigrationStatus','legacy migration notice takes precedence over generic storage unavailability')
window:close()

-- Resize geometry uses current native title/footer metrics and anchor behavior.
local function checkLayout(ui,scrollExpected)
    local panel=ui.content
    check(ui.resizable and ui.resizeWidget.visible and ui.resizeWidget2.visible,'native corner and bottom resize handles remain active')
    check(panel.x>=0 and panel.y>=ui:titleBarHeight() and panel.x+panel.width<=ui.width,'content stays inside the window frame')
    check(panel.y+panel.height+6<=ui.teleportButton.y,'content never covers the fixed transfer footer')
    check(ui.messageY+ui.fontH<ui.resizeWidget.y,'reason and action-message lines leave native resize footer free')
    check(ui.teleportButton.y+ui.teleportButton.height<ui.reasonY,'transfer button and reason line do not overlap')
    local a,b,c,d=ui.slotCards[1],ui.slotCards[2],ui.slotCards[3],ui.slotCards[4]
    check(a.y==b.y and c.y==d.y and a.x==c.x and b.x==d.x,'four battery slots always remain in a 2x2 grid')
    check(a.x+a.w<=b.x and c.x+c.w<=d.x and a.y+a.h<=c.y,'adjacent slot cards do not overlap')
    for slot=1,4 do
        local card,button=ui.slotCards[slot],ui.slotButtons[slot]
        check(button.x>=card.x and button.y>=card.y and button.x+button.width<=card.x+card.w and button.y+button.height<=card.y+card.h,'battery action remains within card '..slot)
    end
    check(ui.pairTitleY>=c.y+c.h and ui.pairButton.y+ui.pairButton.height<=panel.scrollHeight,'pairing controls follow all four slots and remain reachable')
    check((panel.scrollHeight>panel.height)==scrollExpected,'scroll fallback matches actual available layout height')
end
for _,resolution in ipairs({{1366,768},{1920,1080}}) do
    for _,font in ipairs({16,24}) do
        TEST.screenWidth,TEST.screenHeight,TEST.fontH=resolution[1],resolution[2],font
        player,source,target,origin,exit=fixture()
        window=P.UI.open(player,source)
        checkLayout(window,false)
        window.nameEntry:setText('Unfinished name')
        window.targetCombo.selected=2
        local selectedId=window.targetCombo:getOptionData(2)
        window:setWidth(window.width+100);window:setHeight(window.height+30)
        local baseCalls=TEST.nativeResizeCalls or 0
        window:onResize()
        check(TEST.nativeResizeCalls==baseCalls+1,'resize delegates to native ISUIElement minimum-size handling')
        checkLayout(window,false)
        check(window.nameEntry:getText()=='Unfinished name' and window.targetCombo:getOptionData(window.targetCombo.selected)==selectedId,'reflow preserves typed names and selected destination')
        window:setWidth(1);window:setHeight(1);window:onResize()
        check(window.width==window.minimumWidth and window.height==window.minimumHeight,'dragging smaller respects native minimum dimensions')
        checkLayout(window,window.content.scrollHeight>window.content.height)
        window:setWidth(4000);window:setHeight(2000);window:setX(4000);window:setY(-200)
        window:onResize()
        check(window.width<=TEST.screenWidth-40 and window.height<=TEST.screenHeight-40 and window.x>=0 and window.y>=0 and window.x+window.width<=TEST.screenWidth and window.y+window.height<=TEST.screenHeight,'oversized or offscreen resize stays reachable on the current display')
        checkLayout(window,false)
        window:close()
    end
end
TEST.screenWidth,TEST.screenHeight,TEST.fontH=1024,600,24
player,source,target,origin,exit=fixture();window=P.UI.open(player,source)
checkLayout(window,true)
check(window.content.scrollHeight>window.content.height,'smaller display retains scrolling rather than hiding pairing controls')
window:close()
TEST.screenWidth,TEST.screenHeight,TEST.fontH=nil,nil,nil

-- Actual alpha metadata gates ordinary-isometric fallback to visible pixels.
player,source,target,origin,exit=fixture()
TEST.picked=nil;Viewpoint=nil;TEST.zoom=1
local spriteName=source:getSprite():getName()
local meta=P.Visual.getMetadata(spriteName)
check(meta and meta.width==128 and meta.height==256,'client receives the actual cropped visual metadata')
local hitX,hitY
for y,row in pairs(meta.rows) do if #row>=2 then hitX,hitY=string.byte(row,1),y;break end end
local function screenPoint(object,x,y)
    local square=object:getSquare()
    return (IsoUtils.XToScreen(square:getX(),square:getY(),square:getZ(),0)-IsoCamera.getOffX(0)+x-meta.anchorX)/(TEST.zoom or 1),
        (IsoUtils.YToScreen(square:getX(),square:getY(),square:getZ(),0)-IsoCamera.getOffY(0)+y-meta.anchorY)/(TEST.zoom or 1)
end
local mouseX,mouseY=screenPoint(source,hitX,hitY)
check(P.Client.hitPortal(source,0,mouseX,mouseY),'visible frame/base pixel is clickable')
local picked=P.Client.findPortals(0,{},mouseX,mouseY)
check(#picked==1 and picked[1]==source,'precise fallback finds its own actual portal')
TEST.zoom=2
mouseX,mouseY=screenPoint(source,hitX,hitY)
check(P.Client.hitPortal(source,0,mouseX,mouseY),'alpha fallback reverses camera zoom correctly')
TEST.zoom=1
mouseX,mouseY=screenPoint(source,0,0)
check(not P.Client.hitPortal(source,0,mouseX,mouseY),'transparent sprite padding is not an interaction target')
check(#P.Client.findPortals(0,{source},mouseX,mouseY)==0,'transparent ground does not gain a menu from an arbitrary nearby portal')
local holeX,holeY
for y=70,180 do
    for x=45,82 do if not P.Visual.hitPixel(spriteName,x,y) then holeX,holeY=x,y;break end end
    if holeX then break end
end
if holeX then
    mouseX,mouseY=screenPoint(source,holeX,holeY)
    check(#P.Client.findPortals(0,{source},mouseX,mouseY)==0,'transparent gate opening does not create a portal menu')
end
TEST.picked=target
picked=P.Client.findPortals(0,{source},0,0)
check(#picked==1 and picked[1]==target,'direct native IsoObject picker result precedes projected/world-object candidates')
check(TEST.contextPickCalls==0,'right-click logic never consumes opaque ClickObject or its Java fields')
check(TEST.pickThumpableCalls>0 and TEST.lastPickerX==0 and TEST.lastPickerY==0,'direct native picker receives unchanged screen coordinates')
TEST.picked=nil
Viewpoint={View={next=function() return 'third' end,cycle=function() error('must never switch the camera') end}}
check(not P.Client.twoDFallbackAllowed(0),'first-person camera blocks isometric projection fallback')
TEST.picked=target
check(P.Client.findPortals(0,{source},0,0)[1]==target,'Viewpoint camera still prioritizes the direct native IsoObject hit')
TEST.picked=nil
mouseX,mouseY=screenPoint(source,hitX,hitY)
check(#P.Client.findPortals(0,{},mouseX,mouseY)==0,'3D camera cannot gain a false 2D alpha hit')
check(P.Client.findPortals(0,{source},mouseX,mouseY)[1]==source,'3D camera retains its native world-object hit')
Viewpoint.View.next=function() return 'isometric' end
check(not P.Client.twoDFallbackAllowed(0),'third-person camera also blocks isometric projection fallback')
Viewpoint.View.next=function() return 'first' end
check(P.Client.twoDFallbackAllowed(0),'read-only next=first identifies current ordinary isometric camera')
Viewpoint={}
check(not P.Client.twoDFallbackAllowed(0),'unknown optional camera API fails closed for projected clicks')
Viewpoint=nil
local nativePicker=IsoObjectPicker.Instance.PickThumpable
IsoObjectPicker.Instance.PickThumpable=function() error('native-picker-error-remains-visible') end
local pickerOK,pickerError=pcall(P.Client.findPortals,0,{},0,0)
check(not pickerOK and tostring(pickerError):find('native-picker-error-remains-visible',1,true),'native picker errors propagate without a production catch-all')
IsoObjectPicker.Instance.PickThumpable=nativePicker

-- Context-menu installation finds the first empty slot and nested originals.
player,source,target,origin,exit=fixture()
local nestedId=W.getSnapshot(source).slots[2].itemId
check(W.Remove(player,source,2),'empty slot for automatic direct installation')
local nested=player:getInventory():getItemWithIDRecursiv(nestedId)
player:getInventory():Remove(nested)
local bagInventory=TEST.container();bagInventory:AddItem(nested)
local bag={getInventory=function() return bagInventory end,getID=function() return -25 end}
player:getInventory():AddItem(bag)
local candidates=P.UI.collectBatteries(player:getInventory())
check(#candidates==1 and candidates[1]==nested,'battery chooser includes original batteries inside a backpack')
P.Client.queueInstall(player,source,nestedId)
action=TEST.queued[#TEST.queued]
check(action and action.args.slot==2,'direct install selects the actual first empty slot')
check(action:complete(),'direct install moves the nested original only after adjacency completion')
action:perform()
check(P.BatterySlots.read(source)[2]==nested and not bagInventory:contains(nested),'original nested battery is owned by exactly one dedicated slot')

-- When opaque projections overlap, choose the foremost real gate only.
player,source,target,origin,exit=fixture()
local front=TEST.object(TEST.square(2,1,0,false));W.register(front)
local backName,frontName=source:getSprite():getName(),front:getSprite():getName()
local commonX,commonY
for y=64,255 do
    for x=0,127 do
        if P.Visual.hitPixel(backName,x,y) and P.Visual.hitPixel(frontName,x,y-64) then commonX,commonY=x,y;break end
    end
    if commonX then break end
end
check(commonX~=nil,'overlap fixture contains actual opaque pixels from both gate sprites')
TEST.picked=nil;Viewpoint=nil;TEST.zoom=1
mouseX,mouseY=screenPoint(source,commonX,commonY)
picked=P.Client.findPortals(0,{},mouseX,mouseY)
check(#picked==1 and picked[1]==front,'overlapping 2D alpha hits expose only the foremost gate')

-- Opaque old Java-test payloads remain untouched and cannot be falsely recovered.
player,source,target,origin,exit=fixture()
local oldJava=TEST.object(TEST.square(2,0,0,false))
local opaque={schema=2,revision=7,slots={[2]={itemId=9999,payload='keep-old-java-original-bytes'}}}
oldJava.data.SuQingPortals={schema=2,id='old-java-ui',facing=0,batteryStorage=opaque}
W.register(oldJava)
window=P.UI.open(player,oldJava)
check(window.blockReason=='legacy_java_storage','Lua UI states the exact protected old-Java recovery reason')
check(window.legacyButton.enabled==false and window.teleportButton.enabled==false,'Lua UI does not offer a fake decode or replacement-battery action')
window:renderContent(window.content);window:render()
check(oldJava.data.SuQingPortals.batteryStorage==opaque and opaque.slots[2].payload=='keep-old-java-original-bytes','rendering the recovery notice preserves opaque old original state')
window:close()

-- Display and disable logic use the server snapshot's configured trip cost.
player,source,target,origin,exit=fixture()
SandboxVars.SuQingPortals.TransferCost=0.5
window=P.UI.open(player,source)
check(window.snapshot.cost==0.5 and P.UI.tripCount(window.snapshot)==8,'0.5 cost gives eight trips from four full batteries')
check(window.teleportButton.enabled==true and window.teleportButton.title:find('0.50',1,true),'teleport button shows the actual 0.5 departure cost')
check(window.teleportButton.tooltip:find('0.50',1,true),'ready tooltip follows snapshot cost 0.5')
TEST.textCalls={};window:refresh(false);window:renderContent(window.content)
local summary,receiver
for _,call in ipairs(TEST.textCalls) do
    if call.key=='IGUI_SQP_EnergySummary' then summary=call.args end
    if call.key=='IGUI_SQP_ReceiverNote' then receiver=call.args end
end
check(summary and summary[1]=='4.00' and summary[2]=='0.50' and summary[3]=='8','summary passes separate total, actual trip cost and available-trip arguments')
check(receiver and receiver[1]=='0.50','arrival note receives the actual departure-only cost')
check(not window.teleportButton.title:find('2.00',1,true),'0.5-cost button does not retain old fixed-two display')
for slot=2,4 do check(W.Remove(player,source,slot),'prepare low charge for 0.5 cost') end
P.BatterySlots.read(source)[1]:setUsedDelta(0.49)
window:refresh(false)
check(window.blockReason=='insufficient_charge' and P.UI.tripCount(window.snapshot)==0,'0.49 charge is insufficient for the configured 0.5 cost')
check(window.teleportButton.tooltip:find('0.50',1,true),'insufficient-charge tooltip states configured 0.5 rather than a fixed two')
window:close()
player,source,target,origin,exit=fixture()
SandboxVars.SuQingPortals.TransferCost=4
window=P.UI.open(player,source)
check(window.snapshot.cost==4 and P.UI.tripCount(window.snapshot)==1,'cost four requires the entire full four-battery bank for one trip')
check(window.teleportButton.enabled==true and window.teleportButton.title:find('4.00',1,true),'full bank enables and displays cost four')
check(W.Remove(player,source,4),'prepare three full batteries at cost four')
window:refresh(false)
check(window.blockReason=='insufficient_charge' and P.UI.tripCount(window.snapshot)==0,'three full batteries cannot fund a cost-four trip')
check(window.teleportButton.tooltip:find('4.00',1,true),'disabled reason displays the actual cost-four requirement')
local retainedSnapshot=window.snapshot
SandboxVars.SuQingPortals.TransferCost=0.5
check(P.UI.transferCost(retainedSnapshot)==4 and P.UI.tripCount(retainedSnapshot)==0,'snapshot cost takes precedence over a changed sandbox getter')
check(P.UI.transferCost(nil)==0.5,'a missing snapshot uses the current Core.getTransferCost fallback')
window:refresh(false)
check(window.snapshot.cost==0.5 and P.UI.tripCount(window.snapshot)==6,'next state refresh updates cost and trip count together')
check(window.teleportButton.enabled==true and window.teleportButton.title:find('0.50',1,true),'live window refresh removes stale cost-four disabled state')
window:close()
SandboxVars.SuQingPortals.TransferCost=2

-- The removed debug giver stays absent even with legacy saved sandbox state.
TEST.reset()
origin=TEST.square(0,0,0,false);player=TEST.player(origin)
source=TEST.object(TEST.square(1,0,0,false));W.register(source)
player.skills={Electricity=1,MetalWelding=0}
player.getXp=function() error('removed test giver must never alter experience') end
player.LevelPerk=function() error('removed test giver must never alter perks') end
player.data.SuQingPortalsTestKitGiven=true
player.data.SuQingPortalsTestKitVersion='legacy-claimed-kit'
SandboxVars.SuQingPortals.DebugTools=true -- Old world option may still be saved.
check(P.Build.giveTestKit==nil and P.Build.TEST_KIT_VERSION==nil,'production module exposes no item-giver function or kit definition')
local function contextFixture()
    local context={options={},requestX=0,requestY=0}
    function context:addOption(label,target,callback,...)
        local option={label=label,target=target,callback=callback,args={...}}
        self.options[#self.options+1]=option;return option
    end
    function context:getNew() return contextFixture() end
    function context:addSubMenu(option,menu) option.submenu=menu end
    return context
end
TEST.picked=source
local context=contextFixture()
P.Client.fillContext(0,context,{source},false)
check(#context.options==3 and context.options[1].label:find('IGUI_SQP_OpenNamed',1,true) and
    context.options[2].label=='IGUI_SQP_InstallDirect' and context.options[3].label=='IGUI_SQP_RemoveDirect',
    'legacy-enabled DebugTools cannot add any item-giver menu to a gate')
TEST.picked=nil
context=contextFixture()
context.requestX,context.requestY=-10000,-10000
P.Client.fillContext(0,context,{},false)
check(#context.options==0,'ground right-click has no mod item-giver menu')
Events.OnCreatePlayer.run(0,player);Events.OnGameStart.run()
check(player:getInventory():getItems():size()==0,'legacy debug option and spawn/load events cannot grant items')
check(player.skills.Electricity==1 and player.skills.MetalWelding==0,'removed giver leaves character skills unchanged')
check(player.data.SuQingPortalsTestKitGiven==true and player.data.SuQingPortalsTestKitVersion=='legacy-claimed-kit','old claim markers remain harmless saved data rather than migration triggers')
SandboxVars.SuQingPortals.DebugTools=nil
print('PORTAL_CLIENT_TRANSFER_ACTION_UI_PICKER checks='..TEST.checks..' failures=0')
