# 更新说明草稿 / Draft release notes

候选：`0.1.3-lua-test.2`。准备日期：2026-11-06。本文件用于发布准备，未进行工坊上传。

## 中文

本候选在新建造配方、可调耗电和文字修正的基础上，补充供电显示、可缩放界面并移除物资赠送：

- 每门消耗小金属板8、金属管4、电线8、电子零件16、高端相机1、手持对讲机1；接受原版手持对讲机型号，含自制款。
- 建造要求电工4级、焊接3级。螺丝刀、焊枪、焊接面罩保留；不额外消耗焊枪燃料或焊条，汽车电池在建成后另装。
- 单次传送耗电可在沙盒中设为0.5～4，默认2，全部从出发端扣除；界面按当前设置显示耗电、可传送次数和不足原因。
- 修正中英菜单、槽号、电量和耐久等参数文本与百分号显示。
- 管理界面突出显示供电连接状态与充电状态；可靠识别时标明市电或发电机，来源不明时明确标注区域供电。满电、无电池、损坏或缺电均单独说明。
- 管理窗口可拖动右下角或底边缩放，四槽采用紧凑的2×2布局；小屏幕保留滚动，传送与操作提示始终位于独立底部。
- 完全移除模组测试物资领取菜单、发放代码及沙盒测试工具开关；旧存档中残留的开关不会发放物品。
- 现有门、配对及已安装电池沿用当前数据，不因新配方重新扣料。

四个真实汽车电池槽、接收端无需供电、已加载且当地有电才充电、可选Viewpoint显示等玩法保持。当前充电仍未作为独立负载计入原版发电机燃油消耗。仅支持B42.21单人，不支持车辆、拖挂或多人游戏。

验收状态：用户反馈此前隔离测试版的基础使用基本正常。当前候选的新配方、耗电设置、文字修正以及本轮供电显示、缩放布局和移除赠送已通过离线回归，仍待用户游戏内验收。长距离加载、异常恢复、Viewpoint细节及不同模组组合不作全面通过声明。

## English

This candidate adds visible power status, resizable management and complete item-giver removal to the new recipe, configurable cost and text fixes:

- Each gate consumes 8 small steel sheets, 4 iron pipes, 8 electrical wires, 16 scrap electronics, 1 high-end camera and 1 handheld walkie-talkie. Vanilla handheld models, including the makeshift one, are accepted.
- Requires Electrical 4 and Welding 3. The screwdriver, welding torch and welder mask are retained. No additional torch fuel or welding rods are consumed; car batteries are installed after construction.
- Sandbox trip cost is adjustable from 0.5 to 4, default 2, paid entirely at departure. Management shows the current cost, available trips and insufficient-charge reason.
- Corrected parameter and percentage text in CN/EN menus, slot labels, battery charge and condition displays.
- Management prominently separates power connection from charging status. Grid or generator sources are named when reliably identified; otherwise area power remains explicitly unconfirmed. Full, empty, broken and unpowered banks have distinct states.
- Resize management from its native corner or bottom edge. Four compact slots use a 2×2 layout, smaller screens retain scrolling, and transfer/action messages stay in a separate footer.
- Removed the mod test-supply menu, item-grant code and sandbox test-tools option. A legacy saved option cannot grant items.
- Existing gates, pairings and installed batteries keep their current data. The new recipe does not charge existing gates again.

Four original car-battery slots, powerless arrivals, charging only while loaded and locally powered, and optional Viewpoint visuals remain. Charging still has no separate load in native generator fuel use. B42.21 single-player only; vehicles, trailers and multiplayer are not supported.

Validation status: the user reported that basic use in an earlier isolated test build was generally working. The current candidate passed offline regression checks for the recipe, cost setting, text fixes, power display, resizing and giver removal. User gameplay verification remains pending. No complete-acceptance claim is made for long-distance loading, interrupted-trip recovery, Viewpoint details or different mod combinations.
