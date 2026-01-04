# AI Coding + Human Collaboration Architecture Specification (V1)

> Purpose: Provide a **practical, enforceable** architecture and collaboration standard for teams using **AI-assisted coding** at scale.  
> Goals: **(1) predictable dependency graph (2) fast bug localization (3) contract-first development (4) testable, reviewable changes**.

---

## 1. Design Goals

### 1.1 What this architecture optimizes for
- **Short error localization path**: failures should point to a **small unit** (Atom/Use Case) instead of a long implicit call chain.
- **No circular dependencies by construction**: enforce a **one-way dependency flow** and forbid same-layer mutual calls.
- **AI-friendly decomposition**: work items are cut into **contracted, testable units**; AI primarily fills implementation within boundaries.
- **Human “semantic ownership”**: domain boundaries, invariants, and workflows are defined by humans; AI implements details.

### 1.2 Non-goals
- This is not a “one true architecture” for every system. V1 targets:
  - Backend services / APIs / business systems
  - Medium-to-large codebases with multiple contributors
- If you are building a small script or a prototype, you may relax some rules.

---

## 2. Core Principles (must-follow)

### P0. Contract First
All cross-layer or cross-context interactions must be defined by **contracts**:
- API contract (OpenAPI / gRPC proto / interface definition)
- Data contract (Schema, DTO)
- Domain contract (invariants, state transitions, domain events)

### P1. Unidirectional Dependencies
Dependency direction is **strict**:

**Interface/Contracts → Application (Use Cases) → Domain → (Ports) → Infrastructure Adapters**

And within the “Atom/Molecule” concept:
- **Atoms** do not depend on other Atoms.
- **Molecules** do not depend on other Molecules.
- Orchestration happens in **Use Cases / Workflow tables**.

### P2. Orchestration is Explicit
The execution flow must be visible:
- Use a **workflow table / state machine** in the Use Case layer.
- Avoid burying flow logic inside deep call stacks.

### P3. Everything Testable by Unit
Every Atom and Use Case must have:
- Unit tests (minimum)
- Contract tests at boundaries (when applicable)

### P4. Ownership + Governance
- Each bounded context has a **human owner**.
- PR change scope is limited; architecture lint prevents accidental boundary violations.

---

## 3. Layer Model (DDD + AI-Friendly 4-Layer Fusion)

This standard combines:
- **DDD / Hexagonal architecture** (Context, Domain, Ports & Adapters)
- The referenced answer’s “4-layer” idea (Entry / Orchestrator / Molecules / Atoms)

### 3.1 Layers and responsibilities

#### L1 — Entry (Interface Layer)
**What it contains**
- HTTP controllers / CLI entry / message consumers
- Request validation (syntax-level), auth checks (optional)
- Mapping transport DTO ↔ application command/query

**What it must NOT contain**
- Business rules
- Domain invariants
- Multi-step workflows

**Allowed dependencies**
- Only on `application` contracts (commands/queries) and `contracts` DTOs

---

#### L2 — Orchestration (Application / Use Case Layer)
**What it contains**
- Use cases (application services)
- Workflow tables / state machine definitions
- Coordinators (mediator-like roles):
  - **Commander**: executes workflow steps
  - **Data Clerk**: assembles context data, caching, correlation id
  - **Diplomat** (ACL): cross-context requests via ports; no direct imports

**What it must NOT contain**
- Database/HTTP/MQ client code (goes to infrastructure adapters)
- Heavy algorithmic implementation that belongs to domain

**Allowed dependencies**
- `domain` (entities, value objects, domain services, domain events)
- `ports` (interfaces)
- `contracts` (DTO/schema)
- Must NOT depend on `infrastructure` implementations directly

---

#### L3 — Molecules (Domain Composition Units)
This is optional but recommended when domain logic is complex.

**Definition**
- A Molecule is a **composite domain operation** that:
  - uses multiple Atoms within a domain aggregate boundary
  - is still pure domain logic (no IO)

**Rules**
- **Molecules cannot call other Molecules**
- Molecules can call Atoms, entities, and value objects
- All side effects happen via ports triggered from Use Cases (not inside Molecules)

---

#### L4 — Atoms (Small, Independent Domain Units)
**Definition**
- Small, deterministic operations (~50–120 LOC guideline)
- Contains one complete micro capability (validation, calculation, mapping, rule evaluation)
- No IO and no calls to other Atoms

**Rules**
- Atoms must be **pure** whenever possible (input → output)
- Any external dependency must be expressed via **interfaces passed in** (rare; prefer ports at app layer)

---

## 4. Bounded Contexts (DDD)

### 4.1 What is a bounded context
A bounded context is a self-contained area of business meaning:
- Owns its domain model and invariants
- Exposes capabilities through **ports/contracts**
- Has an anti-corruption layer (ACL) for external dependencies

### 4.2 Cross-context calling rule (hard)
- No direct import from context A domain into context B domain.
- Must call via **ports** or **published domain events**.
- Mapping is done in **ACL (Diplomat)**.

---

## 5. Project Layout (Example)

Below is a sample project structure for a service named `order-service`.
Language-agnostic layout; you can adapt to Java/Go/TS/C++.

```
order-service/
├─ README.md
├─ docs/
│  ├─ architecture_v1.md
│  ├─ adr/                         # Architecture Decision Records
│  │  ├─ 0001-bounded-contexts.md
│  │  └─ 0002-workflow-table.md
│  └─ api/
│     ├─ openapi.yaml              # HTTP API contract
│     └─ schemas/                  # JSON schema / protobuf
├─ tools/
│  ├─ lint_arch/                   # dependency rule checker (custom or existing)
│  └─ generate/                    # codegen scripts
├─ src/
│  ├─ shared/
│  │  ├─ contracts/                # shared DTOs, schema, error codes
│  │  ├─ observability/            # logging, tracing, correlation id
│  │  └─ testing/                  # test utilities
│  └─ contexts/
│     ├─ order/
│     │  ├─ entry/                 # L1 - controllers/handlers/consumers
│     │  │  ├─ http/
│     │  │  └─ mq/
│     │  ├─ application/           # L2 - use cases, workflows, coordinators
│     │  │  ├─ usecases/
│     │  │  │  ├─ CreateOrder/
│     │  │  │  │  ├─ create_order_uc.md        # use case spec (human-owned)
│     │  │  │  │  ├─ workflow.table.yaml       # explicit orchestration table
│     │  │  │  │  ├─ create_order_uc.ts        # orchestrator code (AI-assisted)
│     │  │  │  │  └─ create_order_uc_test.ts   # must-have tests
│     │  │  │  └─ CancelOrder/
│     │  │  ├─ coordinators/
│     │  │  │  ├─ commander.ts
│     │  │  │  ├─ data_clerk.ts
│     │  │  │  └─ diplomat_acl.ts
│     │  │  └─ ports/              # interfaces required by use cases
│     │  │     ├─ OrderRepository.port.ts
│     │  │     ├─ PaymentGateway.port.ts
│     │  │     └─ EventPublisher.port.ts
│     │  ├─ domain/                # domain model: pure logic
│     │  │  ├─ model/
│     │  │  │  ├─ Order.ts         # aggregate root
│     │  │  │  ├─ OrderItem.ts
│     │  │  │  └─ Money.ts         # value object
│     │  │  ├─ molecules/          # L3 (optional)
│     │  │  │  └─ PriceCalculation.molecule.ts
│     │  │  ├─ atoms/              # L4
│     │  │  │  ├─ ValidateOrder.atom.ts
│     │  │  │  ├─ ComputeTotals.atom.ts
│     │  │  │  └─ DetermineDiscount.atom.ts
│     │  │  └─ events/
│     │  │     ├─ OrderCreated.event.ts
│     │  │     └─ OrderCancelled.event.ts
│     │  ├─ infrastructure/        # adapters implementing ports
│     │  │  ├─ db/
│     │  │  │  └─ OrderRepository.pg.ts
│     │  │  ├─ http/
│     │  │  │  └─ PaymentGateway.http.ts
│     │  │  └─ messaging/
│     │  │     └─ EventPublisher.kafka.ts
│     │  └─ tests/
│     │     ├─ contract/           # contract tests (ports/API)
│     │     ├─ integration/        # integration tests
│     │     └─ e2e/
│     └─ payment/                  # another bounded context
│        └─ ...
└─ ci/
   ├─ pipeline.yml
   └─ quality-gates.yml
```

### 5.1 Human-owned vs AI-assisted files
**Human-owned (must be reviewed and usually authored by humans)**
- `docs/adr/*`
- `usecases/*/create_order_uc.md` (use case spec)
- `usecases/*/workflow.table.yaml` (workflow definition)
- `domain/model/*` (aggregate boundaries & invariants)
- `ports/*` (interfaces, contracts)

**AI-assisted (AI writes most, human reviews)**
- `entry/*` handlers
- `application/usecases/*/*.ts` implementation
- `domain/atoms/*` and `domain/molecules/*` implementations
- unit tests, fixtures, mock adapters

---

## 6. Dependency Rules (Enforced)

### 6.1 Allowed imports (within a context)
| From | Can import | Cannot import |
|---|---|---|
| entry | application (commands/queries), contracts | domain, infrastructure |
| application | domain, ports, contracts | infrastructure (implementations), entry |
| domain | domain only | application, entry, infrastructure |
| infrastructure | ports, contracts (and its own code) | entry, application, domain (directly; allow domain types only through ports/contracts) |

> Note: some languages may require domain types in repositories. Prefer mapping via contracts or defined domain boundary DTOs.

### 6.2 Same-layer isolation rules (hard)
- `domain/atoms/*` must not import any other `atoms/*`
- `domain/molecules/*` must not import any other `molecules/*`
- Use Cases coordinate atoms/molecules; atoms remain independent.

### 6.3 Enforcement mechanisms
- Architecture lint in CI:
  - forbidden imports
  - cycle detection
- PR template requires listing affected contexts and layers.

---

## 7. Workflow Table (Explicit Orchestration)

### 7.1 Why
Replace hidden call stacks with an explicit, inspectable flow.  
When failure occurs, engineers read:
**Entry → Use Case → Workflow Table → failing step**.

### 7.2 Minimal workflow table schema (example)
`workflow.table.yaml` (example conceptual format)

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

> Your actual execution engine can be simple: a loop + switch + map.

---

## 8. Testing Standard

### 8.1 Atom tests (required)
- Each Atom has unit tests:
  - nominal case
  - boundary cases
  - error cases

### 8.2 Use Case tests (required)
- Use case tests must cover:
  - workflow happy path
  - each failure branch (on_fail paths)
  - port interaction expectations (mock ports)

### 8.3 Contract tests (recommended)
- For each port implementation (adapter):
  - contract test ensures it satisfies interface + behavior assumptions
- For public API:
  - OpenAPI schema validation tests, golden responses

### 8.4 Quality gates (suggested defaults)
- Unit tests mandatory in CI
- Coverage threshold (context-level):
  - Atoms + Use Cases >= 80% (adjust per team)
- Architecture lint must pass

---

## 9. Observability & Debug Standard

### 9.1 Correlation ID
Every request gets a `correlation_id`:
- logged in every step
- passed across ports

### 9.2 Structured logging
Each workflow step logs:
- `usecase`, `step_id`, `correlation_id`, `result`, `latency_ms`
- errors include `error_code` and `blame_layer` (entry/application/domain/infra)

### 9.3 Error code convention
- `CTX-LAYER-CATEGORY-NNNN` e.g. `ORD-DOM-VALID-0003`
- Each error must map to a stable message and remediation hint.

---

## 10. Collaboration Workflow (AI + Human)

### 10.1 Work item template (recommended)
1) Human writes:
- Use case spec (`*.md`)
- Workflow table (`workflow.table.yaml`)
- Contracts (DTO/schema), port interface definitions

2) AI writes:
- Atoms/molecules code
- Use case implementation
- Unit tests

3) Human reviews:
- domain invariants correctness
- cross-context boundary integrity
- test adequacy

### 10.2 Prompting rules (team standard)
When asking AI to implement:
- Provide:
  - target file path
  - layer constraints (“this file must not import …”)
  - input/output contract
  - workflow table reference
  - required tests

### 10.3 Change control
- One PR should ideally touch:
  - 1 bounded context
  - 1–2 layers
- Cross-context changes require ADR or explicit approval.

---

## 11. Migration Guide (from existing code)

### 11.1 Fastest path (recommended)
1) Identify bounded contexts
2) Extract contracts and ports
3) Create use cases with workflow tables
4) Gradually move domain logic into atoms/molecules
5) Move side effects into infrastructure adapters

### 11.2 Anti-patterns to eliminate
- “God service” application layer doing domain + IO
- Domain importing infrastructure
- Use case logic hidden in deep helper calls
- Atom calling atom (creates implicit chains again)

---

## 12. Appendix: Checklist

### 12.1 Before merging a PR
- [ ] Architecture lint passes (no forbidden imports, no cycles)
- [ ] New Atom has unit tests
- [ ] Use case workflow table updated if flow changed
- [ ] Ports changes include contract tests or mocks updated
- [ ] Logs include correlation_id and step_id

### 12.2 When introducing a new bounded context
- [ ] Context owner assigned
- [ ] Context map updated (ADR)
- [ ] Ports defined for external interactions
- [ ] Entry layer only depends on application + contracts

---

## V1 Version Notes
- V1 focuses on **enforceable dependency rules + explicit orchestration**.
- V2 candidates:
  - codegen for workflow execution engine
  - automated step-to-test scaffolding
  - richer domain event and saga patterns
