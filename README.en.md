# SuQing's Portals / 蘇清的传送门

Source version **0.1.5** targets **B42.21 single-player**. The mod ID is `SuQingPortals`. It uses pure Lua, with optional Viewpoint visuals.

The user accepted **0.1.5** in the B42.21 single-player isolated setup on November 8, 2026. See the [power compatibility notes](docs/供电兼容说明.md) for the tested scope and energy rules.

Workshop **0.1.5** is public and verified on the existing item `3834693880`. [Steam Workshop](https://steamcommunity.com/sharedfiles/filedetails/?id=3834693880) · [0.1.5 publication record](publishing/Release_0.1.5/publication-result.json) · [GitHub source](https://github.com/suching8848/suqing-portals)

## Building and travel

Build two fixed gates, right-click either to open management, name them and choose the other gate to form a two-way pair. Each gate has four independent vanilla car-battery slots accepting `Base.CarBattery1/2/3`. Install, retrieve and recharge the same original batteries.

Each gate consumes 8 small metal sheets, 4 metal pipes, 8 electrical wires, 16 scrap electronics, 1 high-end camera and 1 handheld walkie-talkie. Requires Electrical 4 and Welding 3. All six vanilla handheld walkie-talkies, including the makeshift model, are accepted; ordinary radios and large HAM stations are not substitutes. An unbroken screwdriver, welding torch and welding mask are retained tools. No additional torch fuel or welding rods are consumed in this version. Install car batteries after building. Native construction handles requirements, consumption and cancellation; existing gates are not charged the new recipe again.

A trip spends energy **entirely from departure batteries**, adjustable in sandbox from 0.5 to 4 full-car-battery equivalents, default 2. Four full batteries fund 8/2/1 departures at costs of 0.5/2/4. **Arrival needs neither batteries nor local electricity**; returning requires enough energy at that gate. Travel does not consume the battery items themselves.

Resizable management uses four compact slots in a 2×2 layout. It shows battery names, condition, charge, pairing, available trips, power sources and charging status. Normal screens aim to fit all information; small windows or large fonts retain necessary scrolling, with transfer fixed in the footer. The supply-giver menu, grant code and sandbox test-tools option have been removed. Obtain materials and skills through normal play.

Four directions and sixteen occupancy masks produce 64 standard 128×256 sprites with matching Viewpoint models. Only the installed battery bays are shown. The selected C artwork, “Rainy Homecoming”, and the existing icon are retained.

## Charging and energy settlement

Two sandbox settings are provided: trip energy 0.5–4, default 2; total gate charging rate 0.05–4 full-battery equivalents per game hour, default 0.5. This is the **whole gate's total rate**, not a full rate per slot. At the default rate and with sufficient supply, four empty batteries take eight game hours to fill; replacing the default trip's two equivalents takes four hours.

Charging requires a loaded gate, a verified local provider and a healthy battery with room for charge. Indoor grid supply takes priority; otherwise one covering source pays. Empty slots, full/damaged batteries, transfer locks, unloading or lost power create no portal charging debit. Offline or unloaded time earns no catch-up charge.

- **Fuel generators:** independently debit fuel for energy actually and successfully stored, at `0.3 L × GeneratorFuelConsumption` per full-battery equivalent. A 0.5 charging rate and native default multiplier 0.1 add **0.015 L per game hour**, excluding ordinary generator and other-appliance consumption. Available fuel limits the charging step.
- **Optional Immersive Solar Arrays 1.2.15:** Workshop `3781944805`, Mod ID `ISA`. Charging debits one selected bank's real original-battery storage. Its solar supply proxy is not treated as a fuel generator. Ordinary generator support does not require ISA. Only reviewed version 1.2.15 is supported. Unknown versions, unverifiable interfaces and `ISA-Fix` combinations are rejected by the bridge; a local electricity flag cannot create free charge. The separate `Immersive Solar Arrays [BETA]-Fix / 3592668881` package is outside support.
- **Optional Live Wire 1.7.2.** With `batman_LiveWire` from Workshop item `3821807453` enabled, a gate can draw stored energy from loaded battery cabinets on a network whose inverter is supplying power. Indoor mains, independent generators and supported ISA sources take priority. The gate's appliance circuit must be enabled. Networks with a linked Live Wire backup generator or without usable cabinet storage are ineligible. See the power compatibility notes below for rates and limits.
- **Panels and estimates:** the generator-panel wrapper shows additional portal demand and a combined total. The portal is not registered as a Java-native appliance. Native total load and ISA `updateDrain` remain intact to avoid double billing. BGI and other estimates based solely on native total load may overestimate remaining time because they do not include this independent debit. Actual fuel/storage changes take precedence.

See [power compatibility notes](docs/供电兼容说明.md) for exact settlement rules.

## Persistence, removal and limits

Supports characters and carried items within one world. **Vehicles, trailers and multiplayer are not supported.** Original batteries remain in native gate storage, preserving identity, condition, charge, name and custom data. Dedicated four-slot controls isolate the regular container rail, drag/drop and nearby crafting routes; third-party code that directly scans world items lies outside those native UI guards.

Demolition unpairs a gate and releases its original batteries. Ordinary furniture pickup is unsupported. Retrieve batteries and unpair before disabling the mod. Schema3 is unchanged. Version 0.1.0 gates may adopt their native storage in place; invalid data or an unresolved trip blocks migration while preserving storage. Any separate world containing batteries installed by the 0.1.1 Java build must first return them under the corresponding old build. The pure-Lua release does not decode, erase or recreate opaque Java item records.

Travel validates the destination identity and exit before completion. Failure returns the character and refunds through the original-battery receipt. An unloaded source or externally moved originals retain a recovery record; retry the recovery context action. No replacement battery is fabricated. World data, character files and chunks are not one cross-file atomic transaction, so extreme power loss or corrupt saves retain consistency limits. Keep logs instead of clearing world data after an abnormal result.

## Development and repeat checks

- See the [user test steps](docs/用户测试步骤.md) for isolated outage and single-player regression procedures.
- `tools/validate_release.py` runs standalone Kahlua, native API/resource checks, energy settlement and ISA interoperability without starting a game world.
- `mods/SuQingPortals` contains runtime files. `art/` retains reference provenance, prompts, masters and reproducible model resources.
- `publishing/Release_0.1.5` contains this version’s acceptance and publication materials. The previous records are in `publishing/Release_0.1.4`.

The user performs all gameplay operation. Existing isolated entries and outage templates remain available for repeat checks; actual paths/lists belong to their deployment/template receipts. Historical notes do not establish personal enablement. Complete this round's full save and relevant configuration backup before personal deployment; recovery follows that verified backup receipt.

中文：[README.md](README.md).
