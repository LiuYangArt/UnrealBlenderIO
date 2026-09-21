# UE 工程端

这里包含用于 UE 工程的 Python 脚本和 Editor Widget 工具。

## 安装与更新

- 启用 Python Editor Script Plugin。导出 Nanite 资产还需启用 UE 自带的 Geometry Script，用于确认源几何存在。
- 将 `Python/UnrealBlenderIO.py` 更新到工程的 `Content/Python/UnrealBlenderIO.py`；已打开的编辑器需重新加载该 Python 模块或重启编辑器。
- UE 脚本与 Blender 插件需要一起更新。旧网格会话无法继续导入，请从 UE 重新导出。

## 网格与碰撞导出

- `source.fbx` 保存源网格，`collision.fbx` 单独保存碰撞导出结果。
- Blender 只从第二份文件读取碰撞；UE 随附的渲染载体会被丢弃。
- 如果无法确认源几何存在，导出会报错，不使用 Nanite fallback 替代。
- 返回 UE 时仍使用包含编辑后网格与碰撞的 `edited.fbx`。

根因、验证范围与证据见 [Nanite 导出排查记录](../docs/postmortems/2026-09-21-nanite-source-and-collision-export.md)。