[English](README.md) | 中文
# FailCore —— AI Agent 的「安全气囊」执行运行时

> **AI Agent 的执行安全气囊（Safety Airbag）** 🛡️  
> **状态：** Beta（0.1.x） · **安装：** `pip install failcore` · **许可证：** Apache 2.0

[![PyPI version](https://badge.fury.io/py/failcore.svg)](https://badge.fury.io/py/failcore)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**当 Agent 出问题时，你不需要更好的 Prompt ——你需要一个“断路器”。**

FailCore 是一个 **为 AI Agent 设计的 fail-fast 执行运行时（execution runtime）**。  
它并不试图让 Agent 变得更“聪明”，而是让 Agent 在真实系统中 **安全、可控、可回放地执行**。

当 LangChain 等框架关注 *规划（planning）* 与 *推理（reasoning）* 时，  
FailCore 专注于 **执行阶段真正发生的事情**：

- 工具是否被正确调用？
- 是否发生了越权或危险的副作用？
- 失败发生在“执行前”还是“执行中”？
- 能否在不重跑整个流程的情况下复现问题？

FailCore 位于 **Agent 技术栈最底层的执行安全层（Execution Safety Layer）**。

---

## ▶️ 执行阶段安全拦截（实时演示）

FailCore 在 **工具调用（tool invocation）阶段** 强制执行安全策略，  
在任何网络或文件系统副作用发生之前完成拦截。

<p align="center">
  <img src="./assets/gif/2025_12_25_demo.gif" width="820" />
</p>

> 演示内容：  
> Agent 试图访问云元数据与内网地址（SSRF），  
> FailCore 在执行前阻断请求，并生成完整执行轨迹（trace）。

---

## 📸 实际效果（审计报告）

FailCore 会为 **每一次 Agent 运行自动生成审计（Audit）HTML 报告**。  

```bash
failcore show
failcore audit --html > audit.html
```
![FailCore Audit Report](/assets/images/audit.jpeg)

---

## ✨ 核心能力（v0.1.x）

- 🛡️ **SSRF 防护**  
  网络层校验（DNS 解析 + 私有 IP 检测），阻止访问内网与元数据服务。

- 📂 **文件系统沙箱**  
  自动检测并阻止 `../` 路径穿越等越权文件访问。

- 📊 **取证级审计报告**  
  一条命令生成可读性极强的 HTML 执行与安全分析报告。

- 🎯 **语义化执行状态**  
  明确区分：  
  - `BLOCKED`：威胁被成功阻止（安全成功）  
  - `FAIL`：工具自身执行失败（逻辑错误）

---

## 🔥 快速开始

### 1. 安装

```bash
pip install failcore
```

### 2. 零侵入保护你的工具

将你现有的函数（或 LangChain 工具）包裹进 FailCore 的 Session 中。

```python
from failcore import Session, presets

session = Session(
    validator=presets.fs_safe(strict=True),
    sandbox="./workspace"
)

@session.tool
def write_file(path: str, content: str):
    with open(path, "w") as f:
        f.write(content)

# —— 模拟：LLM 试图发起攻击 ——
result = session.call("write_file", path="../etc/passwd", content="hack")

print(result.status)        # e.g. BLOCKED
print(result.error.message) # Path traversal detected
```

FailCore 会在 **执行前** 拦截该操作，原始函数 **不会被调用**。

---

### 3. 生成报告

```bash
failcore show
failcore report --last > report.html
```
（下图展示：LLM 生成了路径穿越攻击，而 FailCore 在执行前将其拦截）
![FailCore Forensic Report](/assets/images/report_screenshot.png)

> 报告中的执行失败记录表明：  
> Agent 曾试图执行未授权操作，并在 *执行阶段的验证层* 被 FailCore 拦截，  
> 相关时间线、事件分析与 Trace 证据已完整保留，便于事后检查与复现。

---

## 为什么需要 FailCore？

现代 AI Agent 在生产环境中非常脆弱：

| 风险 | 没有 FailCore | 使用 FailCore |
|-----|---------------|---------------|
| **SSRF / 内网访问** | Agent 可能访问云元数据服务 | **BLOCKED**（执行前拦截） |
| **文件系统越权** | 任意 `../` 读写真实文件 | **BLOCKED**（沙箱边界） |
| **成本** | 一步失败，整个流程重跑 | **确定性回放** 已成功步骤 |
| **可见性** | 大量日志，难以定位 | **取证报告** 一眼定位原因 |

FailCore 把“不可控的失败”变成 **可解释、可复现、可审计的事件**。

---

## LangChain 集成示例

无需重写工具，只需在执行层加一层 FailCore：

```python
from failcore import Session, presets
from failcore.adapters.langchain import map_langchain_tool

session = Session(validator=presets.fs_safe(strict=True))

safe_tool_spec = map_langchain_tool(my_langchain_tool)
session.invoker.register_spec(safe_tool_spec)
```

---

## FailCore 不是什么

FailCore **不是**：

- Agent 框架
- Planner / 任务分解系统
- Memory 系统
- 可观测性 SaaS

它只负责一件事：

> **确保 Agent 的执行过程是安全的、可解释的、可回放的。**

---

## 参与贡献

欢迎 Issue 与 PR。  
如果你正在构建对执行安全、审计和复现有要求的 Agent 系统，非常欢迎交流。

---

## 许可证

本项目基于 **Apache License 2.0** 发布。  
详见 [LICENSE](LICENSE)。

Copyright © 2025 ZiLing
