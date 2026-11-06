local P,T = SuQingPortals,TEST
local W,E,C = P.World,P.Power,P.Core
local function check(value,label) T.assert(value,label) end
local function near(a,b,label) T.near(a,b,label) end
SandboxVars={GeneratorFuelConsumption=0.1,SuQingPortals={ChargePerHour=0.5}}
local square=T.square(10,10,0,true)
local gen=T.generators[1]
local object=T.object(square)
W.register(object)
local player=T.player(square,0)
local battery=T.battery(0);player.inventory:AddItem(battery)
check(W.Install(player,object,battery,1),'install actual empty original')
E.refreshSources()
check(E.info(object).source=='generator','known fuel source selected')
W.chargeTick();T.hours=T.hours+1;W.chargeTick()
near(battery:getCurrentUsesFloat(),0.5,'one game hour stores configured half battery')
near(gen:getFuel(),9.985,'actual charge costs native charger equivalent scaled once')
local gas=gen:getFuel()
W.chargeTick();near(gen:getFuel(),gas,'repeated tick at same world hour cannot charge or bill twice')
T.hours=T.hours+1;W.chargeTick();near(battery:getCurrentUsesFloat(),1,'fills healthy battery')
gas=gen:getFuel();T.hours=T.hours+10;W.chargeTick()
near(gen:getFuel(),gas,'full bank never consumes extra fuel')
battery:setUsedDelta(0);battery.condition=0;T.hours=T.hours+1;W.chargeTick()
near(gen:getFuel(),gas,'broken bank never consumes extra fuel')
battery.condition=80
object.data.SuQingPortals.pendingToken='lock';T.hours=T.hours+1;W.chargeTick()
near(gen:getFuel(),gas,'transaction-locked bank never consumes extra fuel')
object.data.SuQingPortals.pendingToken=nil
-- Grid wins over a covering generator; solar/gas are not billed for indoor mains.
square.grid,square.room=true,{}
W.chargeTick();T.hours=T.hours+1;W.chargeTick()
near(battery:getCurrentUsesFloat(),0.5,'indoor mains can charge')
near(gen:getFuel(),gas,'mains overlap does not consume fuel')
square.grid,square.room=false,nil
W.chargeTick();local before=battery:getCurrentUsesFloat();gas=gen:getFuel()
battery.failNext=true;T.hours=T.hours+0.5;W.chargeTick()
near(battery:getCurrentUsesFloat(),before,'failed portal setter restores original charge')
near(gen:getFuel(),gas,'failed portal setter refunds energy exactly')
local realPersist=P.BatterySlots.persist
P.BatterySlots.persist=function() return false,'storage_conflict' end
T.hours=T.hours+0.5;W.chargeTick()
P.BatterySlots.persist=realPersist
near(battery:getCurrentUsesFloat(),before,'failed portal persistence restores charge')
near(gen:getFuel(),gas,'failed portal persistence refunds fuel')
-- Emptying the source clips charge to available fuel and switches it off.
gen.fuel=0.003;E.fuelCarry[gen]=nil
T.hours=T.hours+1;W.chargeTick()
near(battery:getCurrentUsesFloat(),before+0.1,'low fuel clips charge instead of going negative')
near(gen:getFuel(),0,'low source spends only available fuel')
check(not gen:isActivated(),'fully exhausted source switches off')
gas=gen:getFuel();T.hours=T.hours+5;W.chargeTick()
near(gen:getFuel(),gas,'exhausted source cannot fund later charging')
-- Overlapping generators have one deterministic owner; the second is untouched.
gen.fuel,gen.activated=5,true
local other=T.generator(T.square(12,10,0,false),7)
E.refreshSources()
local receipt,approved=E.begin(object,0.2)
check(receipt and approved==0.2,'positive charge can reserve energy')
near(gen:getFuel(),4.994,'closest source billed')
near(other:getFuel(),7,'overlapping source not double billed')
check(E.finish(receipt,0.1),'partial actual delivery refunds unused energy')
near(gen:getFuel(),4.997,'only actual delivery charged')
check(E.finish(receipt,0.1),'settlement repeat idempotent')
near(gen:getFuel(),4.997,'settlement repeat does not double charge')
check(not E.rollback(receipt),'finished receipt cannot manufacture refund')
receipt=E.begin(object,0.2)
check(E.rollback(receipt) and E.rollback(receipt),'rollback is idempotent')
near(gen:getFuel(),4.997,'repeat rollback restores original balance once')
gen.failWrite=true
local failed,_,code=E.begin(object,0.2)
check(not failed and code=='power_write_failed','native setter exception fails safely')
near(gen:getFuel(),4.997,'native setter exception recovers fuel')
-- Small float writes carry rounding across payments rather than losing tiny debits.
gen.fuel=10;E.fuelCarry[gen]=nil
for i=1,1000 do
    local r=E.begin(object,0.00015)
    check(r and E.finish(r,0.00015),'micro-charge receipt settles')
end
check(math.abs(gen:getFuel()-(10-1000*0.00015*0.03))<0.000003,'fuel carry bounds accumulated float drift')
-- No source, newly loaded source and source changes never back-charge old hours.
T.squares['10:10:0']=nil;local stored=battery:getCurrentUsesFloat()
T.hours=T.hours+10;W.chargeTick();T.squares['10:10:0']=square
T.hours=T.hours+10;W.chargeTick();near(battery:getCurrentUsesFloat(),stored,'unloaded time never charges')
gen.activated,other.activated=false,false
E.refreshSources()
check(E.info(object).error=='power_unsupported' and not W.localPower(object),'unidentified regional power cannot give free energy')
local rate=SandboxVars.GeneratorFuelConsumption
SandboxVars.GeneratorFuelConsumption=0
gen.activated=true;E.refreshSources();receipt=E.begin(object,0.25)
gas=gen:getFuel();check(receipt and E.finish(receipt,0.25),'zero consumption sandbox intentionally allows no-cost generator energy')
near(gen:getFuel(),gas,'zero multiplier not replaced by default')
SandboxVars.GeneratorFuelConsumption=rate
-- Minimum configured rate must accumulate tiny tick intervals instead of losing them.
battery:setUsedDelta(0);object.data.SuQingPortals.chargeError=nil
SandboxVars.SuQingPortals.ChargePerHour=0.05
W.chargeTick();local initial=T.hours
for i=1,1000 do T.hours=initial+i/100000;W.chargeTick() end
check(battery:getCurrentUsesFloat()>0.0003,'low charging rate accumulates sub-epsilon tick intervals')
object.data.SuQingPortals.chargeError='power_rollback_failed'
gen.activated=false;W.chargeTick()
check(object.data.SuQingPortals.chargeError=='power_rollback_failed','unsupported source cannot erase a fatal rollback fault')
gen.activated=true;T.hours=T.hours+1;local stopped=battery:getCurrentUsesFloat();W.chargeTick()
near(battery:getCurrentUsesFloat(),stopped,'restored source cannot bypass fatal rollback pause')
check(W.State(object).reason=='power_rollback_failed' and not W.State(object).canTeleport,'uncertain rollback balance blocks transfer')
print('PORTAL_POWER_SETTLEMENT checks='..T.checks..' failures=0')
