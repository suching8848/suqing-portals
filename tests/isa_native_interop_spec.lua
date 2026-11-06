-- Executes against the installed upstream PowerBankObject_Server class.
local T, A = ISA_NATIVE, SuQingPortals.ISAPower
local a, b = T.battery(0.2, 50, 50), T.battery(0.8, 100, 100)
local pb, gen, container = T.makeBank({a, b})
local initial, capacity = pb.charge, pb.maxcapacity
local nativeUpdate, nativeDrain = T.class.updateBatteries, T.class.updateDrain
local receipt, approved = A.begin(pb, 0.5, 0.1, 1)
T.check(receipt ~= nil, "installed upstream bank accepts settlement")
T.near(approved, 0.5)
T.near(receipt.capacity, capacity, "adapter capacity equals real upstream calculateBatteryStats")
T.near(pb.charge, initial - 40, "real upstream battery setter debits expected energy")
T.check(container.dirty and gen.sends >= 2, "real updateBatteries/saveData dirty and transmit original object")
T.near(gen.data.charge, pb.charge, "real saveData writes bank charge into original generator ModData")
pb:calculateBatteryStats(container)
T.near(pb.charge, initial - 40, "real upstream recount confirms physical battery energy debit")
T.check(A.rollback(receipt), "real upstream debit can roll back")
T.check(a.charge == 0.2 and b.charge == 0.8, "native original unequal battery charges restored exactly")
T.near(gen.data.charge, initial, "real upstream saveData persisted the refund")
T.check(gen.data.SuQingPortalsISAEnergyCarry == nil, "rollback removes originally absent carry metadata")
T.check(T.class.updateBatteries == nativeUpdate and T.class.updateDrain == nativeDrain,
    "adapter does not wrap upstream drain or battery setters")

SandboxVars.ISA.DrainCalc = 1
local modeOne = A.begin(pb, 0.25, 0.1, 9)
T.check(modeOne ~= nil, "old ISA scan mode supports independent charge settlement")
T.near(pb.charge, initial - 23, "mode one honors 920 conversion and ignores native fuel multiplier")
T.check(A.finish(modeOne, 0.25), "successful ISA charge receipt closes")
SandboxVars.ISA.DrainCalc = 2
local beforeFailure = pb.charge
a.failNext = true
local failure, _, code = A.begin(pb, 0.1, 0.1, 1)
T.check(not failure and code == "isa_write_failed", "real upstream partial setter exception safely rejected")
T.near(pb.charge, beforeFailure, "real upstream failure restores energy and original item values")
pb.conGenerator = {ison = true}
T.check(A.begin(pb, 0.1, 0.1, 1) == nil, "real upstream shouldDrain excludes running backup generator")
print("PORTAL_ISA_NATIVE_INTEROP checks=" .. T.checks .. " failures=0")
