# SuQing's Portals / 蘇清的传送门

Workshop item: [uploaded and verified private item](https://steamcommunity.com/sharedfiles/filedetails/?id=3834693880). Source repository: [suching8848/suqing-portals](https://github.com/suching8848/suqing-portals). Private upload and native content readback completed on2026-11-06. The item is not public; gameplay acceptance is unchanged.

Version `0.1.3-lua-test.2`, Mod ID `SuQingPortals`. Target: the verified B42.21 branch, single-player testing. The portal uses pure Lua with no custom Java component; Viewpoint remains optional. This candidate has not passed user gameplay acceptance.

Version 0.1.3 adopts the approved recipe: eight small metal sheets, four pipes, eight wires, sixteen electronics scraps, one premium camera and one handheld walkie-talkie per gate. Requires Electrical 4 and Welding 3, retaining a screwdriver, blowtorch and welding mask. Existing gates, pairings and separately installed car batteries remain intact.

The current candidate corrects CN/EN placeholders and percentages, with two sandbox settings: trip cost (default 2, range 0.5–4) and total charging rate (default 0.5, range 0.05–4). Management is resizable with a compact four-slot layout and prominent power connection, identifiable sources and charging status. Normal screens aim to show all information at once; small windows or large fonts may scroll. The item-giver feature and its sandbox switch have been removed. User acceptance remains pending.

Test.2 fixes right-click errors by using the native `PickThumpable()` method to obtain the gate directly, without treating a Java `ClickObject` as a Lua table. Battery schema and gameplay are unchanged; continue the existing isolated save.

Build two fixed portals, open management by right-clicking the visible gate, name them and select the other gate to create a bidirectional pair. Each gate has four dedicated car-battery slots (`Base.CarBattery1/2/3`). Context actions and management buttons install/remove the original batteries through the native action queue with an adjacent reachable position.

Original batteries remain in native internal storage on the gate. The game's existing persistence preserves the complete item, ID, condition, charge, name and custom data. Lua hides that storage from the regular container rail, excludes it from nearby crafting materials and blocks ordinary drag/drop and transfer actions. Players use only the dedicated four-slot interface. There is no portal JAR, Java reflection or extra portal Java approval step. Third-party mods that directly scan world items are outside these native interface guards.

A trip spends the sandbox-selected energy **entirely at departure**, default two full-car-battery equivalents and adjustable from 0.5 to 4. Four full batteries fund eight trips at 0.5, two at 2, or one at 4; management uses the current actual cost. The batteries remain reusable. The receiver needs no battery or power; a return journey requires energy at that gate.

Installed batteries charge only while their gate is loaded and locally powered. Grid power requires an indoor room; generator coverage follows the current native rules. Default total gate rate: `0.5` full-battery equivalents per game hour, adjustable from `0.05` to `4`. Filling four empty batteries takes eight game hours; replacing a trip's energy takes four at the default trip cost of 2. Unloaded/offline/unverified-power intervals earn no charge. **This test candidate does not add a separate charging load to native generator fuel consumption or its appliance list.**

Sixteen appearance states match the actual four-slot occupancy mask, with 64 directional sprites/bindings. Installing only slots 2 and 4 displays those exact bays. Standard `128×256` sprites remove the old 128-pixel vertical mismatch while retaining model scale and world coordinates. Management shows each battery's name, condition and charge, available trips, power and identifiable sources, charging status and rate, pairing and disabled-action reasons. A resizable compact 2×2 slot layout aims to fit normal screens; small windows or large fonts can scroll, and transfer stays in the footer.

Each gate needs eight small metal sheets, four metal pipes, eight electric wires, sixteen electronics scraps, one premium camera and one native handheld walkie-talkie, with Electrical 4 and Welding 3. An unbroken screwdriver, blowtorch and welding mask are retained tools; this version does not additionally consume torch fuel or welding rods. Car batteries are installed after construction. Native building logic handles materials and cancellation.

## Isolated test entry

Run `D:\steam\steamapps\common\ProjectZomboid\CodexAssets\SuQingPortals_20261106\IsolatedTest\Start-Portal-Test.cmd` yourself. Preparation never launches or controls the game.

Its separate cache is the adjacent `data` directory. Only `ZombieBuddy`, `Viewpoint`, `SuQingPortals`, `B42ModTrans_CN` and `B42Trans_CN` are enabled. As approved by the user, the entry retains the matching installed PZO Java/Lua runtime and game resources, with PZO user settings copied into the private test cache. Saves, logs, local mod copies and Java-agent configuration remain separate. It does not enable the full Workshop set, reuse personal saves or write the normal AOT output files. The current B42 first-release reset marker is prepared so the initial launch retains this enabled list. The Java framework may show its own approval prompt on first launch.

Create a custom sandbox using `SuQingPortals_Test` for no zombies, long-lasting utilities and normal charging, or continue the existing isolated save. No ground-context item claim or other mod item-giver remains. Obtain materials and skills through normal gameplay; the user may prepare supplies or skills with native debug tools only when testing. Previously granted inventory and historical player fields remain intact.

Build the first gate, install four batteries, then build a second gate elsewhere with no batteries. Pair them in management. Travel to the empty receiver and verify that only the source lost `2.00` charge. Install the other four batteries at the receiver for return testing. Continue with charging, distant unloaded destinations, occupied exits, save/reload, destruction and Viewpoint first/third-person checks.

Logs: isolated `data/console.txt` and `data/Logs`. Your normal Steam entry retains the personal environment. No normal saves were copied into this profile.

## Recovery and limits

Supports the character and carried items in one world. Vehicles, trailers and multiplayer are outside this candidate. Fixed-gate furniture pickup is unsupported; demolition unpairs the gate and releases original batteries. Version 0.1.0 gates adopt their existing native storage in place, preserving coordinates, ID, pairing and original items. Foreign items, excessive quantities, damaged data or unresolved transfers block migration without clearing old storage; use the management recovery controls. The complete isolated-world snapshot was reverified and the previous runtime and entry were separately archived; see this upgrade's recovery receipt. Neither contains a personal world.

Before the test.1 upgrade, read-only inspection found the original isolated save in the 0.1.0 format. The user has since loaded the Lua version; current progress is preserved. A different save with batteries installed under the 0.1.1 Java version needs the corresponding old version to return those originals before upgrading. Pure Lua does not decode, erase or recreate those opaque item records. Empty 0.1.1 gates can migrate.

The transfer service temporarily preserves/restores original movement, noclip and ghost flags. It validates the actual destination gate and exit floor, obstacles, vehicles, fire and occupants before completion. Failure returns to the source and refunds the original battery instances. If the source is not loaded or original items were moved externally, a recovery receipt remains; no replacement battery or unverified refund is created. Use the recovery context action or save/reload for a retry.

Global world data, character files and chunks are not a cross-file atomic transaction. Extreme interruption/corruption consistency, long-distance loading, recovery behavior and Viewpoint placement remain subject to user gameplay testing. Offline parser/interpreter checks are not gameplay acceptance.

The independent source folder contains runtime files, bilingual documentation, original art/prompts, reproducible geometry/resource generators, offline checks and frozen test packaging. Nothing has been published to Workshop or pushed to a Git remote.
