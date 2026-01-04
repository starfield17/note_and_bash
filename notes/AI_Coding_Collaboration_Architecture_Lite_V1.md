# AI Coding + Human Collaboration Architecture (Lite V1)

This is a **simplified** version of the “AI Coding + Human Collaboration” architecture spec, intended for:
- **small projects** (1–5 devs),
- **simple feature sets** (CLI tools / small services / utilities),
- and **incremental refactors** of existing repos.

It keeps the key benefits:
- **short debugging path**
- **no spaghetti dependencies**
- **AI-friendly task slicing**
while reducing ceremony (no heavy context map / ADR stack unless needed).

---

## 1) Core Idea in One Picture

For small projects, you usually only need **3 layers** (plus optional `infra/`):

**Entry → Orchestration → Core**

- **Entry**: CLI / GUI / HTTP handlers (IO boundary)
- **Orchestration**: “pipeline / use case” code that describes *steps and flow*
- **Core**: pure, testable logic (Atoms/Molecules) + data types

Optional:
- **Infra**: file system, network, database, GPU, external services adapters

---

## 2) Minimal Rules (Lite but enforceable)

### R1. One-way imports
Inside your package/module, dependencies must flow only:

`entry → orchestration → core`  
and `orchestration → infra` (via interfaces or thin adapters)

**Forbidden**
- `core` importing `entry` / `orchestration` / `infra`
- `entry` importing `core` directly (must go through orchestration for consistent flow)
- hidden cross-calls between entry variants (e.g., GUI calling CLI internals)

### R2. Core = Atoms & Molecules
Keep Core split into two subtypes:

- **Atoms**: small independent functions/classes (guideline 50–120 LOC), no IO, do not call other atoms.
- **Molecules** (optional): compose atoms, still no IO.

In small projects you can start with only `atoms/` and add `molecules/` if needed.

### R3. Flow is explicit (pipeline table is optional)
You don’t need a full workflow-table engine. For small projects:
- a **single `pipeline.py`** with step functions is enough.
- if flow gets complicated, add a small `workflow.yaml` later.

### R4. Every new Atom has a unit test
Minimum bar:
- each new atom = at least one test for normal case + one for edge case.

### R5. “Human-owned” files are few but strict
Humans must own:
- `README.md` usage contract (CLI flags / GUI behavior / examples)
- public API surface (`__init__.py` exports / CLI commands)
- core data types (`types.py`) and invariants

AI can generate:
- atoms/molecules implementations
- orchestration code
- most unit tests (humans review)

---

## 3) Recommended Directory Layout (Small Project)

Example package name: `mytool`

```
mytool/
├─ README.md
├─ pyproject.toml
├─ src/
│  └─ mytool/
│     ├─ __init__.py              # public exports (human-owned)
│     ├─ __main__.py              # entry router (CLI/GUI fallback)
│     ├─ entry/                   # IO boundary
│     │  ├─ cli.py
│     │  └─ gui.py                # optional
│     ├─ orchestration/           # explicit flow
│     │  ├─ pipeline.py
│     │  └─ services.py           # optional: higher-level helpers
│     ├─ core/                    # pure logic
│     │  ├─ types.py
│     │  ├─ atoms/
│     │  │  ├─ matching.py
│     │  │  ├─ bg_remove.py
│     │  │  └─ alignment.py
│     │  └─ molecules/            # optional
│     │     └─ process_job.py
│     └─ infra/                   # optional: side-effect adapters
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

### Naming conventions (Lite)
- Atoms: pure functions; avoid “Manager/Helper/Utils”.
- Orchestration: use `pipeline`, `usecase`, or verb-based modules (`process.py`).
- Infra: adapters to the outside world (filesystem, multiprocessing, HTTP, GPU).

---

## 4) How to Apply This to an Existing “README-level” Tool Repo

A typical small tool often already has:
- CLI commands
- a GUI entry
- a core processing pipeline
- a few algorithm modules

That maps neatly to Lite layers:

- `__main__.py` → **Entry router**
- `cli.py`, `gui.py` → **Entry**
- `pipeline.py` → **Orchestration**
- algorithm modules (`match.py`, `imageops.py`) → **Core atoms/molecules**
- data structures (`cgtypes.py`) → **Core types**
- multiprocess implementation → **Infra** (or orchestration helper)

This exact “entry + pipeline + core modules + types + cli/gui” style is a good target for small projects.  
(Your README already describes this kind of internal structure and module split, which is what Lite V1 standardizes.)

---

## 5) “Workflow Table” — When to Add It

Start without it.

Add `workflow.table.yaml` only if you hit any of these:
- too many `if/else` branches inside `pipeline.py`
- complex rollback/compensation logic
- you need “dry-run”, “interactive confirm”, “resume”, etc. across many steps

Lite table format (optional):

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

## 6) Guardrails for AI-Assisted Implementation

When asking AI to add a feature, always include:
1. **Target file path**
2. **Layer constraint**
   - “This is an Atom. Must not import other atoms. No IO.”
   - “This is orchestration. May call atoms. No CLI parsing here.”
3. **Input/Output contract**
4. **Tests required**

Example instruction snippet:

> Implement `core/atoms/alignment.py::align_fast(base, diff, params)`  
> Constraints: Atom; no filesystem IO; no importing other atoms; deterministic.  
> Add unit tests in `tests/unit/test_alignment.py`.

---

## 7) Refactor Steps (1–2 days plan for a small repo)

1. **Freeze public behavior** (README + CLI args + GUI behavior)
2. Identify modules and tag them:
   - entry / orchestration / core / infra
3. Move code into the Lite layout (minimal moves first)
4. Add unit tests for the atoms you touch during refactor
5. Add a simple import rule check (optional):
   - fail CI if `core` imports `entry`/`orchestration`

---

## 8) Definition of Done (Lite)

A feature PR is done when:
- [ ] Entry only parses IO and calls orchestration
- [ ] Orchestration reads like an explicit step flow
- [ ] Core atoms are test-covered
- [ ] No forbidden imports (core stays pure)

---

## Version
- Lite V1 is intentionally small and pragmatic.
- Upgrade path to “Full V1”:
  - add bounded contexts if project grows
  - add workflow tables for complex flows
  - add ports/adapters if external dependencies multiply
