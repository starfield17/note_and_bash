# AI-Native PCT Trinity Architecture Specification (V1.0)

## 1. Core Design Philosophy

This architecture is specifically designed for **AI Coding**, not traditional human collaboration patterns. The core principles are:

1. **Context Isolation**: Each functional module (Capsule) must be a "stateless" and "no external dependency" island. When AI modifies any module, it **does not need** to read code from other parts of the project.
2. **Configuration Over Logic**: Business logic flow is determined by YAML/JSON configurations in the L2 layer; hardcoding call chains in code is strictly prohibited.
3. **The Trinity**: Each functional unit must contain three physical files: **Spec (Definition)**, **Impl (Implementation)**, and **Test (Verification)**—none of which can be omitted.

---

## 2. Project Directory Structure

Adopt a **"Bus-Capsule"** topology structure instead of a hierarchical structure.

```text
Project_Root/
├── main.py                  # [L1] Entry point: only responsible for starting the engine and loading workflows
├── config/
│   └── workflows/           # [L2] Orchestration layer: YAML files defining business processes
│       └── process_data.yaml
├── core/                    # [Infrastructure] Infrastructure (human-maintained / write-once)
│   ├── engine.py            # Workflow execution engine (parses YAML -> dispatches capsules)
│   └── blackboard.py        # Data blackboard (global context container)
└── capsules/                # [L3/L4] Functional capsule library (AI's main workspace)
    ├── __init__.py
    ├── text_cleaner/        # <--- A standard capsule
    │   ├── spec.md          # [Prompt] Natural language description of inputs, outputs, and logic
    │   ├── impl.py          # [Code] Pure function implementation; importing sibling capsules is forbidden
    │   └── test.py          # [Test] Unit tests for impl.py
    └── url_fetcher/
        ├── spec.md
        ├── impl.py
        └── test.py
```

---

## 3. Layer Specifications

### L1: Entry Layer

* **Responsibility**: The starting point of the program, used only to receive user intent and trigger the `Core Engine`.
* **Rules**:
  * Must not contain any business logic.
  * Code must not exceed 20 lines.
* **Code Example (`main.py`)**:

  ```python
  from core.engine import WorkflowEngine

  if __name__ == "__main__":
      # User intent: execute "data processing" workflow
      engine = WorkflowEngine()
      # Initial parameters placed on the blackboard
      initial_context = {"target_url": "https://example.com"}
      # Execute the workflow defined in L2
      result = engine.run(workflow="config/workflows/process_data.yaml", context=initial_context)
      print("Final Result:", result)
  ```

### L2: Orchestration Layer

* **Responsibility**: Defines "who does what at when". Equivalent to the wiring on a circuit board.
* **Format**: **YAML** is recommended (lower token consumption, AI-friendly readability).
* **Core Concepts**:
  * `step`: Step name.
  * `capsule`: Which capsule to invoke (folder name).
  * `inputs`: What data to retrieve from the Blackboard and map to function parameters.
  * `outputs`: Where to store function return values in the Blackboard.
* **Configuration Example (`config/workflows/process_data.yaml`)**:

  ```yaml
  name: "URL Content Processing Flow"
  steps:
    - step_name: "Download Page"
      capsule: "url_fetcher"          # Corresponds to capsules/url_fetcher/
      inputs:
        url: "target_url"             # Passes target_url from blackboard to function parameter url
      outputs:
        html_content: "raw_html"      # Stores function return value in blackboard's raw_html

    - step_name: "Clean Content"
      capsule: "text_cleaner"
      inputs:
        text: "raw_html"
      outputs:
        clean_text: "final_summary"
  ```

### L3/L4: Functional Capsules Layer

This is the core area where AI works. Each folder represents an atomic capability.

#### 3.1 Capsule Strict Rules

1. **Zero Dependency**: `impl.py` is **strictly forbidden** from importing other modules under the `capsules` directory. Only standard library or general third-party libraries (such as `requests`, `pandas`) may be imported.
2. **Pure Function**: All inputs must come from parameters, and all outputs must be returned via `return`. Reading/writing global variables is prohibited.
3. **Test Co-location**: Tests must be run before modifying code; tests must be updated after modifying code.

#### 3.2 Capsule File Details

**A. `spec.md` (Specification/Prompt)**
AI must read or generate this file before writing code.

```markdown
# Capsule: URL Fetcher

## Description
Downloads the webpage content from a specified URL.

## Inputs
- `url` (str): The address of the target website.

## Outputs
- `content` (str): The HTML text of the webpage. Returns an empty string if unsuccessful.

## Constraints
- Timeout set to 5 seconds.
- Must handle NetworkException.
```

**B. `impl.py` (Implementation Code)**

```python
import requests

def run(url: str) -> str:
    """
    Implementation corresponding to spec.md
    """
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""
```

**C. `test.py` (Verification Code)**

```python
import unittest
from unittest.mock import patch
# Import implementation from the same directory
from . import impl

class TestUrlFetcher(unittest.TestCase):
    @patch('requests.get')
    def test_success(self, mock_get):
        mock_get.return_value.text = "<html></html>"
        mock_get.return_value.status_code = 200
      
        result = impl.run("http://test.com")
        self.assertEqual(result, "<html></html>")

if __name__ == '__main__':
    unittest.main()
```

---

## 4. Infrastructure Core

This section of code is typically stable and does not require frequent modifications by AI.

* **Blackboard**: Essentially a `Dict[str, Any]`.
* **Engine**:
  1. Reads YAML.
  2. Iterates through Steps.
  3. Dynamically imports `capsules.{capsule_name}.impl`.
  4. Extracts values corresponding to `inputs` from the Blackboard.
  5. Executes the function.
  6. Writes results to the `outputs` keys in the Blackboard.

---

## 5. AI Development Workflow

When you (User) ask AI to develop a new feature, please follow this SOP:

1. **Definition Phase**:
   * User: "I need a feature to extract tables from PDF and save them as CSV."
   * AI (L2 Agent): Creates/updates `workflow.yaml`, defining two capsules: `pdf_parser` and `csv_saver`.

2. **Capsule Generation Phase** (loop for each capsule):
   * **Step 1 Spec**: AI creates `capsules/pdf_parser/spec.md`.
   * **Step 2 Test**: AI writes `capsules/pdf_parser/test.py` based on Spec (will error on execution since implementation is missing).
   * **Step 3 Code**: AI writes `capsules/pdf_parser/impl.py` until `test.py` passes.

3. **Assembly and Execution**:
   * Run `main.py`. Since each capsule has passed unit tests and L2 logic is merely data flow, system integration bug rate is extremely low.

---

## 6. Summary

* **Debugging Bugs**: If an error occurs, simply check L2 to identify which capsule is at fault, then enter that capsule's folder for individual debugging.
* **Adding Features**: Add a new capsule folder + modify YAML. Does not affect existing code.
* **AI Friendliness**: ⭐⭐⭐⭐⭐ (AI only needs to focus on 3 small files each time, with no need to understand the entire project).