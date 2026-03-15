# UnrealBlenderIO 本地化实施计划（中英双语）

更新时间：2026-03-15  
适用范围：`UnrealBlenderIO` Blender 插件（Blender 5.0 开发环境）

## 0. 直接结论

本项目建议采用“**双 JSON 词条文件 + Blender 原生翻译注册**”方案：

1. 中英文词条分别存放在独立 JSON 文件（`en_US.json` / `zh_HANS.json`）。
2. 插件注册时把 JSON 转换为 Blender 可识别的翻译表（`bpy.app.translations.register`）。
3. 代码中统一使用“稳定 key -> 英文 msgid -> 当前语言文案”的路径，消除中英混杂。
4. Blender 语言切换后，插件 UI 和操作器描述自动切换为对应语言。

这个方案能满足你提出的两个关键点：
- 跟随 Blender 语言自动切换。
- 中英文分离到各自 JSON 文件中维护。

## 1. 现状与问题

当前仓库内“面向用户的可见文本”散落在多个文件，且中英混用：

- `UI.py`
  - `StringProperty` 的 `name/description` 混杂
  - 面板标题与按钮文本存在英文硬编码
- `Tools.py`
  - `bl_label` 多为英文，`bl_description` 与 `self.report` 多为中文
  - 模态绘制提示文案（`blf.draw`）为中文
- `UnrealBlenderIO.py`
  - `bl_label/bl_description` 多为英文
  - `self.report` 与 `print` 消息多数中文
- `Preference.py`
  - 设置页说明文案与报错提示多为中文
  - 按钮标题与描述为英文

目前无 i18n 基础设施：
- 无 `i18n` 模块
- 无语言词条文件
- 无 Blender 翻译注册逻辑

## 2. 目标与边界

### 2.1 目标（必须达成）

1. 插件在 Blender 语言为中文时显示中文；为英文时显示英文。
2. 所有用户可见文案（按钮、面板、属性说明、提示、报错）进入 JSON 管理。
3. 中英文词条文件独立维护，key 一致、值不同。
4. 消除“代码里直接写中文/英文句子”的做法，改为统一 key 引用。

### 2.2 非目标（本轮不做）

1. 不扩展第三语言。
2. 不改 UE 侧脚本（`UnrealAsset/Python/UnrealBlenderIO.py`）的日志本地化。
3. 不改业务逻辑（导入导出流程、数据结构）本身。

## 3. 方案设计（Implementation Plan）

### 3.1 目录与文件规划

新增目录：

`i18n/`

新增文件：

1. `i18n/en_US.json`
2. `i18n/zh_HANS.json`
3. `i18n.py`（加载词条、校验词条、提供翻译接口、注册 Blender 翻译）

计划新增结构示例：

```text
UnrealBlenderIO/
├─ i18n/
│  ├─ en_US.json
│  └─ zh_HANS.json
├─ i18n.py
├─ __init__.py
├─ UI.py
├─ Tools.py
├─ UnrealBlenderIO.py
└─ Preference.py
```

### 3.2 词条模型设计

建议使用“扁平 key-value”结构，key 采用模块分组命名：

```json
{
  "panel.main_title": "Unreal Blender IO",
  "panel.tools_title": "UBIO Tools",
  "op.import_latest.label": "Import Latest Unreal Scene",
  "op.import_latest.desc": "Import latest FBX and JSON exported from Unreal Engine",
  "report.import.success": "Successfully imported Unreal scene: {filename}"
}
```

对应中文文件：

```json
{
  "panel.main_title": "Unreal Blender IO",
  "panel.tools_title": "UBIO 工具",
  "op.import_latest.label": "导入最新 Unreal 场景",
  "op.import_latest.desc": "导入 Unreal 导出的最新 FBX 与 JSON",
  "report.import.success": "已成功导入 Unreal 场景: {filename}"
}
```

命名约定：

1. UI 元素：`panel.*` / `prop.*` / `pref.*`
2. 操作器：`op.<operator>.(label|desc)`
3. 运行时提示：`report.<domain>.<type>`
4. 模态提示：`hint.<domain>.*`

### 3.3 语言识别策略

语言来源：`bpy.context.preferences.view.language`

判定规则：

1. `zh_HANS` / `zh_CN` -> 使用 `zh_HANS.json`
2. `en_US` 或 Blender 处于英文界面 -> 使用 `en_US.json`
3. 其他语言按英文展示（本项目仅承诺中英）

### 3.4 Blender 集成方式

核心做法：

1. `i18n.py` 启动时读取 `en_US.json` 与 `zh_HANS.json`。
2. 构建 Blender 翻译字典并在 `register()` 时注册：
   - `bpy.app.translations.register(...)`
3. 在 `unregister()` 中对应卸载：
   - `bpy.app.translations.unregister(...)`
4. 对 `self.report` / `blf.draw` 这类运行时文本，统一走 `tr(key, **kwargs)`。

这样能保证：

1. `bl_label` / `bl_description` 这类 Blender UI 固有文本可随语言切换自动翻译。
2. 运行时消息同样受当前语言控制。

### 3.5 改造范围（按文件）

1. `__init__.py`
   - 注册/卸载翻译表
2. `UI.py`
   - `StringProperty` 的 `name/description`
   - 面板标题、分组标题、按钮文字
3. `Tools.py`
   - 所有 `bl_label/bl_description`
   - 所有 `self.report`
   - `blf.draw` 的操作提示
4. `UnrealBlenderIO.py`
   - 所有 `bl_label/bl_description`
   - 所有 `self.report`
   - 必要的 `print`（若用户可见）改为统一提示
5. `Preference.py`
   - 偏好页文案、按钮文本、说明文本、报错提示

## 4. 任务拆解（Task List）

### Phase 1：建立 i18n 基础设施

- [x] 新建 `i18n/` 目录与两份语言 JSON 文件
- [x] 新建 `i18n.py`，实现：
  - JSON 加载
  - key 完整性校验（两份语言 key 必须一致）
  - `tr(key, **kwargs)` 接口
  - Blender 翻译注册与卸载接口
- [x] 在 `__init__.py` 接入注册/卸载

### Phase 2：统一替换可见文案

- [x] `UI.py` 全量替换为 key 引用
- [x] `Tools.py` 全量替换为 key 引用
- [x] `UnrealBlenderIO.py` 全量替换为 key 引用
- [x] `Preference.py` 全量替换为 key 引用

### Phase 3：校验与修正

- [x] 运行词条一致性检查（缺 key 直接报错）
- [x] 检查格式化占位符一致性（如 `{filename}`）
- [x] 检查拼写与术语统一（Unreal / Blender / Level Asset 等）

### Phase 4：验收与文档

- [ ] 完成中英文切换手测
- [x] 在 `README.md` 补充“语言跟随 Blender 设置”的说明
- [x] 记录后续新增文案的开发规范（新增文案必须先进 JSON）

## 5. 验收标准

以下全部满足才算完成：

1. Blender 切换中文后，插件面板、按钮、提示、报错全部中文。
2. Blender 切换英文后，插件面板、按钮、提示、报错全部英文。
3. 仓库内业务代码不再新增硬编码中英文文案（除词条 key 与极少内部日志）。
4. 两份 JSON 的 key 集与占位符一致。
5. 导入/导出/工具操作主流程在双语下行为一致，无功能回归。

## 6. 手动测试步骤（给使用者）

### 6.1 中文验证

1. 打开 Blender。
2. 将界面语言切换为简体中文（`Edit > Preferences > Interface > Language`）。
3. 重新启用或重载本插件。
4. 打开右侧 N 面板 `UBIO`。
5. 依次点击：
   - 导入最新场景
   - 导入指定场景
   - 导出 JSON
   - 清理临时文件
6. 预期结果：
   - 面板标题、按钮文本、提示消息均为中文
   - 无英文残留（专业名词除外，如 JSON / FBX）

### 6.2 英文验证

1. 将 Blender 语言切换为英文（English）。
2. 重新启用或重载插件。
3. 重复 6.1 的操作。
4. 预期结果：
   - 所有可见文案均为英文
   - 无中文残留

### 6.3 一致性验证

1. 分别在中文与英文界面执行一次“导入 -> 编辑 -> 导出”流程。
2. 预期结果：
   - 功能结果完全一致
   - 只有显示文本变化，业务行为不变

## 7. 风险与控制

1. 风险：漏替换导致残留硬编码文案  
   控制：按文件清单逐项替换，并用检索命令复查（`bl_label`、`bl_description`、`self.report`、`label(text=...)`）。

2. 风险：两份 JSON key 不一致，运行时出现空文案  
   控制：插件注册时做强校验，不通过则阻止注册并输出明确错误。

3. 风险：占位符不一致导致格式化异常  
   控制：增加占位符对齐检查（例如 `{filename}` 在两边必须同名）。

## 8. 里程碑建议

1. 里程碑 M1（0.5 天）：完成 i18n 基础设施与最小可用词条。
2. 里程碑 M2（0.5 天）：完成四个 Blender 侧文件的文案替换。
3. 里程碑 M3（0.5 天）：完成双语手测、修正与文档补充。

总工期建议：1.5 天（单人，不含新功能开发）。

## 9. Thought（关键思路）

1. 这次本地化目标不是“翻译几句文案”，而是建立可持续机制：后续新增文案不会再次回到中英混杂。
2. Blender 场景下，`bl_label/bl_description` 和运行时 `report` 是两类不同文本入口，必须分别覆盖。
3. “中英文 JSON 分离”与“跟随 Blender 自动切换”并不冲突，关键在于把 JSON 与 Blender 翻译注册流程打通。
4. 本轮坚持最小范围改造：只动 Blender 插件侧可见文本，不改业务流程，不引入额外依赖。
