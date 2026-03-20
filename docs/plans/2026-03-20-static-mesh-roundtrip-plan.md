# UnrealBlenderIO 静态模型往返编辑实施计划

更新时间：2026-03-20  
目标版本：Unreal Engine 5.5 / Blender 5.0  
方案选择：方案 A，直接覆盖原始 StaticMesh 资产

## 0. 直接结论

当前项目可以在现有“文件交换 + 两侧 Python 工具按钮”的架构上，扩展出一条新的“单个 StaticMesh 资产往返编辑”链路，实现：

1. 在 Unreal Editor 中选中一个 `StaticMeshActor`。
2. 点击按钮，将它引用的 `StaticMesh` 资产导出为独立 FBX，并写入一份会话 JSON。
3. 在 Blender 中一键导入该会话，完成建模编辑。
4. 在 Blender 中一键导出编辑结果，回写会话 JSON。
5. 在 Unreal Editor 中一键读取该会话，并将返回的 FBX 重新导入到原始 `StaticMesh` 资产路径。

V1 对“一键”的定义是“每一端各一个按钮完成本端动作”，不引入常驻后台服务、不做端口通信、不做自动拉起对端应用。这样能最大化复用现有项目结构，用最小改动先把闭环能力做出来。

## 1. 背景与现状

### 1.1 当前项目已经具备的能力

1. Unreal 侧可以导出当前关卡的 JSON 与整关卡 FBX。
2. Blender 侧可以导入 JSON + FBX，恢复 Actor 元数据并编辑场景。
3. Blender 侧可以回写 JSON，Unreal 侧再读取 JSON，同步 Actor 增删与 Transform。
4. Unreal 与 Blender 之间已经有固定的本地交换目录：`C:\\Temp\\UBIO\\`。

### 1.2 当前项目尚不具备的能力

1. 不能从 Unreal 中单独导出一个选中的 `StaticMesh` 资产进行编辑。
2. 不能在 Blender 中把编辑后的几何体作为 FBX 回传给 Unreal。
3. 不能把 Blender 返回的 FBX 重新导入到原始 `StaticMesh` 资产。
4. 当前数据模型只围绕 Actor 实例同步，不围绕 StaticMesh 资产同步。

### 1.3 本次目标

在不引入后台服务和复杂通信的前提下，新增一条最小但完整的资产级往返通道，让用户能围绕“原始 StaticMesh 资产”完成一次可验证的编辑闭环。

## 2. 目标与边界

## 2.1 目标（必须达成）

1. UE 5.5 中选中一个 `StaticMeshActor` 后，可以一键导出其引用的 `StaticMesh` 到 Blender 会话目录。
2. Blender 5.0 中可以一键导入最新或指定的静态模型会话。
3. Blender 编辑完成后，可以一键导出修改后的 FBX 到会话目录。
4. UE 5.5 中可以一键将 Blender 返回的 FBX 重新导入到原始 `StaticMesh` 资产。
5. 同一个 `StaticMesh` 的所有引用实例在 UE 中会随资产重导入自动更新。

## 2.2 非目标（本轮不做）

1. 不支持 `SkeletalMesh`。
2. 不支持 `Blueprint Actor` 中嵌套的静态网格组件回写。
3. 不支持 `ISM/HISM`、`Nanite` 专项参数恢复、复杂碰撞重建、Socket 重建、LOD 全链路恢复。
4. 不做 Unreal 与 Blender 之间的自动监听通信。
5. 不保证材质槽顺序变化、碰撞设置、导入选项细节在第一版完全无损。

## 2.3 V1 一键体验定义

为避免需求误解，这里明确：

1. UE 侧“一键发送到 Blender”指：在 UE 中点击一次按钮，生成静态模型会话文件。
2. Blender 侧“一键发送回 Unreal”指：在 Blender 中点击一次按钮，导出回传 FBX 与会话状态。
3. UE 不会在 V1 自动检测 Blender 完成状态并立刻回收模型，仍保留一个显式“应用 Blender 返回模型”按钮。

这仍然满足“单击触发本端完整动作”的使用预期，同时显著降低工程复杂度。

## 3. 总体方案（Implementation Plan）

### 3.1 核心思路

新增一条“StaticMesh 会话流”，与现有“Scene JSON 同步流”并行存在，避免把资产编辑逻辑强行塞进场景同步数据模型。

本方案遵循两个原则：

1. **KISS**：不引入 socket、HTTP、守护进程，全部沿用本地文件交换。
2. **最小侵入**：尽量复用现有 UI、工具安装路径与临时目录，只增加少量新的 Operator 与 UE Python 入口。

### 3.2 建议的数据流

1. UE 读取当前选中的 `StaticMeshActor`。
2. UE 获取其 `StaticMeshComponent` 引用的 `StaticMesh` 资产路径。
3. UE 创建独立的 session 目录，导出源 FBX，写入 `session.json`。
4. Blender 导入 `session.json` 指向的 FBX，并把会话元数据写到导入对象的自定义属性。
5. Blender 编辑后导出 `edited.fbx`，并把 `session.json` 的状态改为可回收。
6. UE 读取 `session.json`，定位原始资产路径，执行 reimport 或 import-overwrite。
7. UE 保存该资产并提示完成。

### 3.3 为什么不复用现有场景 JSON 结构

当前场景同步是“Actor 实例视角”，其核心字段是：

1. `name`
2. `fname`
3. `fguid`
4. `actor_type`
5. `transform`

但静态模型往返编辑的关键身份字段是“静态网格资产路径”，比如 `/Game/Props/SM_Chair.SM_Chair`。  
如果继续复用场景 JSON，会把“实例同步”和“资产覆盖”两种模型混在一起，后续风险更大。因此应当单独定义静态模型会话 JSON。

## 4. 会话设计

### 4.1 目录结构

建议在 `C:\\Temp\\UBIO\\StaticMeshSessions\\` 下按 `session_id` 建立独立目录：

```text
C:\Temp\UBIO\StaticMeshSessions\
└─ 20260320_153000_SM_Chair_8f1a2c\
   ├─ session.json
   ├─ source.fbx
   └─ edited.fbx
```

这样做有三个好处：

1. 避免多个模型同时编辑时文件互相覆盖。
2. 便于追踪每次往返的状态与来源。
3. 后续如果加“导入最新静态模型会话”按钮，也能按目录时间排序。

### 4.2 `session.json` 建议结构

```json
{
  "schema_version": "1.0",
  "session_type": "static_mesh_roundtrip",
  "session_id": "20260320_153000_SM_Chair_8f1a2c",
  "ue_version": "5.5",
  "blender_version": "5.0",
  "status": "EXPORTED_FROM_UE",
  "source_actor": {
    "label": "SM_Chair_A",
    "guid": "..."
  },
  "source_asset": {
    "asset_name": "SM_Chair",
    "asset_path": "/Game/Props/SM_Chair.SM_Chair"
  },
  "paths": {
    "source_fbx": "C:\\Temp\\UBIO\\StaticMeshSessions\\...\\source.fbx",
    "edited_fbx": "C:\\Temp\\UBIO\\StaticMeshSessions\\...\\edited.fbx"
  },
  "export_options": {
    "axis": "UE_TO_BLENDER_DEFAULT",
    "unit": "CENTIMETERS"
  },
  "timestamps": {
    "exported_from_ue": "2026-03-20T15:30:00+08:00",
    "imported_in_blender": null,
    "exported_from_blender": null,
    "reimported_in_ue": null
  }
}
```

### 4.3 状态流转

建议使用明确状态，避免两侧逻辑通过“文件是否存在”做隐式推断：

1. `EXPORTED_FROM_UE`
2. `IMPORTED_IN_BLENDER`
3. `EXPORTED_FROM_BLENDER`
4. `REIMPORTED_IN_UE`
5. `FAILED`

状态设计的作用不是做复杂状态机，而是方便：

1. UI 上提示当前会话进展。
2. 出错时快速定位卡在哪一端。
3. 后续扩展“导入最近会话”时进行过滤。

## 5. Unreal 侧设计

### 5.1 功能入口

建议在 `UnrealAsset/Python/UnrealBlenderIO.py` 中新增两类入口，并在 UE Widget 中挂出按钮：

1. `ubio_export_selected_static_mesh_to_blender()`
2. `ubio_reimport_static_mesh_from_blender()`

如果现有 Editor Utility Widget 支持传参，则保留“导入最新会话”与“按文件路径导入”两种形式；否则第一版优先做“处理最新会话”。

### 5.2 导出前校验

点击“发送到 Blender”时，UE 侧必须先做以下校验：

1. 当前仅选中了一个 Actor。
2. 该 Actor 是 `StaticMeshActor`，或者至少存在 `StaticMeshComponent`。
3. `StaticMeshComponent.static_mesh` 不为空。
4. 目标临时目录可写。

任一条件失败时，直接在 UE 内给出明确提示，不进入导出流程。

### 5.3 导出逻辑

导出逻辑分四步：

1. 从选中的 Actor 取到 `StaticMesh` 资产对象与资产路径。
2. 生成独立 session 目录与 `session.json`。
3. 将 `StaticMesh` 资产导出为 `source.fbx`。
4. 更新 `session.json` 状态为 `EXPORTED_FROM_UE`。

这里最关键的是：导出的对象必须是静态网格资产，而不是关卡 Actor 或整关卡 World。  
实施时需要针对 UE 5.5 Python API 验证合适的 `AssetExportTask` 导出器组合，并把导出参数固定下来。

### 5.4 回收逻辑

点击“应用 Blender 返回模型”时，UE 侧执行：

1. 找到最新或指定的 `session.json`。
2. 校验 `edited.fbx` 是否存在。
3. 校验 `source_asset.asset_path` 指向的原始 `StaticMesh` 资产是否仍存在。
4. 使用 UE 5.5 Python API 对该资产执行 reimport 或覆盖式重新导入。
5. 保存资产。
6. 更新 `session.json` 状态为 `REIMPORTED_IN_UE`。

### 5.5 UE 侧 UI 建议

建议在现有 UE Widget 中增加一个独立分组，而不是把按钮混到场景导入导出区域里：

1. `发送选中 StaticMesh 到 Blender`
2. `导入 Blender 返回的 StaticMesh`
3. `打开最新会话目录`（可选）

第一版不做过多参数配置，先把路径和行为固定，减少误操作空间。

## 6. Blender 侧设计

### 6.1 功能入口

Blender 侧建议新增两个 Operator：

1. `导入最新静态模型会话`
2. `发送当前静态模型回 Unreal`

必要时再补一个“按路径导入静态模型会话”的手动入口。

### 6.2 导入逻辑

Blender 导入时：

1. 读取 `session.json`。
2. 校验 `source.fbx` 存在。
3. 通过 `bpy.ops.import_scene.fbx` 导入。
4. 将以下元数据写入根对象自定义属性：
   - `ubio_session_id`
   - `ubio_session_dir`
   - `ubio_source_asset_path`
   - `ubio_source_actor_guid`
   - `ubio_roundtrip_type = StaticMesh`
5. 将 `session.json` 状态改为 `IMPORTED_IN_BLENDER`。

### 6.3 编辑约束

为了保证第一版可控，文档与提示中应明确告知用户：

1. 可以编辑网格几何体。
2. 可以移动顶点、调整拓扑、修改 UV。
3. 不承诺复杂碰撞、Socket、LOD、导入材质规则完整保留。
4. 如果导入后出现多个对象，第一版只回传主对象或按集合统一导出，规则必须写死，不能让逻辑处于模糊状态。

建议第一版做法：

1. 导入后把所有对象放入专用 collection。
2. 导出时统一导出该 collection 内对象到 `edited.fbx`。

### 6.4 回传逻辑

点击“发送当前静态模型回 Unreal”时：

1. 从当前活动对象或专用 collection 读取会话信息。
2. 校验会话目录存在。
3. 导出 `edited.fbx`。
4. 将 `session.json` 状态改为 `EXPORTED_FROM_BLENDER`。
5. 记录导出时间。

### 6.5 Blender 侧 UI 建议

在现有 `UBIO` 面板新增一个“StaticMesh Roundtrip”分组，保持与当前场景工具分离：

1. `导入最新静态模型会话`
2. `发送当前静态模型回 Unreal`
3. `静态模型会话路径`

路径字段可沿用现有“文件路径 + operator”风格，但不要与场景 JSON 路径公用同一个属性，否则会造成状态混淆。

## 7. 文件改动建议

## 7.1 Unreal 侧

主要改动文件：

1. `UnrealAsset/Python/UnrealBlenderIO.py`
   - 新增选中 StaticMesh 导出函数
   - 新增 Blender 返回模型导入函数
   - 新增静态模型会话 JSON 读写函数
   - 新增会话目录发现函数
2. `UnrealAsset/UBIO/EUW_UBIO.uasset`
   - 新增对应按钮并绑定 Python 入口

## 7.2 Blender 侧

主要改动文件：

1. `UI.py`
   - 新增静态模型往返分组与路径属性
2. `UnrealBlenderIO.py`
   - 新增静态模型会话导入导出 operator
   - 新增会话元数据写入与读取逻辑
3. `util.py`
   - 新增静态模型会话目录常量
   - 新增 session 路径辅助函数
4. `i18n/en_US.json`
5. `i18n/zh_HANS.json`
   - 新增新按钮、新提示、新错误文案

## 7.3 为什么不建议新开过多文件

仓库当前规模不大，现有功能集中在少数核心文件中。  
第一版建议坚持最小可审阅修改，不额外拆出一套复杂模块，避免为了“结构漂亮”引入不必要维护成本。

## 8. 分阶段任务拆解（Task List）

### Phase 1：会话协议与目录结构落地

- [ ] 定义静态模型会话 JSON 结构
- [ ] 定义 session 目录命名规则
- [ ] 在 Blender 与 UE 两端统一状态枚举与字段名

### Phase 2：UE 5.5 侧导出链路

- [ ] 读取当前选中的 `StaticMeshActor`
- [ ] 获取 `StaticMeshComponent` 与原始 `StaticMesh` 资产路径
- [ ] 导出 `source.fbx`
- [ ] 写入 `session.json`
- [ ] 在 UE Widget 中增加“发送选中 StaticMesh 到 Blender”按钮

### Phase 3：Blender 5.0 侧导入链路

- [ ] 新增静态模型会话路径属性
- [ ] 新增“导入最新静态模型会话” operator
- [ ] 导入 `source.fbx`
- [ ] 把会话元数据写到对象或 collection
- [ ] 更新 `session.json` 状态为 `IMPORTED_IN_BLENDER`

### Phase 4：Blender 5.0 侧回传链路

- [ ] 新增“发送当前静态模型回 Unreal” operator
- [ ] 导出 `edited.fbx`
- [ ] 更新 `session.json` 状态为 `EXPORTED_FROM_BLENDER`
- [ ] 增加必要错误提示与路径校验

### Phase 5：UE 5.5 侧覆盖回导链路

- [ ] 读取最新或指定 `session.json`
- [ ] 校验 `edited.fbx` 与原始 `StaticMesh` 资产路径
- [ ] 重新导入到原始 `StaticMesh`
- [ ] 保存资产并提示完成
- [ ] 在 UE Widget 中增加“导入 Blender 返回的 StaticMesh”按钮

### Phase 6：文案、验证与收尾

- [ ] 补齐中英文文案
- [ ] 完成最小闭环手测
- [ ] 记录限制项与已知风险

## 9. 验收标准

以下条件全部满足，才视为功能完成：

1. 在 UE 5.5 中选中一个 `StaticMeshActor` 后，点击导出按钮可生成完整会话目录。
2. Blender 5.0 能成功导入该会话并显示可编辑模型。
3. Blender 修改并回传后，会话目录中能生成 `edited.fbx`，且状态正确更新。
4. UE 5.5 能读取该会话，并把 `edited.fbx` 重新导入到原始 `StaticMesh` 资产。
5. 所有引用该 `StaticMesh` 的实例会一起更新。
6. 异常路径下有明确提示，不会静默失败。

## 10. 手动测试步骤

### 10.1 基础闭环验证

1. 在 UE 5.5 打开测试关卡。
2. 选中一个仅被少量实例引用的 `StaticMeshActor`。
3. 点击 `发送选中 StaticMesh 到 Blender`。
4. 预期结果：
   - 生成新的 session 目录
   - 目录内包含 `session.json` 与 `source.fbx`
5. 打开 Blender 5.0。
6. 点击 `导入最新静态模型会话`。
7. 预期结果：
   - 模型成功导入
   - 对象附带会话元数据
8. 在 Blender 中做可见修改，例如拉伸一个顶点面。
9. 点击 `发送当前静态模型回 Unreal`。
10. 预期结果：
   - 会话目录出现 `edited.fbx`
   - `session.json` 状态更新为 `EXPORTED_FROM_BLENDER`
11. 回到 UE 5.5，点击 `导入 Blender 返回的 StaticMesh`。
12. 预期结果：
   - 原始 `StaticMesh` 被覆盖更新
   - 场景中所有引用该网格的实例同时变化

### 10.2 失败路径验证

1. UE 中未选中 Actor 时点击导出。
2. 预期结果：提示“必须选中一个 StaticMeshActor”。
3. Blender 中未导入会话对象时点击回传。
4. 预期结果：提示“当前对象不存在有效会话”。
5. 删除 `edited.fbx` 后在 UE 中点击回导。
6. 预期结果：提示“找不到 Blender 返回文件”。

## 11. 风险与控制

### 11.1 影响范围风险

风险：方案 A 会直接覆盖原始 `StaticMesh` 资产，所有引用实例都会一起变化。  
控制：第一版只建议对测试资产或低复用资产使用，并在 UI 文案里明确提示影响范围。

### 11.2 API 兼容性风险

风险：UE 5.5 Python 的静态网格导出与重导入 API 细节可能与现有脚本不同。  
控制：实施前先用最小脚本验证导出器、导入器与 reimport 入口，再接入正式流程。

### 11.3 导入选项漂移风险

风险：FBX 重新导入后，法线、材质槽、碰撞、LOD 等细节可能与原资产不完全一致。  
控制：V1 只承诺“基础几何体闭环”，高级资源属性单独列为后续增强项。

### 11.4 多对象导出风险

风险：Blender 里用户可能把导入对象拆分成多个对象，导致 UE 侧回导结果不可预测。  
控制：第一版明确导出规则，要么统一导出 collection，要么只认主对象，不能在实现中保留模糊行为。

## 12. 里程碑建议

1. M1：完成会话协议、路径约定、UE 导出验证脚本。
2. M2：完成 Blender 导入与回传最小闭环。
3. M3：完成 UE 原资产回导与保存。
4. M4：补齐文案、手测、错误提示。

建议实施顺序必须严格按上面里程碑推进，不要先做 UI，再回头补协议。

## 13. Thought

1. 这次需求的本质不是“把当前场景同步按钮改一下”，而是新增一条围绕 `StaticMesh` 资产本体的同步链路。
2. 方案 A 最大价值在于它最符合建模工作流直觉：改的是网格资产本体，而不是某个关卡实例。
3. 第一版最重要的是把“会话协议”和“回导目标”设计对，否则后面越写越容易和现有场景同步逻辑缠在一起。
4. 按当前仓库规模，最优策略不是大拆模块，而是围绕现有 `UI.py`、`UnrealBlenderIO.py`、`util.py` 和 UE 侧单脚本做最小扩展。
5. 只要先把 UE 5.5 的 `StaticMesh` 导出和重导入 API 验证清楚，这个功能整体风险是可控的。
