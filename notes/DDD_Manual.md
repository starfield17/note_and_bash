# DDD Architecture Design Reference Manual v1.0

## 1. Core Principles

### 1.1 Dependency Inversion Principle (DIP)

*   **Rule:** The Domain layer must not depend on any external layers (Infrastructure, Web, Application).
*   **Implementation:** All Repository **interfaces** are defined in the Domain layer, and their **implementations** are defined in the Infrastructure layer.

### 1.2 Rich Domain Model

*   **Rule:** Reject "Anemic Models". An Entity must contain business logic, not just getters/setters.
*   **Instruction:** "Data and behavior coexist". Business rules that modify state must be written inside the entity, not in the Service layer.

### 1.3 Explicit Architecture

*   **Rule:** The code structure should directly reflect business meaning, not the technical framework.
*   **Naming:** Use the Ubiquitous Language. Package and class names must be strictly consistent with the terminology of their business domain.

---

## 2. Layering Strategy Details

To achieve separation of concerns, we strictly divide the system into four layers (referencing Onion Architecture / Clean Architecture):

| Layer                                     | Responsibility                                                                                                     | Allowed Dependency Direction     |
| :---------------------------------------- | :----------------------------------------------------------------------------------------------------------------- | :------------------------------- |
| **1. User Interface Layer (Interface / Presentation)** | Handles HTTP requests, RPC calls, message subscriptions. Parses parameters and calls the Application layer.            | -> Application                   |
| **2. Application Service Layer (Application)**        | Orchestrates business processes (Orchestration). **Contains no business rules**. Responsible for transaction control, permission checks, and DTO conversion. | -> Domain                        |
| **3. Domain Layer**                       | **Core layer**. Contains entities, value objects, aggregate roots, domain services, and domain events. Pure business logic.  | **No dependencies** (Pure Java/Go/Python) |
| **4. Infrastructure Layer**               | Provides technical implementations: database persistence, Redis, third-party API clients, message queue implementations.     | -> Domain (implements interfaces) |

---

## 3. Standard Project Structure

This is the most critical part. Please require the Agent to strictly follow this directory tree for code generation. Take an "OrderContext" in an e-commerce system as an example:

```text
src/
├── order_context/                  # Bounded Context: Order
│   ├── api/                        # [Interface Layer] Externally exposed interfaces
│   │   ├── http/                   # Rest Controller
│   │   │   └── OrderController.ts
│   │   └── rpc/                    # gRPC / Dubbo Handler
│   │
│   ├── application/                # [Application Layer] Business process orchestration
│   │   ├── command/                # Write operations (CQS: Command)
│   │   │   ├── PlaceOrderCmd.ts    # DTO
│   │   │   └── PlaceOrderHandler.ts# Application Service
│   │   ├── query/                  # Read operations (CQS: Query)
│   │   │   └── GetOrderByIdQry.ts
│   │   └── assembler/              # DTO <-> Entity Assembler
│   │
│   ├── domain/                     # [Domain Layer] Core business logic (no framework dependencies)
│   │   ├── model/                  # Domain Model
│   │   │   ├── aggregate/          # Aggregate
│   │   │   │   └── Order.ts        # [Aggregate Root] Contains core logic
│   │   │   ├── entity/             # Entity
│   │   │   │   └── OrderItem.ts    # Order Item
│   │   │   └── value_object/       # Value Object
│   │   │       ├── Address.ts      # Address (Immutable)
│   │   │       └── Money.ts        # Money (Immutable)
│   │   ├── service/                # Domain Service (cross-entity logic)
│   │   │   └── OrderPriceCalculator.ts
│   │   ├── event/                  # Domain Event
│   │   │   └── OrderCreatedEvent.ts
│   │   └── repository/             # Repository [Interfaces]
│   │       └── IOrderRepository.ts # Define interfaces only, no SQL dependency
│   │
│   └── infrastructure/             # [Infrastructure Layer] Technical implementation
│       ├── persistence/            # Persistence implementation
│       │   ├── mapper/             # ORM Mapper (MyBatis/TypeORM/JPA)
│       │   ├── data_object/        # DO (Data Object mapping to database table)
│       │   └── OrderRepositoryImpl.ts # Implements IOrderRepository from domain
│       └── client/                 # Anti-Corrosion Layer (ACL) implementation
│           └── InventoryClient.ts  # Implementation for calling inventory service
│
└── shared/                         # Shared Kernel
    └── domain/
        ├── AggregateRoot.ts        # Base Class
        ├── ValueObject.ts          # Base Class
        └── DomainEvent.ts          # Base Class
```

---

## 4. Component Definitions for AI

When instructing the AI to generate specific components, use the following definitions as constraints:

### A. Aggregate Root

*   **Constraint:** Only Aggregate Roots can have a Repository.
*   **Behavior:** Must guarantee data consistency within the aggregate.
*   **Code characteristics:** Contains business methods like `create()`, `changeStatus()`. Directly exposing the internal List's `add` method is forbidden (should be encapsulated as `addItem`).

### B. Value Object

*   **Constraint:** **Immutable**.
*   **Code characteristics:** No setters. All modification operations return a new object (e.g., `money.add(otherMoney)` returns a new Money object).
*   **Criterion:** If two objects can be interchanged when their attributes are identical, they are value objects.

### C. Repository

*   **Constraint:** The input and output must be an **Aggregate Root**. Directly returning underlying Data Objects (DAO/PO) is strictly forbidden.
*   **Responsibility:** Responsible for the conversion between Entity and Data Object.

### D. Application Service

*   **Constraint:** **Contains no `if/else` business logic**.
*   **Pseudo-code template:**

  ```python
  def place_order(command):
      # 1. Prepare data
      customer = customer_repo.find(command.user_id)
      # 2. Call domain layer business behavior (Core!)
      order = Order.create(customer, command.items)
      # 3. Persist
      order_repo.save(order)
      # 4. Publish event (optional)
      event_bus.publish(OrderCreatedEvent(order))
  ```

---

## 5. System Prompt Specifically for LLM Agents

If you are building a programming assistant Agent, you can put the following content directly into its system prompt:

> **[System Directive: DDD Expert Mode]**
>
> You are an expert Software Architect specializing in Domain-Driven Design (DDD). When asked to generate code or design systems, you must strictly adhere to the following rules:
>
> 1.  **Strict Layering:** Never allow the `Domain` layer to import `Infrastructure` or `Application` packages.
> 2.  **Rich Models:** Generate "Rich Domain Models". Entities must contain business logic methods. Avoid generating "Anemic Models" (classes with only getters/setters).
> 3.  **Value Objects:** Prefer Value Objects over primitives. E.g., Use a `Email` class instead of `string email`. Value Objects must be immutable.
> 4.  **Repository Pattern:** Define Repository interfaces in the Domain layer, but implement them in the Infrastructure layer.
> 5.  **Ubiquitous Language:** Use the user's business terminology precisely for class and method names.
> 6.  **Directory Structure:** Follow the standard `api` -> `application` -> `domain` -> `infrastructure` folder structure.
>
> **Goal:** Produce code that is testable, decoupled, and business-centric.

---
