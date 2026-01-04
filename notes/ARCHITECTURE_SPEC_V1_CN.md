# AI-Native PCT Trinity Architecture Specification (V1.0)

## 1. 核心设计哲学 (Core Philosophy)

本架构专为 **AI 自动编程 (AI Coding)** 设计，而非传统的人类协作模式。核心原则如下：

1. **上下文隔离 (Context Isolation)**：每个功能模块（Capsule）必须是“无状态”、“无外部依赖”的孤岛。AI 修改任何模块时，**不需要**阅读项目其他部分的代码。
2. **配置驱动流程 (Configuration Over Logic)**：业务逻辑的流转由 L2 层的 YAML/JSON 配置决定，严禁在代码中硬编码调用链。
3. **三位一体 (The Trinity)**：每个功能单元必须包含 **Spec (定义)**、**Impl (实现)**、**Test (验证)** 三个物理文件，缺一不可。

---

## 2. 项目目录结构 (Directory Structure)

采用 **“总线-胶囊”** 式拓扑结构，而非层级结构。

```text
Project_Root/
├── main.py                  # [L1] 入口文件：只负责启动引擎，加载流程
├── config/
│   └── workflows/           # [L2] 编排层：定义业务流程的 YAML 文件
│       └── process_data.yaml
├── core/                    # [Infrastructure] 基础设施（人类维护/一次性写入）
│   ├── engine.py            # 流程执行引擎（解析 YAML -> 调度胶囊）
│   └── blackboard.py        # 数据黑板（全局上下文容器）
└── capsules/                # [L3/L4] 功能胶囊库（AI 的主要工作区）
    ├── __init__.py
    ├── text_cleaner/        # <--- 一个标准的胶囊 (Capsule)
    │   ├── spec.md          # [Prompt] 自然语言描述输入、输出、逻辑
    │   ├── impl.py          # [Code] 纯函数实现，禁止 import 同级胶囊
    │   └── test.py          # [Test] 针对 impl.py 的单元测试
    └── url_fetcher/
        ├── spec.md
        ├── impl.py
        └── test.py
```

---

## 3. 层级详细规范 (Layer Specifications)

### L1: 入口层 (Entry Layer)

* **职责**：程序的起点，仅用于接收用户意图并启动 `Core Engine`。
* **规则**：

  * 禁止包含任何业务逻辑。
  * 代码行数不超过 20 行。
* **代码示例 (`main.py`)**:

  ```python
  from core.engine import WorkflowEngine

  if __name__ == "__main__":
      # 用户意图：执行“数据处理”流程
      engine = WorkflowEngine()
      # 初始参数放入黑板
      initial_context = {"target_url": "https://example.com"}
      # 运行 L2 定义的流程
      result = engine.run(workflow="config/workflows/process_data.yaml", context=initial_context)
      print("Final Result:", result)
  ```

### L2: 编排层 (Orchestration Layer)

* **职责**：定义“谁在什么时候做什么”。相当于电路板的布线。
* **格式**：推荐 **YAML** (对 Token 消耗少，AI 易读)。
* **核心概念**：

  * `step`: 步骤名称。
  * `capsule`: 调用哪个胶囊（文件夹名）。
  * `inputs`: 从黑板（Blackboard）取什么数据映射给函数参数。
  * `outputs`: 函数返回值存入黑板的哪个 Key。
* **配置示例 (`config/workflows/process_data.yaml`)**:

  ```yaml
  name: "URL Content Processing Flow"
  steps:
    - step_name: "Download Page"
      capsule: "url_fetcher"          # 对应 capsules/url_fetcher/
      inputs:
        url: "target_url"             # 将黑板中的 target_url 传给函数参数 url
      outputs:
        html_content: "raw_html"      # 将函数返回值存入黑板的 raw_html

    - step_name: "Clean Content"
      capsule: "text_cleaner"
      inputs:
        text: "raw_html"
      outputs:
        clean_text: "final_summary"
  ```

### L3/L4: 功能胶囊层 (Functional Capsules)

这是 AI 工作的核心区域。每个文件夹代表一个原子能力。

#### 3.1 胶囊铁律 (Capsule Strict Rules)

1. **零依赖 (Zero Dependency)**：`impl.py` **严禁** import `capsules` 目录下的其他模块。只能 import 标准库或第三方通用库（如 `requests`, `pandas`）。
2. **纯函数 (Pure Function)**：输入必须全部来自参数，输出必须全部通过 return。禁止读写全局变量。
3. **伴生测试 (Test Co-location)**：修改代码前必须先运行测试；修改代码后必须更新测试。

#### 3.2 胶囊文件详解

**A. `spec.md` (说明书/Prompt)**
AI 在写代码前必须先阅读或生成此文件。

```markdown
# Capsule: URL Fetcher

## 描述
下载指定 URL 的网页内容。

## 输入 (Inputs)
- `url` (str): 目标网站的地址。

## 输出 (Outputs)
- `content` (str): 网页的 HTML 文本。如果不成功则返回空字符串。

## 约束
- 超时时间设置为 5 秒。
- 需要处理 NetworkException。
```

**B. `impl.py` (实现代码)**

```python
import requests

def run(url: str) -> str:
    """
    对应 spec.md 的实现
    """
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""
```

**C. `test.py` (验证代码)**

```python
import unittest
from unittest.mock import patch
# 引用同目录下的实现
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

## 4. 基础设施层 (Infrastructure Core)

此部分代码通常固定，不需要 AI 频繁修改。

* **黑板 (Blackboard)**：本质是一个 `Dict[str, Any]`。
* **引擎 (Engine)**：

  1. 读取 YAML。
  2. 循环遍历 Steps。
  3. 动态 Import `capsules.{capsule_name}.impl`。
  4. 从黑板提取 `inputs` 对应的值。
  5. 执行函数。
  6. 将结果写入黑板 `outputs` 对应的 Key。

---

## 5. AI 开发工作流 (AI Workflow)

当你（User）要求 AI 开发一个新功能时，请遵循以下 SOP：

1. **定义阶段**：

   * 用户：“我要一个从 PDF 提取表格并存为 CSV 的功能。”
   * AI (L2 Agent)：创建/更新 `workflow.yaml`，定义两个胶囊：`pdf_parser` 和 `csv_saver`。

2. **胶囊生成阶段**（对每个胶囊循环）：

   * **Step 1 Spec**: AI 创建 `capsules/pdf_parser/spec.md`。
   * **Step 2 Test**: AI 根据 Spec 编写 `capsules/pdf_parser/test.py` (此时运行会报错，因为没实现)。
   * **Step 3 Code**: AI 编写 `capsules/pdf_parser/impl.py` 直到 `test.py` 通过。

3. **组装运行**：

   * 运行 `main.py`。由于每个胶囊都已通过单元测试，且 L2 逻辑只是数据流转，系统集成 Bug 率极低。

---

## 6. 总结 (Summary)

* **调试 Bug**：若报错，只需看 L2 确定是哪个胶囊，然后进入该胶囊文件夹单独调试。
* **增加功能**：增加新的胶囊文件夹 + 修改 YAML。不影响旧代码。
* **AI 友好度**：⭐⭐⭐⭐⭐ (AI 每次只需关注 3 个小文件，无需理解全项目)。
