# 传送门行程保护与三维资源 / Portal Travel Guard and model resources

两个子模组随原传送门工坊条目提供。0.1.6-rc.12 的 Lua 本体必须加载行程保护。三维资源可独立启用。

- **行程保护 0.1.0-rc.1。** Mod ID 为 SuQingPortalsTravelGuard，本体依赖本附属，本附属依赖 ZombieBuddy。玩家在模组菜单启用本体时，游戏会自动启用已安装的前置。运行支持范围为 B42.22.2（3d39148846）、经指纹核对的 PZ Optimization 和 ZombieBuddy 2.3.4 单人组合。启用后按 ZombieBuddy 的 Java 模组规则批准 JAR。如未通过接口检查，传送门会在扣电前拒绝开始行程。
- **三维资源 1.0.0。** Mod ID 为 SuQingViewpointModelResources。启用 Viewpoint 0.1.7 和本子模组，在重启后的 Delete → Graphics → Resource Packs 中分别启用传送门或返鲜冰箱模型。模型适用于相应玩法模组放置的物件。

行程保护以 JDK 25、B42.22.2 的 projectzomboid.jar 及 ZombieBuddy 2.3.4 的 ZombieBuddy.jar 作为构建依赖。用 javac --release 25 编译 java/suqingportaltravelguard 下的源文件，再以 jar --create 将该包的生成类放入 SuQingPortalsTravelGuard.jar。发布包的 12 个类与重新编译完全一致。JAR SHA-256 为 ffe5f8185c8a1f71a9fb32916602ae0939911aa7092035b117a63b0de0f68696。实际 PZO 和 ZombieBuddy 组合通过 26 项断言，未加载 PZO 的对照通过 2 项。Viewpoint 原生管理器通过 722 项独立开关及模型资源检查。跨分块传送和两种家具的游戏内显示待验收。

The existing Steam Workshop item contains both submods. The Lua base mod requires Travel Guard in version 0.1.6-rc.12. Model Resources can be enabled independently.

- **Travel Guard 0.1.0-rc.1.** The base mod requires SuQingPortalsTravelGuard, which requires ZombieBuddy. The Mods menu enables installed requirements with the base mod. Travel Guard supports the fingerprint-verified combination of B42.22.2 (3d39148846), PZ Optimization and ZombieBuddy 2.3.4 in single-player. Approve the JAR according to ZombieBuddy's rules. If required runtime checks fail, new transfers are refused before a battery debit.
- **Model Resources 1.0.0.** Mod ID SuQingViewpointModelResources requires Viewpoint 0.1.7. Enable it in the startup list. After restarting, open Delete → Graphics → Resource Packs and enable the portal or freshness-fridge models separately. The models apply to objects placed by the respective gameplay mods.

Build the Travel Guard with JDK 25. Compile java/suqingportaltravelguard using javac --release 25 against the installed B42.22.2 projectzomboid.jar and ZombieBuddy 2.3.4 ZombieBuddy.jar. Use jar --create to package the generated suqingportaltravelguard classes in SuQingPortalsTravelGuard.jar. All 12 published class files matched the rebuild. Native tests passed 26 assertions with PZO and ZombieBuddy and two without PZO. The Viewpoint resource manager passed 722 checks covering discovery, independent toggles, meshes and bindings. Cross-chunk travel and both objects' visuals still await gameplay checks.
