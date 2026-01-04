# AI 编码 + 人机协作架构规范 (V1)

> 目的：为规模化使用 **AI 辅助编程** 的团队提供一个 **可实操、可执行** 的架构与协作标准。
> 目标：**(1) 可预测的依赖图 (2) 快速故障定位 (3) 契约优先开发 (4) 可测试、可评审的变更**。

---

## 1. 设计目标

### 1.1 本架构优化方向
- **短的错误定位路径**：故障应指向 **小单元**（Atom/Use Case），而非冗长的隐式调用链。
- **构建上杜绝循环依赖**：强制 **单向依赖流**，禁止同层互相调用。
- **AI 友好的分解**：工作项被切割为 **契约化、可测试单元**；AI 主要在边界内填充实现。
- **人保有“语义所有权”**：领域边界、不变量和工作流由人定义；AI 实现细节。

### 1.2 非目标
- 这不是每个系统的“唯一真理架构”。V1 针对：
  - 后端服务 / API / 业务系统
  - 有多名贡献者的中大型代码库
- 若您构建的是小脚本或原型，可放宽部分规则。

---

## 2. 核心原则 (必须遵守)

### P0. 契约优先
所有跨层或跨上下文的交互必须由 **契约** 定义：
- API 契约（OpenAPI / gRPC proto / 接口定义）
- 数据契约（Schema, DTO）
- 领域契约（不变量、状态转换、领域事件）

### P1. 单向依赖
依赖方向 **严格** 如下：

**接口/契约 → 应用层（Use Cases）→ 领域层 → （Ports）→ 基础设施适配器**

在 “Atom/Molecule” 概念内部：
- **Atoms** 不依赖其他 Atoms。
- **Molecules** 不依赖其他 Molecules。
- 编排在 **Use Cases / 工作流表** 中发生。

### P2. 编排必须显式化
执行流必须可见：
- 在 Use Case 层使用 **工作流表 / 状态机**。
- 避免将流程逻辑埋在深层调用栈中。

### P3. 一切皆可单元测试
每个 Atom 和 Use Case 必须拥有：
- 单元测试（最低要求）
- 边界处的契约测试（若适用）

### P4. 所有权 + 治理
- 每个 Bounded Context 有 **一个负责人**。
- PR 变更范围受限制；架构 lint 防止意外边界违规。

---

## 3. 层级模型 (DDD + AI 友好型 4 层融合)

本标准结合：
- **DDD / 六边形架构**（Context, Domain, Ports & Adapters）
- 引用回答中的“4层”理念（Entry / Orchestrator / Molecules / Atoms）

### 3.1 层级与职责

#### L1 — Entry (接口层)
**包含内容**
- HTTP 控制器 / CLI 入口 / 消息消费者
- 请求验证（语法层面）、鉴权检查（可选）
- 传输 DTO ↔ 应用命令/查询的映射

**禁止内容**
- 业务规则
- 领域不变量
- 多步工作流

**允许的依赖**
- 仅依赖 `application` 层契约（commands/queries）和 `contracts` DTO

---

#### L2 — Orchestration (应用层 / Use Case 层)
**包含内容**
- Use cases（应用服务）
- 工作流表 / 状态机定义
- 协调者（类似调解员角色）：
  - **Commander**：执行工作流步骤
  - **Data Clerk**：组装上下文数据、缓存、关联 ID
  - **Diplomat**（ACL）：通过 ports 跨上下文请求；禁止直接导入

**禁止内容**
- 数据库/HTTP/MQ 客户端代码（放入基础设施适配器）
- 属于领域的重算法实现

**允许的依赖**
- `domain`（实体、值对象、领域服务、领域事件）
- `ports`（接口）
- `contracts`（DTO/架构）
- **不得** 直接依赖 `infrastructure` 实现

---

#### L3 — Molecules (领域组合单元)
此层可选，但当领域逻辑复杂时建议使用。

**定义**
- Molecule 是一个 **组合的领域操作**，它：
  - 在领域聚合边界内使用多个 Atoms
  - 仍是纯领域逻辑（无 I/O）

**规则**
- **Molecules 不能调用其他 Molecules**
- Molecules 可调用 Atoms、实体和值对象
- 所有副作用通过 ports 从 Use Cases 触发（而非在 Molecules 内部）

---

#### L4 — Atoms (小且独立的领域单元)
**定义**
- 小的、确定性的操作（~50–120 LOC 指导原则）
- 包含一个完整的微能力（验证、计算、映射、规则评估）
- 无 I/O，且不调用其他 Atoms

**规则**
- Atoms 应尽可能 **纯粹**（输入 → 输出）
- 任何外部依赖必须通过 **传入的接口** 表达（罕见；更推荐在应用层使用 ports）

---

## 4. 限界上下文 (DDD)

### 4.1 何为限界上下文
限界上下文是一个自包含的业务含义区域：
- 拥有其领域模型和不变量
- 通过 **ports/契约** 暴露能力
- 对外部依赖拥有防腐层（ACL）

### 4.2 跨上下文调用规则（严格）
- 禁止从上下文 A 的领域直接导入上下文 B 的领域。
- 必须通过 **ports** 或 **已发布的领域事件** 调用。
- 映射在 **ACL (Diplomat)** 中完成。

---

## 5. 项目布局（示例）

以下是一个名为 `order-service` 的服务示例项目结构。
语言无关布局；您可适配到 Java/Go/TS/C++。

```
order-service/
├─ README.md
├─ docs/
│  ├─ architecture_v1.md
│  ├─ adr/                         # 架构决策记录
│  │  ├─ 0001-bounded-contexts.md
│  │  └─ 0002-workflow-table.md
│  └─ api/
│     ├─ openapi.yaml              # HTTP API 契约
│     └─ schemas/                  # JSON schema / protobuf
├─ tools/
│  ├─ lint_arch/                   # 依赖规则检查器（自定义或现有）
│  └─ generate/                    # 代码生成脚本
├─ src/
│  ├─ shared/
│  │  ├─ contracts/                # 共享 DTOs、架构、错误码
│  │  ├─ observability/            # 日志、追踪、关联 ID
│  │  └─ testing/                  # 测试工具
│  └─ contexts/
│     ├─ order/
│     │  ├─ entry/                 # L1 - 控制器/处理器/消费者
│     │  │  ├─ http/
│     │  │  └─ mq/
│     │  ├─ application/           # L2 - 用例、工作流、协调者
│     │  │  ├─ usecases/
│     │  │  │  ├─ CreateOrder/
│     │  │  │  │  ├─ create_order_uc.md        # 用例规约（人所有）
│     │  │  │  │  ├─ workflow.table.yaml       # 显式编排表
│     │  │  │  │  ├─ create_order_uc.ts        # 编排器代码（AI 辅助）
│     │  │  │  │  └─ create_order_uc_test.ts   # 必须的测试
│     │  │  │  └─ CancelOrder/
│     │  │  ├─ coordinators/
│     │  │  │  ├─ commander.ts
│     │  │  │  ├─ data_clerk.ts
│     │  │  │  └─ diplomat_acl.ts
│     │  │  └─ ports/              # 用例所需接口
│     │  │     ├─ OrderRepository.port.ts
│     │  │     ├─ PaymentGateway.port.ts
│     │  │     └─ EventPublisher.port.ts
│     │  ├─ domain/                # 领域模型：纯逻辑
│     │  │  ├─ model/
│     │  │  │  ├─ Order.ts         # 聚合根
│     │  │  │  ├─ OrderItem.ts
│     │  │  │  └─ Money.ts         # 值对象
│     │  │  ├─ molecules/          # L3（可选）
│     │  │  │  └─ PriceCalculation.molecule.ts
│     │  │  ├─ atoms/              # L4
│     │  │  │  ├─ ValidateOrder.atom.ts
│     │  │  │  ├─ ComputeTotals.atom.ts
│     │  │  │  └─ DetermineDiscount.atom.ts
│     │  │  └─ events/
│     │  │     ├─ OrderCreated.event.ts
│     │  │     └─ OrderCancelled.event.ts
│     │  ├─ infrastructure/        # 实现端口的基础设施适配器
│     │  │  ├─ db/
│     │  │  │  └─ OrderRepository.pg.ts
│     │  │  ├─ http/
│     │  │  │  └─ PaymentGateway.http.ts
│     │  │  └─ messaging/
│     │  │     └─ EventPublisher.kafka.ts
│     │  └─ tests/
│     │     ├─ contract/           # 契约测试（端口/API）
│     │     ├─ integration/        # 集成测试
│     │     └─ e2e/
│     └─ payment/                  # 另一个限界上下文
│        └─ ...
└─ ci/
   ├─ pipeline.yml
   └─ quality-gates.yml
```

### 5.1 人所有 vs AI 辅助文件
**人所有（必须由人评审，通常由人撰写）**
- `docs/adr/*`
- `usecases/*/create_order_uc.md`（用例规约）
- `usecases/*/workflow.table.yaml`（工作流定义）
- `domain/model/*`（聚合边界和不变量）
- `ports/*`（接口、契约）

**AI 辅助（AI 编写大部分，人评审）**
- `entry/*` 处理器
- `application/usecases/*/*.ts` 实现
- `domain/atoms/*` 和 `domain/molecules/*` 实现
- 单元测试、fixture、模拟适配器

---

## 6. 依赖规则（强制）

### 6.1 允许的导入（在一个上下文内）
| 从何处 | 可导入 | 不可导入 |
|---|---|---|
| entry | application（commands/queries）, contracts | domain, infrastructure |
| application | domain, ports, contracts | infrastructure（实现）, entry |
| domain | domain 仅自身 | application, entry, infrastructure |
| infrastructure | ports, contracts（及其自身代码） | entry, application, domain（直接；允许通过 ports/contracts 获取领域类型） |

> 注意：某些语言可能需要在 repository 中使用领域类型。建议通过契约或定义的领域边界 DTO 进行映射。

### 6.2 同层隔离规则（严格）
- `domain/atoms/*` 不得导入任何其他 `atoms/*`
- `domain/molecules/*` 不得导入任何其他 `molecules/*`
- Use Cases 协调 atoms/molecules；atoms 保持独立。

### 6.3 执行机制
- CI 中的架构 lint：
  - 禁止的导入
  - 循环检测
- PR 模板要求列出受影响的上下文和层级。

---

## 7. 工作流表（显式编排）

### 7.1 目的
用显式、可检查的流替换隐藏的调用栈。
当故障发生时，工程师阅读：
**Entry → Use Case → Workflow Table → 失败的步骤**。

### 7.2 最小工作流表模式（示例）
`workflow.table.yaml`（示例概念格式）

```yaml
usecase: CreateOrder
version: 1
steps:
  - id: validate
    action: ValidateOrder
    on_fail: end_with_error

  - id: compute
    action: ComputeTotals
    on_fail: end_with_error

  - id: reserve_payment
    action: ReservePayment
    via_port: PaymentGateway
    on_fail: rollback_and_end

  - id: persist
    action: SaveOrder
    via_port: OrderRepository
    on_fail: rollback_and_end

  - id: publish_event
    action: PublishOrderCreated
    via_port: EventPublisher
    on_fail: warn_and_continue
```

> 您的实际执行引擎可以很简单：循环 + 切换 + 映射。

---

## 8. 测试标准

### 8.1 Atom 测试（必需）
- 每个 Atom 都有单元测试：
  - 正常情况
  - 边界情况
  - 错误情况

### 8.2 Use Case 测试（必需）
- Use case 测试必须覆盖：
  - 工作流顺利路径
  - 每个失败分支（on_fail 路径）
  - 端口交互期望（模拟 ports）

### 8.3 契约测试（推荐）
- 对于每个端口实现（适配器）：
  - 契约测试确保满足接口 + 行为假设
- 对于公共 API：
  - OpenAPI 架构验证测试、黄金响应

### 8.4 质量门禁（建议默认）
- CI 中单元测试强制
- 覆盖率阈值（上下文级别）：
  - Atoms + Use Cases >= 80%（团队可调整）
- 架构 lint 必须通过

---

## 9. 可观测性 & 调试标准

### 9.1 关联 ID
每个请求获得一个 `correlation_id`：
- 每个步骤中记录
- 跨端口传递

### 9.2 结构化日志
每个工作流步骤记录：
- `usecase`, `step_id`, `correlation_id`, `result`, `latency_ms`
- 错误包括 `error_code` 和 `blame_layer`（entry/application/domain/infra）

### 9.3 错误码约定
- `CTX-LAYER-CATEGORY-NNNN` 例：`ORD-DOM-VALID-0003`
- 每个错误必须映射到稳定的消息和修复提示。

---

## 10. 协作工作流 (AI + 人)

### 10.1 工作项模板（推荐）
1) 人撰写：
- 用例规约 (`*.md`)
- 工作流表 (`workflow.table.yaml`)
- 契约（DTO/架构）、端口接口定义

2) AI 编写：
- Atoms/molecules 代码
- Use case 实现
- 单元测试

3) 人评审：
- 领域不变量正确性
- 跨上下文边界完整性
- 测试充分性

### 10.2 提示规则（团队标准）
当要求 AI 实现时：
- 提供：
  - 目标文件路径
  - 层级约束（“此文件不得导入...”）
  - 输入/输出契约
  - 工作流表引用
  - 要求的测试

### 10.3 变更控制
- 一个 PR 理想情况下应涉及：
  - 1 个限界上下文
  - 1–2 个层级
- 跨上下文变更需要 ADR 或显式批准。

---

## 11. 迁移指南（从现有代码）

### 11.1 最快路径（推荐）
1) 识别限界上下文
2) 提取契约和 ports
3) 创建带工作流表的 use cases
4) 逐步将领域逻辑移入 atoms/molecules
5) 将副作用移入基础设施适配器

### 11.2 需消除的反模式
- “上帝服务”应用层同时做领域 + I/O
- 领域导入基础设施
- Use case 逻辑隐藏在深层辅助调用中
- Atom 调用 Atom（再次创建隐式链）

---

## 12. 附录：检查清单

### 12.1 合并 PR 前
- [ ] 架构 lint 通过（无禁止导入，无循环）
- [ ] 新的 Atom 有单元测试
- [ ] 若流程改变，Use case 工作流表已更新
- [ ] Ports 变更包括契约测试或模拟已更新
- [ ] 日志包含 `correlation_id` 和 `step_id`

### 12.2 引入新限界上下文时
- [ ] 分配上下文负责人
- [ ] 更新上下文映射（ADR）
- [ ] 为外部交互定义 ports
- [ ] Entry 层仅依赖 application + contracts

---

## V1 版本说明
- V1 聚焦于 **可执行的依赖规则 + 显式编排**。
- V2 候选特性：
  - 工作流执行引擎的代码生成
  - 自动的步骤到测试脚手架
  - 更丰富的领域事件和 Saga 模式
