# 0.1.6-rc.11

适配 Live Wire 2.1.5 并修复与 ISA 并网时的充电结算。按电池步进向下取整后充电，并按实际充入量扣电。改进传送落点核对、回程保护与重进结算。

Supports Live Wire 2.1.5 and fixes charging settlement when combined with ISA. Charging rounds down to a native battery increment and debits the charge actually stored. Improves destination checks, return protection and recovery on reload.

B42.22.2 正式单人档自动存档已确认混合电网充电恢复。Lua 本体可独立加载。使用 PZO 的 B42.22.2 环境如拒绝原版保护标记，应装配匹配的可选传送保护模块。Viewpoint 0.1.7 的模型使用独立资源包。跨区传送待单独验收。

B42.22.2 single-player autosaves confirm that charging resumed on the mixed grid. The Lua mod loads independently. A matching optional travel guard covers PZO B42.22.2 setups that reject the original protection flags. Viewpoint 0.1.7 models use a separate resource pack. Cross-chunk travel awaits separate gameplay acceptance.
