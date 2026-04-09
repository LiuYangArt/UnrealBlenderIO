# Postmortem: UE 5.5 StaticMesh 导出选择接口误用

## 结论

这次问题的根因不是 `StaticMeshExporterFBX` 本身，而是 **UE 5.5 里“资产选择”和“关卡 Actor 选择”属于不同 Python API 类**，脚本把关卡 Actor 选择错误地写成了：

```python
selected_actors = editor_util.get_selected_level_actors()
```

在 UE 5.5 中，`EditorUtilityLibrary` 负责 `Content Browser` 资产相关选择，而关卡里已选中的 Actor 应该通过：

```python
actor_subsys.get_selected_level_actors()
```

来读取。

## 现象

用户在以下两种场景下执行 `ubio_export_selected_static_mesh_to_blender()`：

1. `Content Browser` 中选中 `StaticMesh` 资产
2. 关卡中选中 `StaticMeshActor` 或带 `StaticMeshComponent` 的 BP Actor

然后脚本没有导出出 `source.fbx`，或者直接报：

```python
AttributeError: type object 'EditorUtilityLibrary' has no attribute 'get_selected_level_actors'
```

## 根因

### 1. 错把关卡 Actor 选择接口挂到了 `EditorUtilityLibrary`

错误代码：

```python
selected_actors = editor_util.get_selected_level_actors()
```

这在 UE 5.5 官方 Python 文档中不存在，所以运行时直接抛 `AttributeError`。

### 2. 原始脚本的可观测性太弱

即使不是直接抛属性错误，原始导出链路也缺少足够的过程日志，导致用户看到的是“没有导出东西”，但无法快速判断：

1. 是否真的进入了导出函数
2. 读到的是关卡选中对象还是资产选中对象
3. 解析出的对象是否带 `StaticMeshComponent`
4. 导出器是否返回成功
5. FBX 是否真正写到了磁盘

这使问题从一个很快能定位的 API 兼容错误，放大成了黑盒故障。

## 修复

### 1. 按 UE 5.5 文档拆分两条选择链路

- 关卡 Actor 选择：`EditorActorSubsystem.get_selected_level_actors()`
- 资产选择：`EditorUtilityLibrary.get_selected_assets()`

并统一在 `get_selected_static_mesh_source()` 中兼容：

1. 关卡中的 `StaticMeshActor`
2. 带 `StaticMeshComponent` 的 BP Actor
3. `Content Browser` 中单选的 `StaticMesh` 资产

### 2. 给 StaticMesh roundtrip 增加统一日志前缀

新增：

```python
STATIC_MESH_LOG_PREFIX = "[UBIO StaticMesh]"
```

并在关键边界打日志：

1. 函数开始执行
2. 当前关卡选中 Actor 数量
3. 当前资产选中数量
4. 最终解析到的 `StaticMesh`
5. 目标 session 目录
6. `StaticMeshExporterFBX` 返回值
7. `AssetExportTask.errors`
8. FBX 是否真实落盘

### 3. 只在导出成功后写入 session

避免“有 `session.json` 但没有 `source.fbx`”这种半成功状态污染 Blender 侧导入。

## 经验

### 1. 先查官方文档，不要凭旧版本 API 记忆写 UE Python

这次直接暴露出一个常见问题：UE Python API 在不同版本之间有“类归属变化”或“常用接口不在直觉里的类上”的情况。  
以后凡是涉及以下能力，必须先对当前 UE 版本文档：

1. 选择集读取
2. 导入导出任务
3. Editor Subsystem
4. Editor Utility Library

### 2. 编辑器自动化脚本必须优先补可观测性

如果一条链路跨越：

1. UE 选择集
2. 资产解析
3. 导出任务
4. 本地文件系统
5. Blender 导入

那就不能接受“失败了但没有关键状态日志”。  
日志不是调试阶段临时加的工具，而是这类工作流功能的一部分。

### 3. “能跑”不等于“可诊断”

这次真正拖慢定位的不是代码量，而是失败时缺少边界信息。  
以后新增类似工作流功能时，第一版就要同时交付：

1. 主功能
2. 最小诊断日志
3. 明确的失败提示

## 参考

- [UE 5.5 EditorUtilityLibrary](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/EditorUtilityLibrary?application_version=5.5)
- [UE 5.5 EditorActorSubsystem](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/EditorActorSubsystem?application_version=5.5)
- [UE 5.5 StaticMeshExporterFBX](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/StaticMeshExporterFBX?application_version=5.5)
- [UE 5.5 AssetExportTask](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/AssetExportTask?application_version=5.5)
