# Notes: StaticMesh 往返编辑方案调研

## 仓库现状

- 现有功能是“关卡 Actor 场景导入导出”，不是“静态网格资产内容往返编辑”。
- UE 侧当前使用 `LevelExporterFBX` 导出整关卡 FBX。
- Blender 回传 UE 当前只通过 JSON 同步 Actor 增删和 Transform。
- 现有文件交换目录是 `C:\\Temp\\UBIO\\`。

## 已确认结论

- 用户已确认采用方案 A：直接覆盖原始 StaticMesh 资产。
- 用户要求先写详细计划文档，再创建对应 issue。
- 仓库没有 issue 模板，可以直接用 Markdown 正文创建 GitHub issue。
- `gh` 已安装且当前账号已登录，可直接创建远程 issue。
- GitHub issue 已创建成功：`https://github.com/LiuYangArt/UnrealBlenderIO/issues/1`

## 计划文档应覆盖的重点

- V1 功能边界
- 会话目录与 JSON 数据结构
- UE 5.5 侧导出、导入、重导入链路
- Blender 5.0 侧导入、编辑、回传链路
- UI 入口与按钮命名
- 风险、验收标准、手动测试步骤

## 关键实现判断

- V1 的“一键”建议定义为：
  - UE 侧一个按钮：发送选中的 StaticMeshActor 到 Blender
  - Blender 侧一个按钮：将编辑结果发送回 Unreal
- 第一版不做后台监听、端口通信、自动唤起另一端。
- 为避免多个会话互相覆盖，建议使用独立 session 目录。
