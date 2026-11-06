# 蘇清的传送门 / SuQing's Portals

发布材料草稿，2026-11-06。当前候选 `0.1.3-lua-test.2`；仅准备材料，未上传或发布。

## 中文短介绍

建造并配对传送门，用四槽可反复充电的汽车电池连接据点。单次耗电可调0.5～4，默认2，全部由出发端提供；接收端无需电池或供电。附可缩放的2×2四槽管理界面，突出显示供电及充电状态；提供四朝向外观和可选Viewpoint适配。适用于B42.21单人；本体采用纯Lua，暂不支持车辆或联机。当前为测试候选，最新改动仍待游戏内复核。

## English short description

Build paired portals with four rechargeable car-battery slots. Set trip cost from 0.5 to 4, default 2, paid entirely at departure; arrival needs neither batteries nor power. Includes resizable 2×2 management with prominent power/charging states, four directions and optional Viewpoint visuals. Pure Lua for B42.21 single-player. Vehicles and multiplayer are not supported. This test candidate's latest changes still await gameplay verification.

## 发布信息核对 / Listing facts

| 项目 / Field | 当前内容 / Current value |
| --- | --- |
| 标题 / Title | 蘇清的传送门 / SuQing's Portals |
| Mod ID | `SuQingPortals` |
| 版本 / Version | `0.1.3-lua-test.2` |
| 范围 / Scope | B42.21，单人 / single-player |
| 本体前置 / Base dependencies | 无额外玩法前置；本体纯Lua / No additional gameplay dependency; pure Lua |
| 可选适配 / Optional | Viewpoint，遵循其自身要求 / Viewpoint, subject to its own requirements |
| 电量 / Energy | 四槽，单次0.5～4，默认2，全部出发端承担 / Four slots; trip cost 0.5–4, default 2, departure only |
| 充电 / Charging | 整门0.05～4等量／游戏小时，默认0.5；仅已加载且当地有电 / Total gate rate 0.05–4 per game hour, default 0.5; loaded and locally powered only |
| 已知限制 / Known limitation | 充电尚无独立发电机负载及额外油耗 / No separate generator charging load or added fuel use yet |
| 验收 / Acceptance | 用户反馈此前隔离版基础使用基本正常；当前候选配方、成本、文字、供电/缩放/移除赠送已离线通过，待游戏内验收 / Earlier isolated basic use reported generally working; current recipe/cost/text/power/resize/giver-removal checked offline; gameplay acceptance pending |

发布时使用同目录中英BBCode正文。封面已选C雨夜归途；独立icon、最终游戏验收和是否发布仍待确认，本材料不表示已发布。
