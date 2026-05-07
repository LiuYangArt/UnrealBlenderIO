# UnrealBlenderIO Blueprint 多 StaticMesh Roundtrip 实施方案

更新时间：2026-05-07  
目标版本：Unreal Engine 5.5 / Blender 5.0  
方案定位：在现有单 StaticMesh roundtrip 基础上，扩展为“Blueprint Actor 局部装配 roundtrip”

## 0. 本次修订结论

2026-05-06 版本的方案已经明确了“UE 侧按唯一资产导出 / Blender 侧按组件查看 / UE 侧按资产 reimport”的大方向，这一点仍然成立。  
但旧版方案在 Blender 表示模型上还有三个关键缺口，必须在文档层先补齐，否则实现时一定会反复返工：

1. 只依赖 `parent_component_key + relative_transform` 恢复布局，不足以覆盖 Blueprint 中常见的中间 `SceneComponent` 链。
2. 把“首个组件实例”直接当作 canonical 导出源，会把组件装配 transform 污染进资产 FBX。
3. 对“一个资产导入成多个 Blender 对象”的情况，没有定义稳定的组根与导出锚点。

因此，本次修订后的直接结论是：

1. 保留 UE 侧“多组件收集 + 唯一资产去重 + 逐资产导出 / reimport”的总体方向。
2. 放弃 Blender 侧 `Sources/Layout + collection instance` 的用户主工作流。
3. Blender 侧改为“**单可见会话组 + 隐藏 canonical 资产组 + linked data 可见实例**”方案。
4. Blender 中所有组件实例统一通过 **wrapper empty** 承载组件级 transform。
5. Blender 默认布局恢复不再依赖 `relative_transform`，而依赖 UE 导出阶段预先烘焙好的 `actor_local_transform`。
6. canonical 资产组始终保持在**资产局部空间**；任何可见组件实例都不是导出源本体。
7. `session_type` 仍保持 `bp_static_mesh_roundtrip`，但 `schema_version` 升级，loader 必须兼容旧字段名与旧布局。

## 1. 为什么不能在旧 Blender 方案上继续小修

当前问题不是单点 bug，而是表示模型不够稳。

### 1.1 旧方案的主要问题

旧方案的问题不只是“collection instance 不顺手”，还包括下面几个结构性风险：

1. `collection instance` 不利于直接检查和直接编辑。
2. `Sources/Layout` 双层结构把“资产源对象”和“组件预览对象”强行拆开，理解成本高。
3. 旧方案默认认为 `relative_transform` 足够恢复组件布局，但 Blueprint 中经常存在 `SceneComponent -> SceneComponent -> StaticMeshComponent` 的中间链；如果 UE 侧只导出 mesh 组件，Blender 侧无法无损重建这条链。
4. 如果 canonical 直接借用某个可见组件实例，就会把该组件的装配位置、旋转、缩放混进资产局部空间，最终污染导出 FBX。
5. 对多对象资产缺少稳定根节点定义，后续 parent、导出、日志和选择逻辑都会发散。

### 1.2 哪些方向仍然正确

以下方向不需要推翻：

1. UE 侧支持选中一个带多个 `StaticMeshComponent` 的 BP Actor。
2. UE 侧按唯一 `StaticMesh` 资产去重导出 `source.fbx`。
3. session 协议中保留 `assets[]` 与 `components[]` 的双粒度结构。
4. Blender 回传时按唯一资产逐个写出 `edited.fbx`。
5. UE 侧逐资产 reimport，同一资产只 reimport 一次。

### 1.3 哪些部分必须重写

以下部分应视为设计变更，不建议在旧实现上继续补丁：

1. Blender 侧 `Sources/Layout` 的组织方式。
2. Blender 侧 `collection instance` 的实例恢复方式。
3. 以 `relative_transform` 为默认恢复链的布局逻辑。
4. 让可见实例兼任 canonical 导出源的元数据模型。
5. 旧的 `source_object_names` 语义。

## 2. 修订后的目标与边界

### 2.1 本轮目标

1. 支持选中一个 BP Actor，并处理其下全部有效 `StaticMeshComponent`。
2. 同一 `StaticMesh` 资产只导出一次、只回传一次。
3. Blender 中提供一个**用户可直接使用**的会话组，不再要求用户理解 `Sources/Layout`。
4. Blender 中整组 root 固定在世界原点。
5. Blender 中组件装配默认按 `actor_local_transform` 正确恢复。
6. 同一资产被多个组件复用时，在 Blender 中复用同一份 mesh data。
7. UE 回传时仍能稳定映射回不同原始 `StaticMesh` 资产。
8. 对“多对象资产”的 canonical 根、组件根、导出锚点给出明确规则。

### 2.2 本轮非目标

1. 不处理 `SkeletalMeshComponent`。
2. 不处理 `ISM/HISM/Foliage`。
3. 不做 Blueprint 结构回写，不新增 / 删除组件。
4. 不做 Blueprint 组件 transform 回写。
5. 不处理材质、碰撞、Socket、LOD、Nanite 的完整无损 roundtrip。
6. 不处理“在 Blender 中修改组件引用关系后回写 UE”的能力。
7. 不做自动监听，仍保留显式按钮触发。

### 2.3 V1 对“可编辑”的精确定义

这次必须把“什么能改、什么不能改”写清楚：

1. **可 roundtrip 的核心内容**：静态网格资产几何本体的修改。
2. **只用于上下文预览、不回写 UE 的内容**：组件 wrapper 的摆放、组件之间的装配关系。
3. **对多对象资产的额外约束**：
   - mesh data 编辑会联动；
   - asset 内部子对象的 object-level transform 修改，默认只在 canonical 源组上受支持；
   - 在普通可见实例上改 asset 内部子对象的 object transform，不保证回传。

## 3. 修订后的关键设计决策

### 3.1 用户可见模型与内部模型分离

修订后的核心不是“只保留一个 collection”，而是：

1. **用户只需要面对一个可见会话组**。
2. **内部仍保留一组隐藏 canonical 资产对象**，用于稳定导出。
3. 旧方案的问题是把 `Sources/Layout` 当作用户主工作流；新方案允许内部有 canonical 缓存，但它不再是用户必须理解的操作层。

建议结构：

```text
UBIO_BP_<ActorLabel>_<SessionSuffix>
|- BP_<ActorLabel>_ROOT
|  |- CMP_SeatComponent
|  |  |- SeatComponent__0
|  |- CMP_Leg_FL
|  |  |- Leg_FL__0
|  |- CMP_Leg_FR
|  |  |- Leg_FR__0
|- _UBIO_INTERNAL
   |- SRC_SM_ChairSeat_ROOT
   |  |- SM_ChairSeat__SRC__0
   |- SRC_SM_ChairLeg_ROOT
      |- SM_ChairLeg__SRC__0
```

说明：

1. `BP_<ActorLabel>_ROOT` 是用户可见的装配根，固定在 Blender 世界原点。
2. `CMP_<ComponentName>` 是组件 wrapper empty，只承载组件级 transform。
3. `_UBIO_INTERNAL` 是内部隐藏 collection，不作为日常操作入口。
4. `SRC_<AssetName>_ROOT` 是每个资产的 canonical 根，始终停留在资产局部空间。
5. 可见组件对象与 canonical 对象共享 mesh data，但不共享 object transform。

### 3.2 transform 策略：默认使用 `actor_local_transform`

这是本次修订最重要的设计调整。

修订后规则如下：

1. Blender 会话 root 固定放在世界原点 `(0, 0, 0)`。
2. 不把 UE Actor 的 world transform 直接应用到 Blender root。
3. UE 导出阶段必须为每个组件计算 `actor_local_transform`：
   - 定义：组件相对于 Actor root 的最终局部 transform；
   - 这个结果必须已经吸收中间 `SceneComponent` 链的影响；
   - 推荐计算方式：`actor_local_transform = inverse(actor_world_transform) * component_world_transform`。
4. Blender 导入时默认使用 `actor_local_transform` 恢复组件 wrapper 的位置、旋转、缩放。
5. `relative_transform`、`parent_component_key`、`attach_chain` 继续保留，但主要用于：
   - 调试；
   - 校验；
   - 后续如果要恢复可视层级时使用。

这样做的结果是：

1. Blueprint 中是否存在中间 `SceneComponent`，不会再影响 Blender 的基础装配恢复。
2. Blender 端不需要先完整重建 UE 的 attach 树，才能把组件摆对。
3. root 固定在世界原点时，整组对象仍能以 Actor 局部坐标系正确展开。

### 3.3 组件层级策略：V1 默认扁平挂到 root

虽然 UE 协议仍可记录 `parent_component_key`，但 V1 的**默认可见层级**建议写死为：

1. 所有 `CMP_<ComponentName>` wrapper 直接挂到 `BP_<ActorLabel>_ROOT`。
2. 不强依赖 `parent_component_key` 去恢复 Blender 可见层级。
3. `parent_component_key` 在 V1 中只作为调试信息和未来扩展入口。

原因：

1. 组件布局回放的核心需求是“摆对位置”，不是“镜像 UE 原 attach 树”。
2. V1 本来就不做 Blueprint 结构回写。
3. 只要 `actor_local_transform` 已经烘焙好，扁平层级最稳、最容易排错。

### 3.4 canonical 与可见实例必须彻底解耦

这里必须明确一条硬规则：

1. **任何可见组件实例都不是 canonical 导出源。**
2. 每个唯一 `asset_key` 都有自己独立的 canonical 根与 canonical 对象组。
3. canonical 对象组始终保持在资产局部空间，不承载任何组件装配 transform。
4. 可见组件实例只是：
   - canonical 对象的对象副本；
   - 共享同一份 mesh data；
   - 父到某个组件 wrapper empty 下。
5. 导出 UE 时只导出 canonical 对象组，不导出任何可见组件实例。

这条规则是为了避免一个老问题：

- 如果首个组件实例直接复用 canonical，本地看起来省事；
- 但一旦该实例携带了组件装配 transform，导出时资产原点就会被污染。

### 3.5 多对象资产必须引入稳定根节点

对“一个 UE StaticMesh 导入 Blender 后变成多个对象”的情况，V1 也要有稳定规则：

1. 每个资产都必须创建一个 canonical 根 empty：`SRC_<AssetName>_ROOT`。
2. 该资产导入出的所有对象都 parent 到这个 canonical 根下。
3. 每个组件都必须创建一个组件 wrapper empty：`CMP_<ComponentName>`。
4. 该组件对应的所有可见对象都 parent 到这个 wrapper 下。
5. canonical 根与组件 wrapper 都是**组级锚点**，后续 parent、日志、导出、选择逻辑都围绕这两个锚点展开。

这样即使资产包含多个 mesh 对象，也有稳定答案：

1. 资产级导出锚点是谁：`SRC_<AssetName>_ROOT`。
2. 组件级摆放锚点是谁：`CMP_<ComponentName>`。
3. 组件内部“整组移动”改谁：wrapper。
4. 资产内部“对象局部关系”改谁：canonical 根下的对象组。

### 3.6 linked data 的正确使用边界

修订后 Blender 中的“实例”语义改成：

1. 首次导入某个唯一资产时，生成 canonical 对象组。
2. 后续每个组件都复制一组普通 Blender Object。
3. 这些对象共享 canonical 对应对象的 `obj.data`。
4. 这些对象在 Outliner 中仍然是普通对象，不是 `collection instance`。

需要明确 linked data 的边界：

1. **共享的是 mesh data，不是 object transform。**
2. 所以：
   - 改几何、改拓扑、改 UV：可以联动；
   - 改某个可见实例里子对象的 object transform：不会自动回写到 canonical。
3. 因此对于多对象资产：
   - 默认推荐用户做几何编辑；
   - 若要修改 asset 内部子对象的 object-level transform，应切到 canonical 源组进行编辑，或使用“跳转到 canonical”辅助功能。

### 3.7 `world_transform` 与旧字段的用途

`world_transform` 与旧字段不删除，但角色调整为：

1. `world_transform`
   - 调试；
   - 导入校验；
   - fallback 恢复。
2. `relative_transform`
   - 保留原始 UE 组件相对父节点数据；
   - 用于日志和后续扩展；
   - 不再作为默认布局恢复字段。
3. `parent_component_key`
   - 保留关系信息；
   - 默认不驱动 Blender 可见层级。
4. `root_transform`
   - 视为旧字段别名；
   - 新文档统一改名为 `source_actor_world_transform`。
5. `source_object_names`
   - 视为旧字段别名；
   - 新文档统一改名为 `canonical_object_names`。

## 4. 会话协议修订

### 4.1 会话类型保持不变

session 类型仍建议使用：

- `bp_static_mesh_roundtrip`

这点不变。

### 4.2 目录结构保持基本不变

目录结构仍建议保持：

```text
C:\Temp\UBIO\BPStaticMeshSessions\<session_id>\
|- session.json
|- assets\
|  |- <asset_key>\
|  |  |- source.fbx
|  |  |- edited.fbx
|- logs\
   |- export_ue.json
   |- import_blender.json
   |- export_blender.json
   |- reimport_ue.json
```

原因：

1. UE 侧天然适合按资产目录管理。
2. 逐资产导出 / reimport / 重试都更清晰。
3. Blender 表示模型变化，不影响落盘目录结构。

### 4.3 session.json 建议结构

建议结构修订为：

```json
{
  "schema_version": "2.2",
  "session_type": "bp_static_mesh_roundtrip",
  "session_id": "20260507_101500_BP_ChairSet_ab12cd",
  "status": "EXPORTED_FROM_UE",
  "ue_version": "5.5",
  "blender_version": "5.0",
  "source_actor": {
    "label": "BP_ChairSet_A",
    "guid": "...",
    "class_path": "/Game/BP/BP_ChairSet.BP_ChairSet_C"
  },
  "source_actor_world_transform": {
    "location": {"x": 0, "y": 0, "z": 0},
    "rotation": {"x": 0, "y": 0, "z": 0},
    "scale": {"x": 1, "y": 1, "z": 1}
  },
  "blender_import_policy": {
    "root_at_world_origin": true,
    "component_transform_mode": "ACTOR_LOCAL_BAKED",
    "component_hierarchy_mode": "FLAT_UNDER_ROOT",
    "instance_mode": "LINKED_DATA",
    "canonical_storage": "INTERNAL_HIDDEN"
  },
  "assets": [
    {
      "asset_key": "sm_chair_seat_a1b2c3",
      "asset_name": "SM_ChairSeat",
      "asset_path": "/Game/Props/SM_ChairSeat.SM_ChairSeat",
      "source_fbx": "C:\\Temp\\UBIO\\BPStaticMeshSessions\\...\\assets\\sm_chair_seat_a1b2c3\\source.fbx",
      "edited_fbx": "C:\\Temp\\UBIO\\BPStaticMeshSessions\\...\\assets\\sm_chair_seat_a1b2c3\\edited.fbx",
      "component_keys": ["SeatComponent"],
      "canonical_root_name": "SRC_SM_ChairSeat_ROOT",
      "canonical_object_names": [],
      "edited_object_names": [],
      "reimport_status": "PENDING"
    },
    {
      "asset_key": "sm_chair_leg_d4e5f6",
      "asset_name": "SM_ChairLeg",
      "asset_path": "/Game/Props/SM_ChairLeg.SM_ChairLeg",
      "source_fbx": "C:\\Temp\\UBIO\\BPStaticMeshSessions\\...\\assets\\sm_chair_leg_d4e5f6\\source.fbx",
      "edited_fbx": "C:\\Temp\\UBIO\\BPStaticMeshSessions\\...\\assets\\sm_chair_leg_d4e5f6\\edited.fbx",
      "component_keys": ["Leg_FL", "Leg_FR", "Leg_BL", "Leg_BR"],
      "canonical_root_name": "SRC_SM_ChairLeg_ROOT",
      "canonical_object_names": [],
      "edited_object_names": [],
      "reimport_status": "PENDING"
    }
  ],
  "components": [
    {
      "component_key": "Leg_FL",
      "component_name": "Leg_FL",
      "component_class": "StaticMeshComponent",
      "asset_key": "sm_chair_leg_d4e5f6",
      "actor_local_transform": {
        "location": {"x": 0, "y": 0, "z": 0},
        "rotation": {"x": 0, "y": 0, "z": 0},
        "scale": {"x": 1, "y": 1, "z": 1}
      },
      "relative_transform": {
        "location": {"x": 0, "y": 0, "z": 0},
        "rotation": {"x": 0, "y": 0, "z": 0},
        "scale": {"x": 1, "y": 1, "z": 1}
      },
      "world_transform": {
        "location": {"x": 0, "y": 0, "z": 0},
        "rotation": {"x": 0, "y": 0, "z": 0},
        "scale": {"x": 1, "y": 1, "z": 1}
      },
      "parent_component_key": null,
      "attach_chain": ["DefaultSceneRoot", "LegOffset_FL", "Leg_FL"],
      "visible": true
    }
  ],
  "timestamps": {
    "exported_from_ue": "2026-05-07T10:15:00+08:00",
    "imported_in_blender": null,
    "exported_from_blender": null,
    "reimported_in_ue": null
  }
}
```

### 4.4 字段修订说明

1. `source_actor_world_transform`
   - 替代旧的 `root_transform` 表达。
   - 只表示 UE 原始 Actor 的 world transform，用于记录，不用于 Blender root 摆放。

2. `actor_local_transform`
   - 新增必需字段。
   - 它是 Blender 默认恢复组件布局时的主字段。
   - 必须由 UE 侧预先烘焙好，而不是让 Blender 侧自己猜。

3. `blender_import_policy`
   - 明确写死本轮策略，减少后续歧义。
   - 建议至少记录：
     - `root_at_world_origin`
     - `component_transform_mode`
     - `component_hierarchy_mode`
     - `instance_mode`
     - `canonical_storage`

4. `canonical_root_name`
   - 记录该资产 canonical 根 empty 的名称。
   - 方便 Blender 导出、日志和诊断。

5. `canonical_object_names`
   - 替代旧的 `source_object_names`。
   - 记录 canonical 资产组中实际参与导出的对象。

6. `attach_chain`
   - 推荐新增。
   - 用于记录从 Actor root 到目标组件的 attach 路径，便于排障。

### 4.5 兼容与迁移策略

这部分必须在方案里写死，避免实现时出现“同一 `session_type` 下新旧字段混用”的歧义。

1. `session_type` 不变，仍为 `bp_static_mesh_roundtrip`。
2. `schema_version` 升级到 `2.2`。
3. loader 必须兼容旧字段：
   - `root_transform` -> 视为 `source_actor_world_transform`
   - `source_object_names` -> 视为 `canonical_object_names`
4. 如果旧 session 没有 `actor_local_transform`：
   - 允许临时 fallback 到 `relative_transform` 或 `world_transform`；
   - 但必须在日志中明确记录是兼容降级路径；
   - 新导出流程生成的 session 必须补齐 `actor_local_transform`。
5. 不要求对已经导入到 Blender 场景中的旧对象做自动场景内迁移；V1 只要求 session 文件兼容。

## 5. UE 侧设计

### 5.1 保持总体方向

UE 侧总体方向不变，仍建议：

1. 保留专用导出入口。
2. 选中一个 BP Actor 后收集全部有效 `StaticMeshComponent`。
3. 按 `asset_path` 去重。
4. 每个唯一资产导出一个 `source.fbx`。
5. 写出 `session.json`。

### 5.2 组件收集逻辑必须升级

UE 侧收集逻辑不能只停留在“拿到 mesh 组件就写 relative transform”，还需要补齐：

1. `component_name`
2. `static_mesh`
3. `static_mesh.get_path_name()`
4. `relative_transform`
5. `world_transform`
6. `actor_local_transform`
7. `parent_component_key`（可选，默认用于调试）
8. `attach_chain`
9. 可见性状态

### 5.3 `actor_local_transform` 的计算要求

推荐写死为：

1. 先取 Actor 的 world transform。
2. 再取组件的 world transform。
3. 通过 `inverse(actor_world_transform) * component_world_transform` 得到组件相对 Actor root 的最终局部 transform。
4. 这个结果必须已经吸收中间 `SceneComponent` 链的偏移、旋转、缩放。

这样导出的 Blender 布局数据会更稳，也更容易验证。

### 5.4 资产记录与日志

UE 导出时建议补强日志：

1. `export_ue.json` 中按 `asset_key` 记录：
   - `asset_path`
   - `source_fbx`
   - `component_keys`
2. 按 `component_key` 记录：
   - `actor_local_transform`
   - `relative_transform`
   - `world_transform`
   - `attach_chain`
3. 如果某组件缺失 `actor_local_transform` 或链计算失败，应直接失败并说明原因，不要静默退化。

### 5.5 UE reimport 逻辑

UE 侧 reimport 逻辑仍建议保留：

1. 遍历 `assets[]`。
2. 找到各自的 `edited.fbx`。
3. 按 `asset_path` 逐个 reimport。
4. 更新 `reimport_status`。
5. 允许部分失败并汇总整体状态。
6. 若存在部分失败，整个 session 状态可标记为 `PARTIAL_FAILED`，不要把整体误写成成功。

## 6. Blender 侧修订设计

### 6.1 导入入口

入口名仍可使用：

- `import_bp_static_mesh_session(session_file)`

但实现思路需要改写。

### 6.2 导入后的场景结构

导入后建议强制建立以下结构：

1. 顶级会话 collection：`UBIO_BP_<ActorLabel>_<SessionSuffix>`
2. 用户可见 root empty：`BP_<ActorLabel>_ROOT`
3. 内部隐藏 collection：`_UBIO_INTERNAL`
4. 每个资产一个 canonical 根：`SRC_<AssetName>_ROOT`
5. 每个组件一个 wrapper empty：`CMP_<ComponentName>`

### 6.3 Blender 导入流程

修订后导入流程建议为：

1. 读取 `session.json`。
2. 校验 session 类型、schema 和关键字段。
3. 创建顶级会话 collection。
4. 创建 `BP_<ActorLabel>_ROOT`，并固定在世界原点。
5. 创建 `_UBIO_INTERNAL` collection，并默认隐藏。
6. 遍历 `assets[]`，逐个导入 `source.fbx`。
7. 为每个资产建立 canonical 根 empty。
8. 把导入出的对象统一 parent 到 canonical 根下。
9. 为 canonical 根和 canonical 对象写入 `asset_key`、`session_id` 等元数据。
10. 遍历 `components[]`。
11. 为每个组件创建 `CMP_<ComponentName>` wrapper empty，并挂到可见 root 下。
12. 把 canonical 对象组按一一对应方式复制为普通对象，复制结果 parent 到 wrapper 下，并共享 `obj.data`。
13. 对 wrapper 应用 `actor_local_transform`。
14. 记录导入日志、canonical 对象名、wrapper 名和兼容 fallback 信息。

### 6.4 为什么 wrapper empty 是必需的

wrapper empty 不是装饰，而是本方案能稳定工作的关键：

1. 组件级装配 transform 只放在 wrapper 上。
2. canonical 对象组始终留在资产局部空间，不被装配 transform 污染。
3. 多对象资产可以整组 parent / 隐藏 / 选择 / 日志归类。
4. 导出时可以明确区分：
   - 哪些是资产源对象；
   - 哪些只是用户可见的装配实例。

### 6.5 编辑体验与约束

修订后用户体验目标是：

1. Outliner 中默认看到最终装配。
2. 不需要理解 `Sources/Layout`。
3. 可直接框选、查看、隐藏、检查对象。
4. 同一资产复用的组件能自动联动更新几何。

但下面这些约束必须明确写进 UI 提示或日志：

1. 移动 `CMP_<ComponentName>` wrapper 只影响 Blender 预览，不会回写 UE Blueprint 组件位置。
2. 对普通可见实例做 mesh data 编辑，会通过 linked data 联动到 canonical。
3. 对普通可见实例做 object-level 子对象 transform 编辑，不保证回传。
4. 若用户需要改 asset 内部子对象的 object transform，应通过 helper 跳到 canonical 源组编辑。

### 6.6 Blender 导出入口

入口名仍可使用：

- `export_bp_static_mesh_session_to_fbx(context, session_file, session_data)`

但导出规则必须改成：

1. 不再从可见组件实例找导出对象。
2. 逐个 `asset_key` 找到该资产对应的 canonical 根。
3. 只导出 canonical 根下的 canonical 对象组。
4. 为每个资产写一份 `edited.fbx`。
5. 回写 `canonical_root_name`、`canonical_object_names`、`edited_object_names` 和导出日志。

### 6.7 Blender 导出前验证

建议在导出前加最小必要校验：

1. 每个 `asset_key` 都能定位到 canonical 根。
2. canonical 根下至少有一个可导出的 mesh 对象。
3. 若 session 是旧 schema 且缺失新字段，日志中必须标记兼容路径。
4. 若检测到可见实例与 canonical 的对象级 transform 已明显漂移，可给出警告：
   - 几何编辑仍可导出；
   - 但 object-level transform 修改不会体现在导出结果中。

### 6.8 建议补的辅助能力

这几个辅助能力不一定首批必做，但非常值得列进方案：

1. `从当前组件跳到 canonical 资产源`。
2. `临时显示 / 隐藏 _UBIO_INTERNAL`。
3. `选中当前 asset 的所有组件实例`。
4. `显示当前 asset 的 canonical 对象组名单`。

## 7. 元数据与命名约定

### 7.1 建议新增或保留的 Blender 自定义属性

建议至少保留或新增：

1. `ubio_bp_session_id`
2. `ubio_bp_session_file`
3. `ubio_bp_asset_key`
4. `ubio_bp_component_key`
5. `ubio_bp_source_asset_path`
6. `ubio_bp_role`
   - `SESSION_ROOT`
   - `INTERNAL_ROOT`
   - `CANONICAL_ROOT`
   - `CANONICAL_OBJECT`
   - `COMPONENT_WRAPPER`
   - `COMPONENT_OBJECT`
7. `ubio_bp_instance_mode = LINKED_DATA`
8. `ubio_bp_is_canonical = True/False`
9. `ubio_bp_transform_mode = ACTOR_LOCAL_BAKED`

### 7.2 collection 与对象命名建议

建议命名：

1. 顶级会话 collection：`UBIO_BP_<ActorLabel>_<SessionSuffix>`
2. root 对象：`BP_<ActorLabel>_ROOT`
3. 内部 collection：`_UBIO_INTERNAL`
4. canonical 根：`SRC_<AssetName>_ROOT`
5. canonical 对象：`<AssetName>__SRC__<index>`
6. 组件 wrapper：`CMP_<ComponentName>`
7. 组件可见对象：`<ComponentName>__<index>`

重点是：

1. 用户可见对象与 internal canonical 对象在命名上可直接区分。
2. 所有导出选择都基于 role 和 asset_key，不基于名字猜测。
3. canonical 根和 wrapper empty 是稳定锚点，不能省略。

## 8. 实现顺序建议

### 8.1 第一阶段：先修协议，不先修 UI

1. 在 UE 和 Blender 两端统一新字段名与默认值。
2. 增加 `actor_local_transform`。
3. 把 `root_transform` 升级为 `source_actor_world_transform`。
4. 把 `source_object_names` 升级为 `canonical_object_names`。
5. 补 `blender_import_policy`。
6. 先写兼容 loader，再改新 exporter。

### 8.2 第二阶段：升级 UE 导出

1. 保留现有多组件 / 多资产导出方向。
2. 计算并写出 `actor_local_transform`。
3. 补 `attach_chain` 与更完整日志。
4. 若 transform 烘焙失败，直接报错，不静默 fallback。

### 8.3 第三阶段：重写 Blender 导入

1. 去掉用户主工作流里的 `Sources/Layout`。
2. 去掉 `collection instance`。
3. 建立“可见 root + internal canonical”结构。
4. root 固定在世界原点。
5. 每个资产建立 canonical 根。
6. 每个组件建立 wrapper empty。
7. 用 linked data 表达重复资产实例。
8. 用 `actor_local_transform` 恢复 wrapper 布局。

### 8.4 第四阶段：重写 Blender 导出

1. 逐资产定位 canonical 根。
2. 只导出 canonical 对象组。
3. 回写 `canonical_root_name`、`canonical_object_names`、`edited_object_names`。
4. 对可见实例 transform 漂移给出日志警告。
5. 保持 UE 逐资产 reimport 不变。

### 8.5 第五阶段：辅助能力与提示

1. 增加“跳到 canonical”辅助能力。
2. 增加“显示 / 隐藏 internal canonical”辅助能力。
3. 增加必要的 UI 提示，明确哪些编辑会回传、哪些不会。

### 8.6 第六阶段：端到端验证与收尾

1. 做 Blueprint 样例端到端验证。
2. 补日志与报错。
3. 补兼容旧 schema 的验证。
4. 记录已知限制项与 postmortem。

## 9. 验证方案

### 9.1 最小正向用例

准备一个 BP Actor：

1. 至少 5 个 `StaticMeshComponent`。
2. 其中 4 个组件共用同一个腿部资产。
3. 另 1 个组件使用座面资产。
4. 至少有 1 个组件经过中间 `SceneComponent` 偏移后再挂载到 BP 上。
5. 组件带不同位置 / 旋转 / 缩放。

验证步骤：

1. UE 中选中该 BP Actor。
2. 执行导出。
3. 检查 `session.json`：
   - `components` 数量正确；
   - `assets` 数量等于唯一资产数；
   - 腿部资产只出现一次；
   - 每个组件都有 `actor_local_transform`；
   - 中间 `SceneComponent` 偏移已被折进 `actor_local_transform`。
4. Blender 导入后检查：
   - 顶级会话 collection 创建正确；
   - `BP_<ActorLabel>_ROOT` 在 Blender 世界原点；
   - 可见组件通过 wrapper 正确摆放；
   - 4 个腿组件是 4 组可见对象，但共享同一份 mesh data；
   - `_UBIO_INTERNAL` 默认隐藏，且存在 canonical 根。
5. 在 Blender 的任意一个腿组件实例上修改 mesh 几何。
6. 确认 4 个腿组件同步变化。
7. Blender 导出后检查：
   - 每个资产目录都有自己的 `edited.fbx`；
   - 导出源来自 canonical 根，而不是可见组件实例。
8. UE reimport 后检查：
   - 腿部资产只 reimport 一次；
   - 4 个腿组件全部更新；
   - 座面资产独立更新。

### 9.2 多对象资产用例

准备一个导入 Blender 后会变成多个对象的 StaticMesh 资产，验证：

1. canonical 根下是否稳定挂住全部对象。
2. 组件 wrapper 下是否生成一组对应可见对象。
3. 修改某个可见实例的 mesh data 后，canonical 是否同步反映。
4. 只导出 canonical 根时，是否能生成正确 `edited.fbx`。

### 9.3 兼容旧 session 用例

准备一个旧版 session：

1. 只有 `root_transform`，没有 `source_actor_world_transform`。
2. 只有 `source_object_names`，没有 `canonical_object_names`。
3. 没有 `actor_local_transform`。

预期：

1. Blender 能导入，但日志明确记录兼容路径。
2. 若回写新 session，则字段应规范化到新命名。
3. 无法无歧义恢复的旧数据，应明确报错，不要静默猜测。

### 9.4 关键失败用例

1. BP Actor 下没有有效 `StaticMeshComponent`
   - 预期：UE 直接报错，不生成 session。
2. 某组件无法计算 `actor_local_transform`
   - 预期：UE 导出失败，并指出具体 `component_key`。
3. 某资产 `source.fbx` 导出失败
   - 预期：session 标记失败，日志写明 `asset_key`。
4. Blender 导入时某个 `source.fbx` 丢失
   - 预期：导入失败并指出具体 `asset_key` 和路径。
5. Blender 导入后某资产 canonical 根为空
   - 预期：导出该资产失败，并写明 `asset_key`。
6. UE reimport 时某原始资产路径失效
   - 预期：该资产 `reimport_status = FAILED`，其他资产继续处理。
7. 用户只改了可见实例的 object-level 子对象 transform
   - 预期：导出前给出警告，说明该修改不会进入资产导出结果。

## 10. 风险与控制

### 10.1 主要风险

1. UE Python 对 Blueprint 组件层级、矩阵换算和 transform 烘焙细节仍可能有坑。
2. 某些 StaticMesh 资产导入 Blender 后可能不是单对象，而是多个对象组。
3. linked data 只能共享 mesh data，不能共享 object transform；如果用户误把可见实例当 canonical 来改 object transform，会产生认知偏差。
4. 新旧 schema 同 session type 并存，兼容逻辑如果写得含糊，后续会很难排错。

### 10.2 控制手段

1. 先用带中间 `SceneComponent` 的最小样例验证 `actor_local_transform` 是否正确。
2. 先验证 root 固定在世界原点时，组件布局是否符合预期。
3. 日志按 `asset_key` 和 `component_key` 记录，保证 agent 可定位失败点。
4. 导入后把 canonical 根与 canonical 对象组名单显式写回 session 与日志。
5. 对兼容旧 schema 的 fallback 必须有日志，不允许 silent fallback。
6. 对“可见实例 transform 不会回传”必须在 UI 文案或日志里明确提示。

## 11. 建议的最终落地范围

如果以“尽快可用”为目标，修订后的 V1 建议做到：

1. 支持单个 BP Actor。
2. 支持多个 `StaticMeshComponent`。
3. 支持按唯一资产去重导出。
4. 支持 UE 侧生成 `actor_local_transform`。
5. 支持 Blender 中“单可见会话组 + 隐藏 canonical 资产组”导入。
6. 支持 root 固定在世界原点。
7. 支持 wrapper empty 承载组件级布局。
8. 支持 linked data 方式的重复资产实例。
9. 支持逐资产导出 `edited.fbx`。
10. 支持 UE 逐资产 reimport 与逐资产日志。
11. 支持旧 session 字段的最小兼容加载。

这比旧版 `Sources/Layout + collection instance` 更贴近当前项目需求，也能把 transform、canonical 与多对象资产这三个硬问题先收住。

## 12. 与现有文档的关系

本方案是对以下文档的扩展与修订：

- `docs/plans/2026-03-20-static-mesh-roundtrip-plan.md`

关系如下：

1. `2026-03-20` 文档解决“单 StaticMesh 资产往返”。
2. 本文解决“一个 BP Actor 内多个 StaticMeshComponent 的局部装配往返”。
3. 2026-05-07 修订版进一步明确：
   - Blender 侧不再使用 `collection instance` 作为主表示；
   - 默认布局恢复基于 `actor_local_transform`，而不是直接依赖 `relative_transform`；
   - canonical 导出源与可见组件实例彻底解耦；
   - 多对象资产通过 canonical 根与 wrapper empty 获得稳定锚点。