# 0.1.4 更新说明 / Release notes

本次更新沿用原工坊条目3834693880和现有可见性。 / This update reuses the existing Workshop item and preserves its visibility.

## 中文

- 新增实际成功充入量的能源结算：普通发电机独立扣油，燃油不足限制本次充入量。
- 新增可选Immersive Solar Arrays 1.2.15储能结算与太阳能来源显示；拒绝未知版本、ISA-Fix及不能核实的桥接，不把代理发电机当燃油机。
- 发电机面板显示额外负载及合计，不改原生总负载或ISA updateDrain，避免重复计费。BGI等仅按原生负载估算的剩余时间可能偏长。
- 保留四槽原电池、原生新配方、可调传送耗电、整门充电速率、可缩放界面及schema3。空槽、满电、损坏、锁定、卸载及断电不收取门的附加充电消费。
- 用户已反馈本轮单人游戏内测试全部正常；完整离线回归通过。0.1.4仅提升正式版号和说明，不再更改已验收玩法。
- 使用已选C「雨夜归途」封面，现有icon沿用。B42.21单人，不支持车辆、拖挂或联机；极端断电/存档损坏及未核对的第三方组合仍有限制。

## English

- Added settlement for energy actually and successfully stored. Fuel generators pay independently; fuel availability limits each step.
- Added optional Immersive Solar Arrays 1.2.15 real-storage settlement/solar identification. Unknown versions, ISA-Fix and unverifiable bridges are rejected; the proxy is not billed as fuel.
- Panels show portal demand and combined total without changing native load or ISA updateDrain. BGI/native-load-only time estimates may run long.
- Retains original four-slot batteries, recipe, configurable trip cost/total charging rate, resizable UI and schema3. Empty/full/damaged banks, locks, unloading and power loss create no extra portal debit.
- The user reported all current single-player tests working normally; the complete offline suite passed. Promotion to 0.1.4 changes version metadata/documentation without altering accepted gameplay.
- Retains selected C “Rainy Homecoming” cover and existing icon. B42.21 single-player; no vehicles, trailers or multiplayer. Extreme interruption/corruption and unreviewed combinations retain limits.

Preparation only. Existing public item 3834693880/visibility 0 is reused. New receipts establish upload, Git and personal enablement completion.
