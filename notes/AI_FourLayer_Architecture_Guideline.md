# AI-Friendly Four-Layer Architecture (4L) — Landing Spec

> A practical, GitHub-ready guideline for building **AI-assisted projects** with **strict layering, one-way dependencies, and explicit control-flow** to reduce debug cost and make collaboration scalable.

- **Audience**: engineers using AI to generate substantial code while maintaining maintainability and predictable debugging.
- **Goal**: turn “implicit dependency webs” into **visible, enforceable structure**.

---

## 1. Core Ideas

### 1.1 Problem This Solves
AI often writes correct local logic but struggles with:
- **fuzzy dependency chains** (`a -> b -> c -> ... -> a`)
- **hidden coupling** between modules
- **debugging through long call stacks**

This spec enforces:
- **single-direction dependencies**
- **no peer-to-peer coupling** within key layers
- **explicit control-flow tables** that make execution paths readable

### 1.2 Design Summary (TL;DR)
- **L1 Entry**: minimal entry module(s), no business logic.
- **L2 Orchestration**: *Commander* (control-flow table), *Data*, *Diplomat*, and API docs.
- **L3 Molecules**: compose atoms; **molecule-to-molecule calls are forbidden**.
- **L4 Atoms**: small complete functions (~80 LOC target); **atom-to-atom calls are forbidden**.

Debug path becomes:
> `L1 -> L2(flow table) -> exact failing L3/L4 unit`

---

## 2. Layer Responsibilities

### L1 — Entry Layer
**Purpose**: system entry points (CLI / service main / handler).
- Owns bootstrapping only: config load, DI/container init, logging init.
- Calls into **L2 only** (commander/diplomat).

**Forbidden**
- direct call to L3/L4
- business logic and workflow branching

---

### L2 — Orchestration Layer
**Purpose**: single place for **workflow control** and **cross-module coordination**.

Recommended sub-roles:
- **Commander**: control-flow table (steps, conditions, transitions).
- **Data Clerk**: data mapping/validation boundary (DTO ↔ Domain ↔ Persistence).
- **Diplomat**: cross-entry or cross-domain communications (prevents L1 modules calling each other directly).
- **Atomic API Doc**: documentation for L4 atoms (inputs/outputs/errors).

**Allowed**
- Calls L3 molecules and L4 atoms (depending on your strictness).
- Controls branching, retries, fallback, error-to-next-step mapping.

**Forbidden**
- implementing heavy domain logic (push logic down to L3/L4)
- importing from L1 (L2 should not depend on entry layer)

---

### L3 — Molecule Layer
**Purpose**: compose atoms into meaningful domain operations.

- Each molecule module can use **multiple atoms**.
- Molecule modules are **isolated**:  
  ✅ molecule can call atoms (L4)  
  ✅ molecule can be called by L2  
  ❌ molecule cannot call other molecules

**Forbidden**
- `molecule_a -> molecule_b` calls
- shared mutable global state

---

### L4 — Atom Layer
**Purpose**: smallest reusable building blocks, complete and testable.

- Target size: **~80 LOC** (guideline, not a hard rule).
- Each atom:
  - does one complete thing
  - has clear inputs/outputs/errors
  - is independently unit-testable
- **Atoms do not call atoms.**

**Forbidden**
- calling other atoms
- hidden I/O (unless explicitly part of the atom’s contract)

---

## 3. Dependency Rules (Hard Constraints)

### 3.1 Allowed Dependency Directions
```
L1  ->  L2  ->  (L3, L4)
L3  ->  L4
L4  ->  (no internal project deps)
```

### 3.2 Forbidden Dependencies
- L4 → L4
- L3 → L3
- L1 → L3 / L4
- L2 → L1
- any cyclic dependencies anywhere

### 3.3 Dependency Matrix
| From \ To | L1 | L2 | L3 | L4 |
|---|---:|---:|---:|---:|
| **L1** | ✗ | ✓ | ✗ | ✗ |
| **L2** | ✗ | (✓)* | ✓ | ✓ |
| **L3** | ✗ | ✗ | ✗ | ✓ |
| **L4** | ✗ | ✗ | ✗ | ✗ |

\* L2 internal refs should still avoid tangling (prefer subpackages + interfaces).

---

## 4. Project Structure Example

Below is a **language-agnostic** structure. Replace file extensions as needed.

```
project/
  README.md
  docs/
    architecture_4l.md
    atoms_catalog.md
  scripts/
    check_deps.sh
  src/
    l1_entry/
      app_main.cpp
      app_main.h
      http_handler.cpp
      http_handler.h

    l2_orchestration/
      commander/
        flows/
          user_register.flow.yaml
          user_login.flow.yaml
        flow_runtime.cpp
        flow_runtime.h
      diplomat/
        gateway_user.cpp
        gateway_user.h
        gateway_billing.cpp
        gateway_billing.h
      data_clerk/
        dto_user.h
        map_user.cpp
        map_user.h
      api_docs/
        atoms_user.md

    l3_molecules/
      user/
        user_register_molecule.cpp
        user_register_molecule.h
        user_login_molecule.cpp
        user_login_molecule.h
      billing/
        invoice_issue_molecule.cpp
        invoice_issue_molecule.h

    l4_atoms/
      user/
        validate_email_atom.cpp
        validate_email_atom.h
        hash_password_atom.cpp
        hash_password_atom.h
        insert_user_atom.cpp
        insert_user_atom.h
      billing/
        calc_tax_atom.cpp
        calc_tax_atom.h

  tests/
    l4_atoms/
      test_validate_email_atom.cpp
    l3_molecules/
      test_user_register_molecule.cpp
```

---

## 5. L2 “Control-Flow Table” Specification

### 5.1 Why Tables?
- execution becomes readable at a glance
- errors map to steps without searching call chains
- AI can generate steps safely if the table format is strict

### 5.2 Flow File Format (YAML)
A flow describes steps and transitions.

```yaml
# src/l2_orchestration/commander/flows/user_register.flow.yaml
flow_id: user_register_v1
context: UserRegisterContext

steps:
  - id: S1_validate_input
    call: l4_atoms.user.validate_email_atom
    on_success: S2_hash_password
    on_error:
      INVALID_EMAIL: END_BAD_REQUEST

  - id: S2_hash_password
    call: l4_atoms.user.hash_password_atom
    on_success: S3_insert_user
    on_error:
      HASH_FAIL: END_INTERNAL_ERROR

  - id: S3_insert_user
    call: l4_atoms.user.insert_user_atom
    on_success: END_OK
    on_error:
      DUPLICATE_USER: END_CONFLICT
      DB_FAIL: END_INTERNAL_ERROR

ends:
  END_OK:
    http_status: 201
  END_BAD_REQUEST:
    http_status: 400
  END_CONFLICT:
    http_status: 409
  END_INTERNAL_ERROR:
    http_status: 500
```

### 5.3 Commander Runtime Rules
- Must support:
  - step dispatch
  - context passing
  - structured error codes
  - deterministic transitions

**Commander should not contain business logic**; only dispatch and transition.

---

## 6. “Diplomat” Pattern (Cross-Entry / Cross-Domain)

### 6.1 Rule
- Entry module A **must not** call entry module B directly.
- Use L2 **Diplomat** as the only bridge.

### 6.2 Why
- prevents hidden coupling between entry points
- enforces star-shaped communication rather than chain-shaped (`1->2->3`)
- keeps cross-boundary calls auditable

### 6.3 Example
- `l1_entry/http_handler` calls `l2_orchestration/diplomat/gateway_user`
- diplomat chooses which flow/molecule to run

---

## 7. Atom Contract & Documentation Standard

### 7.1 Atom Must Declare
- purpose
- inputs / outputs
- error codes (enumerated)
- side effects (DB, network, filesystem) — explicit

### 7.2 Atom API Doc Template (Markdown)
```md
## validate_email_atom
**Purpose**: Validate email address string.

**Input**
- email: string

**Output**
- ok: bool

**Errors**
- INVALID_EMAIL
- EMPTY_EMAIL

**Side Effects**
- none

**Notes**
- Pure function preferred.
```

Store these in:
- `src/l2_orchestration/api_docs/atoms_*.md`  
or
- `docs/atoms_catalog.md` (project-wide)

---

## 8. Coding Rules (Enforcement)

### 8.1 Naming & Files
- L4 atoms end with `_atom`
- L3 molecules end with `_molecule`
- flows end with `.flow.yaml`

### 8.2 Import/Include Policy
- Each layer exposes a minimal public interface:
  - e.g., `l3_molecules/user/user_register_molecule.h`
- Ban direct includes that break layering.

### 8.3 Automated Checks
**Minimum recommended**
- dependency check script (static scan)
- CI gate on violations

Example `scripts/check_deps.sh` idea:
- grep includes/imports and assert:
  - l4 does not import l4/l3/l2/l1
  - l3 does not import l3/l2/l1
  - l1 only imports l2
  - l2 does not import l1

(Implementation varies by language; start simple and iterate.)

---

## 9. Testing Strategy (Aligned with Layers)

### L4 Unit Tests (Most Important)
- each atom independently tested
- fast, deterministic

### L3 Unit/Component Tests
- validate composition logic
- mock external I/O

### L2 Flow Tests
- ensure flow tables transition correctly on success/error
- snapshot tests on flow definitions (optional)

### L1 Smoke Tests
- minimal integration (boot + route wiring)

---

## 10. AI Collaboration Workflow (Practical)

### 10.1 Generate L4 Atoms First
1. Write atom contract (inputs/outputs/errors)
2. Ask AI to implement atom + unit tests
3. Validate no forbidden dependencies

### 10.2 Then Generate L3 Molecules
- molecules compose atoms
- keep molecules thin: sequencing + mapping only

### 10.3 Finally Write L2 Flows
- create flow YAML
- connect to commander runtime
- map errors to end states

### 10.4 Human “1%” Work That Matters Most
- define boundaries & contracts
- enforce dependency rules
- maintain flow tables as truth of orchestration

---

## 11. Code Review Checklist

- [ ] Layering: does the PR introduce forbidden dependencies?
- [ ] L4 atoms: no calls to other atoms; contract is explicit; unit tests included.
- [ ] L3 molecules: no calls to other molecules; only composes atoms.
- [ ] L2 commander: control-flow only; no heavy logic; flow table updated.
- [ ] Error codes: structured and mapped in flow YAML.
- [ ] Entry layer: no business logic; only calls L2.

---

## 12. Common Pitfalls & Fixes

### Pitfall: “Helper” atoms calling atoms
**Fix**: merge them or lift composition to L3 molecule.

### Pitfall: Molecule A needs Molecule B
**Fix**: extract shared atoms or create a new molecule that owns the composition (still: no peer calls).

### Pitfall: L2 becomes a god-object
**Fix**: keep L2 about orchestration; push computations to L3/L4; use roles (commander/data/diplomat).

---