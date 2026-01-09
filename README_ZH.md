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

## 🧪 实验性功能：Proxy 模式（Pre-release）

FailCore 正在开发 **实验性的 Proxy 模式**，并通过 GitHub **Pre-release** 提供。  

Proxy 以轻量网关的形式运行在客户端与模型服务之间，**透明转发请求**，同时在运行时对请求与响应进行观测与追踪。该模式支持流式（Streaming）响应，是未来执行期策略拦截、审计与回放能力的基础。

> Proxy 模式仍处于实验阶段，接口与行为可能发生变化，不建议用于生产环境。

---

## 💰 Cost 相关能力（早期阶段）

FailCore 正在探索 **执行期成本信息的提取与追踪**，以支持更好的可观测性与审计能力。  
当前阶段以 **正确性与可追溯性** 为目标，相关设计仍在演进中。

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

---

## 许可证

本项目基于 **Apache License 2.0** 发布。  
详见 [LICENSE](LICENSE)。

Copyright © 2025 ZiLing
