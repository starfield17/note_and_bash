# AI 编码 + 人类协作架构（轻量版 V1）

这是"AI编码+人类协作"架构规范的**简化**版本，适用于：
- **小型项目**（1-5名开发者）
- **简单功能集**（CLI工具/小型服务/实用程序）
- 现有仓库的**渐进式重构**

它保留了关键优势：
- **调试路径短**
- **无混乱的依赖关系**
- **对AI友好的任务切片**
同时减少了繁琐的仪式感（除非需要，否则不使用繁重的上下文映射/ADR堆栈）。

---

## 1) 核心理念图解

对于小型项目，通常只需要**3层**（加上可选的`infra/`）：

**入口 → 编排 → 核心**

- **入口（Entry）**: CLI / GUI / HTTP 处理器（IO边界）
- **编排（Orchestration）**: 描述*步骤和流程*的"管道/用例"代码
- **核心（Core）**: 纯粹的、可测试的逻辑（原子/分子）+ 数据类型

可选：
- **基础设施（Infra）**: 文件系统、网络、数据库、GPU、外部服务适配器

---

## 2) 最小规则（轻量但可执行）

### R1. 单向导入
在你的包/模块内部，依赖必须只流向：

`entry → orchestration → core`
以及 `orchestration → infra`（通过接口或薄适配器）

**禁止**
- `core` 导入 `entry` / `orchestration` / `infra`
- `entry` 直接导入 `core`（必须通过编排层以确保流程一致）
- 入口变体之间的隐藏交叉调用（例如，GUI调用CLI内部实现）

### R2. 核心层 = 原子 & 分子
将核心层分为两个子类型：

- **原子（Atoms）**: 小型独立函数/类（指导原则50-120行代码），无IO，不调用其他原子。
- **分子（Molecules）（可选）**: 组合原子，仍然无IO。

在小型项目中，你可以从只有`atoms/`开始，如果需要再添加`molecules/`。

### R3. 流程显式化（管道表可选）
你不需要完整的工作流表引擎。对于小型项目：
- 一个**单独的`pipeline.py`**，包含步骤函数就足够了。
- 如果流程变得复杂，稍后可以添加一个小的`workflow.yaml`。

### R4. 每个新原子都有单元测试
最低要求：
- 每个新原子 = 至少一个正常情况测试 + 一个边界情况测试。

### R5. "人类拥有"的文件很少但严格
人类必须拥有：
- `README.md` 使用契约（CLI标志/GUI行为/示例）
- 公共API表面（`__init__.py` 导出 / CLI命令）
- 核心数据类型（`types.py`）和不变性

AI可以生成：
- 原子/分子的实现
- 编排层代码
- 大多数单元测试（人类进行审查）

---

## 3) 推荐的目录布局（小型项目）

示例包名：`mytool`

```
mytool/
├─ README.md
├─ pyproject.toml
├─ src/
│  └─ mytool/
│     ├─ __init__.py              # 公共导出（人类拥有）
│     ├─ __main__.py              # 入口路由器（CLI/GUI后备）
│     ├─ entry/                   # IO边界
│     │  ├─ cli.py
│     │  └─ gui.py                # 可选
│     ├─ orchestration/           # 显式流程
│     │  ├─ pipeline.py
│     │  └─ services.py           # 可选：更高级别的辅助函数
│     ├─ core/                    # 纯逻辑
│     │  ├─ types.py
│     │  ├─ atoms/
│     │  │  ├─ matching.py
│     │  │  ├─ bg_remove.py
│     │  │  └─ alignment.py
│     │  └─ molecules/            # 可选
│     │     └─ process_job.py
│     └─ infra/                   # 可选：副作用适配器
│        ├─ fs.py
│        └─ parallel.py
└─ tests/
   ├─ unit/
   │  ├─ test_matching.py
   │  ├─ test_bg_remove.py
   │  └─ test_alignment.py
   └─ integration/
      └─ test_pipeline_smoke.py
```

### 命名约定（轻量版）
- 原子：纯函数；避免使用"Manager/Helper/Utils"。
- 编排：使用`pipeline`、`usecase`，或基于动词的模块（`process.py`）。
- 基础设施：外部世界的适配器（文件系统、多进程、HTTP、GPU）。

---

## 4) 如何将此应用到现有的"README级别"工具仓库

典型的小型工具通常已有：
- CLI命令
- GUI入口
- 核心处理管道
- 一些算法模块

这可以整齐地映射到轻量版的各层：

- `__main__.py` → **入口路由器**
- `cli.py`、`gui.py` → **入口**
- `pipeline.py` → **编排**
- 算法模块（`match.py`、`imageops.py`）→ **核心原子/分子**
- 数据结构（`cgtypes.py`）→ **核心类型**
- 多进程实现 → **基础设施**（或编排层辅助函数）

这种精确的"入口 + 管道 + 核心模块 + 类型 + cli/gui"风格是小型项目的良好目标。
（你的README已经描述了这种内部结构和模块拆分，这正是Lite V1要标准化的。）

---

## 5) "工作流表" — 何时添加

开始时不需要它。

仅在遇到以下任何一种情况时才添加`workflow.table.yaml`：
- `pipeline.py` 内部有太多的`if/else`分支
- 复杂的回滚/补偿逻辑
- 需要在多个步骤中实现"干运行"、"交互式确认"、"恢复"等功能

轻量版表格格式（可选）：

```yaml
name: ProcessImages
steps:
  - id: scan
    action: scan_inputs
  - id: match
    action: match_pairs
  - id: remove_bg
    action: remove_background
  - id: align
    action: align_images
  - id: compose
    action: compose_and_save
```

---

## 6) AI辅助实现的护栏

当要求AI添加功能时，始终包含：
1. **目标文件路径**
2. **层约束**
   - "这是一个原子。不得导入其他原子。无IO。"
   - "这是编排。可以调用原子。此处不进行CLI解析。"
3. **输入/输出契约**
4. **测试要求**

示例指令片段：

> 实现 `core/atoms/alignment.py::align_fast(base, diff, params)`
> 约束：原子函数；无文件系统IO；不导入其他原子；确定性。
> 在 `tests/unit/test_alignment.py` 中添加单元测试。

---

## 7) 重构步骤（小型仓库的1-2天计划）

1. **冻结公共行为**（README + CLI参数 + GUI行为）
2. 识别模块并标记它们：
   - entry / orchestration / core / infra
3. 将代码移动到轻量版布局中（首先进行最少的移动）
4. 为重构期间接触到的原子添加单元测试
5. 添加一个简单的导入规则检查（可选）：
   - 如果`core`导入`entry`/`orchestration`，则CI失败

---

## 8) 完成定义（轻量版）

一个功能PR完成时：
- [ ] 入口层只解析IO并调用编排层
- [ ] 编排层读起来像显式的步骤流
- [ ] 核心原子有测试覆盖
- [ ] 没有禁止的导入（核心层保持纯粹）

---

## 版本
- Lite V1 有意保持小巧和实用。
- 升级到"完整版 V1"的路径：
  - 如果项目增长，添加有界上下文
  - 为复杂流程添加工作流表
  - 如果外部依赖增多，添加端口/适配器
