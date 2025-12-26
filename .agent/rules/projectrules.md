---
trigger: always_on
---

# 项目说明
本项目用于在blender中编辑unreal engine中传递过来的场景，并使用json方式把编辑结果返回unreal。
\UnrealAsset\ 下是UE中使用的python脚本和EditorWidggt


# Blender Python 插件开发规则

## 任务范围与规划 (Define Scope & Plan) 
-   **制定清晰的计划**: 编写清晰的计划，详细说明将涉及哪些Blender功能、Python模块或组件，并解释其原因。在完成并充分推理之前，不要开始实施。
-   **检查可复用性**: 在实施前，检查项目内部的 `.utils.py` 文件中是否有可复用的功能。优先使用现有功能，避免重复造轮子。

## 代码实现 (Implementation)

### 环境与API交互
-   **Blender版本**: 项目基于Blender 5.0 版本开发。
-   **API文档检索**: 使用 `context7 mcp` 检索Blender API文档，以确保对API的准确理解和正确使用。

### 结构与导入
-   **`import bpy`**: 必须在项目所有Python文件的文件头添加 `import bpy`。
-   **统一导入**: 所有的 `import` 语句都必须放置在文件头部，避免在函数中间进行导入。
-   **模块化设计**: 将通用的、可复用的功能抽象为独立的函数，并将其组织到 `.utils.py` 文件中。每段代码或每个函数体不应过长。

### 代码规范与可读性
-   **变量命名**: 变量名应具有表达性且易于阅读，避免过度缩写。例如，使用 `obj` 而不是 `o` 来表示对象（objects）。
-   **操作符 (Operator) 逻辑**:
    -   所有自定义的Blender Operator在 `execute` 方法执行主要逻辑之前，应先使用 `invoke` 方法检查上下文（context）是否合适。
    -   此项目使用 `auto_load` 机制，因此**无需**单独注册Operator。
-   **注释规范**:
    -   **功能性函数**: 对于所有非Blender Operator固定方法（如 `execute`, `invoke` 等）的功能性函数，必须添加**块注释 (block comment)** 来标记其用途，并详细说明所有参数的意义。
    -   **语言**: 注释内容使用中文书写，但涉及到的专业名词、API名称或代码专有名词（例如 `Mesh`, `Bounding Box`, `Vertex Group`）请使用英文原文。

