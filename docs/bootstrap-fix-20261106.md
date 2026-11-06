# 2026-11-06 隔离启动修复

用户首次启动停在 Lua 调试器。隔离 `console.txt` 对应 B42.21.0，明确显示 `ZomboidFileSystem.loadMods(0 mods)`；异常 Lua 栈全部来自安装在游戏 `media/lua` 内的 PZO 脚本。并没有进入门户或 Viewpoint 的模组加载流程，因此不能把本次启动失败归因于其功能代码。

两项独立原因：

1. 旧入口仅保留原版 Java 类路径，却仍在原游戏工作目录读取 PZO Lua。截图中的 `pzopt_benchmark.lua` 调用 `PerformanceSettings.pzoptBenchmark`，原版类没有此方法。
2. 新缓存目录没有本版本的 `mods/reset-mods-42_00.txt`。原引擎首次启动生成该标记并清空 `default.txt`，导致原先准备的五项名单被清除。标记只按是否存在判断，未解析内容；今后换版本仍需核实规则。

用户随后明确允许保留 PZO 做隔离测试，并要求把经验写入项目 `AGENTS.md`。当前入口改为沿用安装中匹配的 `pzopt/aot/pzopt.jar;projectzomboid.jar` 及原目录 Lua／shader，保留独立 cachedir、home、临时目录、PZO 用户选项和 ZombieBuddy 配置。没有修改原启动 JSON 或原游戏 PZO 文件。五项默认名单已恢复，并预建当前版本标记。没有复用正式存档。

离线修复验证：

- 47 项 PZO 接口及路径检查通过：实际类来自 PZO JAR，19 份 PZO Lua 请求的 43 个相关接口均存在，PZO 用户选项解析到隔离 `data/pzopt/options.ini`。
- 21 项原生首次启动配置回归通过：当前五项 ID 与顺序正确；缺标记的独立临时对照会清空名单，有标记会保留；原测试目录的标记和名单在验证中保持。
- 修订后 PowerShell 启动脚本解析通过。本次写入范围为隔离实例、项目工具／说明和用户要求的 `AGENTS.md`；没有写正式存档。最终核对发现正式档 `mods.txt`、`map_sand.bin` 与初版交付的旧保护基线已不同，保留其现状，不归因也不恢复旧值。其余六项受保护文件与初版基线一致；该差异单列在修复回执中，不能继续声称整个旧基线均未变。

失败日志、小型启动配置回退副本、当前修复记录：`D:\steam\steamapps\common\ProjectZomboid\CodexAssets\SuQingPortals_20261106\BootstrapFix_20261106`。测试入口与桌面快捷方式位置保持。

排查中另准备并离线验证过不含 PZO 的独立资源视图，作为对照资料保留；当前桌面入口采用用户认可的保留 PZO 路线，不使用该视图。没有启动或操作游戏；修复后的实际模组装载、Viewpoint 和门户玩法仍由用户重新启动验收。

原冻结测试 ZIP 的模组运行文件保持，启动修订及当前说明以此记录、源码 README 和实例中的当前文件为准。
