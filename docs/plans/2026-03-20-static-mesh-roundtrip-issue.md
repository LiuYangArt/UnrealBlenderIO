# 功能需求：支持 StaticMesh 从 Unreal 到 Blender 再回 Unreal 的往返编辑

## 背景

当前项目已经支持“场景级”导入导出：

- UE 导出当前关卡的 JSON + FBX
- Blender 导入场景并编辑
- Blender 回写 JSON
- UE 再同步 Actor 增删与 Transform

但当前还不支持“资产级”的静态模型往返编辑，也就是：

1. 在 UE 中选中一个 `StaticMeshActor`
2. 一键发送到 Blender 编辑
3. Blender 编辑完成后
4. 一键发送回 UE，并直接覆盖原始 `StaticMesh` 资产

本 issue 的目标是新增这条资产级闭环能力。

## 方案结论

采用方案 A：**直接覆盖原始 StaticMesh 资产**。

效果：

- Blender 修改完成后，回到 Unreal 直接覆盖原始 `StaticMesh`
- 所有引用该 `StaticMesh` 的实例会自动同步更新

V1 对“一键”的定义：

- UE 侧一个按钮完成“导出会话”
- Blender 侧一个按钮完成“回传会话”
- UE 侧再提供一个显式按钮完成“应用 Blender 返回模型”

本轮不引入后台监听、端口通信或自动唤起对端应用。

## 目标

1. UE 5.5 中选中一个 `StaticMeshActor` 后，可以导出它引用的 `StaticMesh` 到独立 session 目录
2. Blender 5.0 可以导入该 session 并进行建模编辑
3. Blender 可以将编辑后的结果导出回 session 目录
4. UE 5.5 可以读取该 session，并将返回的 FBX 覆盖导入到原始 `StaticMesh`
5. 所有引用该网格的实例会一起更新

## 非目标

1. 不支持 `SkeletalMesh`
2. 不支持 Blueprint 内嵌静态网格组件回写
3. 不支持 ISM/HISM
4. 不做后台通信与自动联动
5. 不承诺第一版完整保留碰撞、LOD、Socket、复杂材质导入细节

## 设计要点

### 1. 单独的 StaticMesh 会话协议

不要复用当前场景 JSON 结构，新增独立 `session.json`，至少包含：

- `session_id`
- `status`
- `source_actor.label`
- `source_actor.guid`
- `source_asset.asset_name`
- `source_asset.asset_path`
- `paths.source_fbx`
- `paths.edited_fbx`

### 2. 独立 session 目录

建议目录：

```text
C:\Temp\UBIO\StaticMeshSessions\<session_id>\
```

目录内至少包含：

- `session.json`
- `source.fbx`
- `edited.fbx`

### 3. V1 状态流转

- `EXPORTED_FROM_UE`
- `IMPORTED_IN_BLENDER`
- `EXPORTED_FROM_BLENDER`
- `REIMPORTED_IN_UE`
- `FAILED`

## 实施任务

### UE 侧

- [ ] 在 `UnrealAsset/Python/UnrealBlenderIO.py` 中新增“导出选中 StaticMesh 到 Blender”入口
- [ ] 校验当前只选中一个有效 `StaticMeshActor`
- [ ] 获取 `StaticMeshComponent` 引用的原始 `StaticMesh` 资产路径
- [ ] 导出 `source.fbx`
- [ ] 写入 `session.json`
- [ ] 新增“导入 Blender 返回的 StaticMesh”入口
- [ ] 校验 `edited.fbx` 与原始 `StaticMesh` 资产路径
- [ ] 将 `edited.fbx` 重新导入到原始 `StaticMesh`
- [ ] 保存资产
- [ ] 在 `EUW_UBIO.uasset` 中增加按钮入口

### Blender 侧

- [ ] 在 `UI.py` 中新增静态模型往返分组与路径属性
- [ ] 在 `UnrealBlenderIO.py` 中新增“导入最新静态模型会话” operator
- [ ] 读取 `session.json` 并导入 `source.fbx`
- [ ] 将会话元数据写到导入对象或 collection
- [ ] 在 `UnrealBlenderIO.py` 中新增“发送当前静态模型回 Unreal” operator
- [ ] 导出 `edited.fbx`
- [ ] 更新 `session.json` 状态与时间戳
- [ ] 在 `util.py` 中增加静态模型 session 常量和辅助函数
- [ ] 补齐 `i18n/en_US.json` 与 `i18n/zh_HANS.json` 文案

## 验收标准

1. UE 5.5 中选中一个 `StaticMeshActor` 后，点击导出按钮可生成完整 session 目录
2. Blender 5.0 能成功导入该 session 并显示模型
3. Blender 编辑并回传后，session 目录中出现 `edited.fbx`
4. UE 5.5 能将该 `edited.fbx` 回导到原始 `StaticMesh`
5. 关卡中所有引用该 `StaticMesh` 的实例自动更新
6. 失败路径下能给出明确提示，不出现静默失败

## 风险说明

1. 方案 A 会直接覆盖原始 `StaticMesh`，影响该资产的全部引用实例
2. UE 5.5 Python 的静态网格导出与重导入 API 需要先做最小脚本验证
3. 第一版只承诺基础几何体闭环，不承诺高级资源属性完全无损

## 参考计划文档

详细设计见：

- `docs/plans/2026-03-20-static-mesh-roundtrip-plan.md`
