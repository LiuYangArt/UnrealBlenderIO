# Postmortem: Blender 隐藏集合导出空 FBX

## 症状

蓝图 StaticMesh 往返流程在 Blender 导出后生成 4060 字节的合法 FBX 容器，但文件不含 Mesh；UE 重导入后资产为空。

## 根因

canonical 对象位于隐藏的 `_UBIO_INTERNAL` 集合。代码调用 `select_set(True)` 后使用 `use_selection=True`，但 Blender FBX 导出器读取 `context.selected_objects`。隐藏集合中的对象不会进入该上下文集合，因此导出器收到空对象列表，仍返回成功并写出空 FBX。

## 修复

调用 FBX 导出器时通过 `context.temp_override` 显式提供 `active_object`、`selected_objects` 和 `selected_editable_objects`，不改变内部集合的隐藏设计。

## 回归验证

Blender 5.1.2 最小复现中：

- 修复前：隐藏集合导出文件为 4060 字节，无 Mesh。
- 修复后：同一隐藏对象导出文件为 11116 字节，重新导入后包含 1 个 Mesh 和 1 个三角面。

未来排查入口：检查 `logs/export_blender.json`、`edited.fbx` 文件大小，并用 Blender 后台重新导入确认 Mesh 数量。
