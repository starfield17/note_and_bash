# DDD 架构设计参考手册 v1.0

## 1. 核心设计原则 (Core Principles)

### 1.1 依赖倒置原则 (DIP)

* **规则：** 领域层 (Domain) 不得依赖任何外部层（基础设施、Web、应用层）。
* **实现：** 所有的 Repository **接口** 定义在领域层，**实现** 定义在基础设施层。

### 1.2 充血模型 (Rich Domain Model)

* **规则：** 拒绝“贫血模型”。实体 (Entity) 必须包含业务逻辑，不仅仅是 getter/setter。
* **指令：** "数据与行为同在"。如果是修改状态的业务规则，必须写在实体内部，而不是 Service 层。

### 1.3 显式架构 (Explicit Architecture)

* **规则：** 代码结构应直接反映业务含义，而非技术框架。
* **命名：** 使用统一语言 (Ubiquitous Language)。包名、类名必须与其业务领域的术语严格一致。

---

## 2. 架构分层详解 (Layering Strategy)

为了实现关注点分离，我们将系统严格划分为四层（参考洋葱架构/整洁架构）：

| 层级 (Layer)                              | 职责 (Responsibility)                                   | 允许的依赖方向                       |
| :-------------------------------------- | :---------------------------------------------------- | :---------------------------- |
| **1. 用户接口层 (Interface / Presentation)** | 处理 HTTP 请求、RPC 调用、消息订阅。解析参数并调用 Application 层。         | -> Application                |
| **2. 应用服务层 (Application)**              | 编排业务流程（Orchestration）。**不包含业务规则**。负责事务控制、权限校验、DTO 转换。 | -> Domain                     |
| **3. 领域层 (Domain)**                     | **核心层**。包含实体、值对象、聚合根、领域服务、领域事件。纯粹的业务逻辑。               | **无依赖** (Pure Java/Go/Python) |
| **4. 基础设施层 (Infrastructure)**           | 提供技术实现：数据库持久化、Redis、第三方 API 客户端、消息队列实现。               | -> Domain (实现接口)              |

---

## 3. 标准化工程目录结构 (Standard Project Structure)

这是最关键的部分。请要求 Agent 严格遵循此目录树进行代码生成。以一个电商系统的“订单上下文 (OrderContext)”为例：

```text
src/
├── order_context/                  # 限界上下文：订单
│   ├── api/                        # [接口层] 对外暴露的接口
│   │   ├── http/                   # Rest Controller
│   │   │   └── OrderController.ts
│   │   └── rpc/                    # gRPC / Dubbo Handler
│   │
│   ├── application/                # [应用层] 业务流程编排
│   │   ├── command/                # 写操作 (CQS: Command)
│   │   │   ├── PlaceOrderCmd.ts    # DTO
│   │   │   └── PlaceOrderHandler.ts# Application Service
│   │   ├── query/                  # 读操作 (CQS: Query)
│   │   │   └── GetOrderByIdQry.ts
│   │   └── assembler/              # DTO <-> Entity 转换器
│   │
│   ├── domain/                     # [领域层] 核心业务逻辑 (无框架依赖)
│   │   ├── model/                  # 领域模型
│   │   │   ├── aggregate/          # 聚合
│   │   │   │   └── Order.ts        # [聚合根] 包含核心逻辑
│   │   │   ├── entity/             # 实体
│   │   │   │   └── OrderItem.ts    # 订单项
│   │   │   └── value_object/       # 值对象
│   │   │       ├── Address.ts      # 地址 (Immutable)
│   │   │       └── Money.ts        # 金额 (Immutable)
│   │   ├── service/                # 领域服务 (跨实体逻辑)
│   │   │   └── OrderPriceCalculator.ts
│   │   ├── event/                  # 领域事件
│   │   │   └── OrderCreatedEvent.ts
│   │   └── repository/             # 仓储 [接口] (Repository Interfaces)
│   │       └── IOrderRepository.ts # 只定义接口，不依赖 SQL
│   │
│   └── infrastructure/             # [基础设施层] 技术实现
│       ├── persistence/            # 持久化实现
│       │   ├── mapper/             # ORM Mapper (MyBatis/TypeORM/JPA)
│       │   ├── data_object/        # DO (数据库表映射对象)
│       │   └── OrderRepositoryImpl.ts # 实现 domain 中的 IOrderRepository
│       └── client/                 # 防腐层 (ACL) 实现
│           └── InventoryClient.ts  # 调用库存服务的实现
│
└── shared/                         # 共享内核 (Shared Kernel)
    └── domain/
        ├── AggregateRoot.ts        # 基类
        ├── ValueObject.ts          # 基类
        └── DomainEvent.ts          # 基类
```

---

## 4. 关键构件定义 (Component Definitions for AI)

当指示 AI 生成特定组件时，请使用以下定义作为约束：

### A. 聚合根 (Aggregate Root)

* **约束：** 只有聚合根可以拥有 Repository。
* **行为：** 必须保证聚合内的数据一致性。
* **代码特征：** 包含 `create()`, `changeStatus()` 等业务方法，禁止直接暴露内部 List 的 `add` 方法（应封装为 `addItem`）。

### B. 值对象 (Value Object)

* **约束：** **不可变 (Immutable)**。
* **代码特征：** 没有 Setter。所有修改操作都返回一个新的对象（例如 `money.add(otherMoney)` 返回新 Money）。
* **判断标准：** 如果两个对象属性相同就可以互相替换，它是值对象。

### C. 资源库 (Repository)

* **约束：** 输入输出必须是 **聚合根 (Aggregate Root)**，严禁直接返回底层的 Data Object (DAO/PO)。
* **职责：** 负责 Entity 和 Data Object 之间的互相转换。

### D. 应用服务 (Application Service)

* **约束：** **没有任何 `if/else` 业务判断**。
* **伪代码模板：**

  ```python
  def place_order(command):
      # 1. 准备数据
      customer = customer_repo.find(command.user_id)
      # 2. 调用领域层业务行为 (核心!)
      order = Order.create(customer, command.items)
      # 3. 持久化
      order_repo.save(order)
      # 4. 发布事件 (可选)
      event_bus.publish(OrderCreatedEvent(order))
  ```

---

## 5. 专门给 LLM Agent 的 System Prompt

如果您正在构建一个辅助编程的 Agent，可以将以下内容直接放入它的系统提示词中：

> **[System Directive: DDD Expert Mode]**
>
> You are an expert Software Architect specializing in Domain-Driven Design (DDD). When asked to generate code or design systems, you must strictly adhere to the following rules:
>
> 1. **Strict Layering:** Never allow the `Domain` layer to import `Infrastructure` or `Application` packages.
> 2. **Rich Models:** Generate "Rich Domain Models". Entities must contain business logic methods. Avoid generating "Anemic Models" (classes with only getters/setters).
> 3. **Value Objects:** Prefer Value Objects over primitives. E.g., Use a `Email` class instead of `string email`. Value Objects must be immutable.
> 4. **Repository Pattern:** Define Repository interfaces in the Domain layer, but implement them in the Infrastructure layer.
> 5. **Ubiquitous Language:** Use the user's business terminology precisely for class and method names.
> 6. **Directory Structure:** Follow the standard `api` -> `application` -> `domain` -> `infrastructure` folder structure.
>
> **Goal:** Produce code that is testable, decoupled, and business-centric.

---
