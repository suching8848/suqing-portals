# 传送门模型与 Viewpoint / Portal models and Viewpoint

0.1.2纯Lua版沿用下述修正后的完整资源，不更换模型、锚点或美术。The pure-Lua 0.1.2 update retains these corrected assets and anchors.

0.1.1 使用四槽实际占用状态：`mask = slot1×1 + slot2×2 + slot3×4 + slot4×8`。十六种组合分别导出真实模型，四方向共64张图片和绑定；槽位位置与管理界面一致。原封面及模组 icon 保留。

Version 0.1.1 represents actual slot occupancy: `mask = slot1×1 + slot2×2 + slot3×4 + slot4×8`. Sixteen model states and 64 directional sprites/bindings match the management slots. Existing cover and mod-icon art is retained.

| 项目 / Item | 当前资源 / Current resources |
| --- | --- |
| 模型 / Meshes | 16 original meshes; X east, Y south, Z up, 1 unit per tile |
| 普通图片 / Sprites | 64 RGBA images, 128×256 |
| 方向 / Facing | S=0, E=1, N=2, W=3 |
| 索引 / Index | `mask × 4 + facing` |
| 原生锚点 / Native anchor | `(64,192)` at tile scale 2 |
| 地面中心 / Ground center | `(64,224)`; +32px is the native tile-center projection |
| Viewpoint 原点 / Origin | Model Z=0; bindings XYZ=0, scale=1; framework already supplies tile center |
| 旋转 / Rotations | S=0°, E=−90°, N=180°, W=90° |
| 资源身份 / Resource identity | `SuQingPortals_tiles`, `suqing_portal_01`, tiledef `7836` |

旧128×384图片顶部有额外128像素透明区。0.1.1仅移除这块透明区并同步pack原始尺寸，保持网格、门体比例及世界坐标；预览和放置使用同一地块基准，不通过移动三维模型补偿二维错位。

The old 128×384 canvas contained an extra 128 transparent pixels above the object. The new export removes that region and updates pack dimensions without changing mesh scale or world coordinates. Preview and placed sprites share the native floor reference; no 3D translation conceals a 2D alignment error.

`art/model-source/anchor_alignment.png` 对照旧图与修正后的预览／放置；`anchor_four_facings.png` 展示四方向。图片按当前原生绘制公式叠加，属于离线投影检查，不是游戏截图。

The two anchor images in `art/model-source` compare the old canvas and corrected preview/placed projections across all facings. They are offline projections based on the current native formula, not in-game screenshots.

`VisualData.lua` 保存真实图片边界及逐行 alpha 区间，供普通视角精确点击补偿；透明门洞不当作实心点击区。Viewpoint 相机仍优先使用其原生命中路径。`setSpriteFromName` 保留tiledef属性，状态切换不替换门对象或专用电池数据。

`VisualData.lua` contains real image bounds and row-level alpha runs for precise ordinary-view picking fallback; transparent openings are excluded. Viewpoint cameras use native picking. `setSpriteFromName` preserves tile properties and changes appearance without replacing the gate or dedicated battery state.

当前PZ pack／tile读回、Viewpoint ObjReader／PackManifest、64绑定和Recipe.model原生中心计算已离线验证。结构检查数不代表玩法断言；实际FBO遮挡、第一／第三人称位置、缩放和点击仍由用户验收。

Native PZ pack/tile readback, Viewpoint OBJ/manifest parsing, all 64 bindings and native model-center calculations were checked offline. Structural counts are not gameplay assertions. Actual FBO occlusion, camera placement, zoom and interaction remain subject to user testing.
