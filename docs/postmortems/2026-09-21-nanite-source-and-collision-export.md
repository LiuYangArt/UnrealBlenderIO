# Issue #3：Nanite 源网格与碰撞导出互斥

## 症状与根因

`BP_BLD01WallE_SM` 对应的 `SM_BLD01WallE` 经 UBIO 导入 Blender 后只有 149 顶点、313 面；手动 FBX 导出有 2413 顶点、4712 面。

2026-08-31 的提交 `701f813` 为碰撞往返把 `collision=False` 改为 `True`，同时仍保留 `export_source_mesh=True`。当前 UE 5.7.4 的 `FbxMainExport.cpp:5469` 要求源网格导出必须同时关闭 LOD 和 Collision，否则改用渲染数据。手动窗口关闭时会自动纠正互斥选项，自动导出不会。

墙体的 Nanite fallback 被明显简化，因而暴露问题；`SM_BeamKitFrameA` 的源和 fallback 同为 3216 三角形，外观不容易发现差异。实际加载脚本与仓库逻辑相同，不是旧版脚本或 Blender 简化导致。

## 修复约定

- `source.fbx`：只导出源几何，明确 `export_source_mesh=True`、`level_of_detail=False`、`collision=False`。
- `collision.fbx`：独立导出碰撞；UE 原生导出器会附带渲染载体，Blender 只保留 UCX/UBX/UCP/USP 对象并清理载体及其无引用网格、材质。载体不会成为可编辑源对象。
- 两份 FBX 使用相同导入坐标与单位选项，碰撞继续关联原始几何。
- Blender → UE 继续输出包含编辑后源网格和碰撞的 `edited.fbx`；不改变现有碰撞关联和 BP 共享实例流程。
- 普通 StaticMesh 会话格式升为 `2.0`，BP 格式升为 `3.0`。旧会话直接拒绝并提示重新从 UE 导出，不迁移或猜测几何来源。
- 找不到源几何时直接失败，不静默输出 fallback。
- Nanite 导出检查依赖 UE 自带的 **Geometry Script** 插件，用其公开接口确认有效 HiRes 源数据；有效 HiRes 优先，否则使用源 LOD0。当前 Paralogue 已有此接口，无需改变工程设置。其他工程应启用 Geometry Script 与 Python Editor Script Plugin。
- UE 日志的 `Geometry source` 标识 `NANITE_HI_RES` 或 `SOURCE_LOD0`；后者包含源 LOD0 顶点数和三角形数，避免把 LOD0 计数冒充独立 HiRes 的计数。

## 本次验证

环境：当前打开的 Paralogue / UE 5.7.4；Blender 5.2.1 LTS 后台模式。

1. `python -B -m unittest discover -s tests -p test_source_mesh_export.py -v`
   - 五项通过：互斥导出选项、有效 HiRes 优先且不依赖 LOD0、无源数据拒绝、关闭 Nanite 不选 HiRes、缺失 Nanite 检查能力时拒绝输出。
2. 在当前 UE Python 远程执行 `tests/validate_source_mesh_ue.py`。
   - 真实墙体、Beam、无碰撞 Decal 的源几何及碰撞独立导出成功。
   - 墙体源文件保持 2413 顶点、4712 三角形；fallback 为 322 三角形。
   - 空源 StaticMesh 在创建 FBX 前报错。
   - 为避免改变用户正在编辑的关卡，BP 验证使用真实 Blueprint 类与真实 Mesh 资产，构造单组件和四组件夹具；四组件包含共享墙体、独立 Beam、无碰撞 Decal 和负/非均匀缩放，不在当前关卡生成 Actor。
3. `blender.exe --background --factory-startup --python-exit-code 1 --python tests/validate_source_mesh_blender.py`
   - 七组通过：StaticMesh 墙体/Beam/Decal、单组件 BP、共享多资产 BP、StaticMesh/BP 旧会话与缺失碰撞检查。
   - 完整墙体为 2413 顶点、4712 面，另有 75 顶点、126 面碰撞。
   - fallback 的 149 顶点网格未留在对象或网格数据中。
   - 共享网格实例、碰撞目标、负/非均匀缩放保持；关闭“导入碰撞”时不读碰撞文件。
   - 缺失碰撞文件或旧格式在清理已有场景之前失败。
   - 各资产重新导出的 `edited.fbx` 保持源面数和碰撞面数；没有把碰撞载体导回去。
   - 中文/英文提示随 Blender 语言切换，JSON key 与占位符一致。
4. 已将 UE 脚本同步到当前项目 `Content/Python/UnrealBlenderIO.py`，SHA256 与仓库相同，并用 Python 热重载；实际运行该模块的源/碰撞导出成功。
5. Blender 的 `extensions/vscode_development` 是指向 `F:/CodeProjects/BlenderAddons` 的目录联接，直接使用当前仓库代码。

本次没有在用户原资产上执行重导入。验证覆盖 UE → Blender → 编辑后 FBX；UE 重导入逻辑未改动。独立 HiRes 选择有自动化分支测试，当前三份真实资产没有独立 HiRes 数据，未声称完成真实 HiRes 资产回归。

UE 导出检查前后 dirty content packages 均为空，用户选择保持不变。所有本任务启动的 Blender 验证进程退出；Python 远程连接关闭。没有使用 Computer Use。

## 证据与后续排查入口

- `artifacts/nanite-source/ue_export.json`：源和渲染计数、场景未修改证明、源缺失拒绝。
- `artifacts/nanite-source/ue_export_response.json`：实际 UE 命令结果与日志。
- `artifacts/nanite-source/blender_validation.json`：七组检查、源/碰撞数量、返回 FBX 列表。
- `artifacts/nanite-source/blender_validation.log`：完整 Blender 输出。
- `tests/test_source_mesh_export.py`：不需要 UE 或 Blender 的导出回归。
- `tests/validate_source_mesh_ue.py` / `tests/validate_source_mesh_blender.py`：当前项目真实资产验证。

碰撞文件的废弃渲染载体仍可能触发 Blender 原有的 FBX layer 数据不足日志；最终碰撞和源对象均通过数量及关联检查。排查时应分别检查 source、collision 文件以及 session 内对应路径，不能仅凭 FBX 容器导出成功判断源数据正确。
