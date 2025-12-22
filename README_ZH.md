[English](README.md) | 中文
# FailCore —— AI Agent 的确定性执行运行时

> **状态：** Beta（0.1.x） · 已发布至 PyPI · 内置 CLI  
> 安装：`pip install failcore` · 体验：`failcore sample`

> *“成功有很多父亲，失败却有自己的核心。”*

FailCore 是一个 **为 AI Agent 设计的 fail-fast 执行运行时（execution runtime）**。

它并不试图让 Agent 变得更“聪明”，而是让 Agent 的 **执行过程变得可靠、可审计、可复现**。

大多数 Agent 框架关注的是 *规划（planning）* 和 *推理（reasoning）*；  
FailCore 关注的是 **计划生成之后发生了什么**：

- 工具是否被正确调用？
- 为什么失败？
- 是否可以跳过已成功的步骤？
- 能否在不重跑整个流程的情况下复现问题？

FailCore 专注于 **执行层（execution layer）**。

---

## 为什么需要 FailCore？

现实中的 Agent 系统往往运行在一种“尽力而为”的状态下：

- **失败代价高**  
  一个 10 步的任务在第 9 步失败，通常需要从头再来。

- **执行不可见**  
  Agent 出错时，很难回答：到底调用了什么？参数是什么？

- **权限风险大**  
  没有原子级拦截时，Agent 的错误行为可能直接影响真实系统。

FailCore 的角色是：

> **当 Agent 行为失控或不可解释时，你唯一能信任的执行黑匣子（Black Box）。**

它既是 **飞行记录仪**，也是 **安全气囊**。

---

## 快速开始

### 安装

```bash
pip install failcore
```

### 运行内置示例

```bash
failcore sample
failcore show
```

该示例演示了：

1. **策略拦截（Policy Gate）** —— 阻止越权或危险操作  
2. **输出契约漂移检测** —— 检测 TEXT / JSON 不匹配  
3. **执行回放（Replay）** —— 从 trace 中进行离线复现  

---

## 一个真实的失败场景

假设一个 Agent 执行 10 个步骤：

- 第 9 步失败
- 前 8 步其实已经成功

### 没有 FailCore
- 整个流程从头重跑
- 所有工具再次执行
- 难以复现和定位问题

### 使用 FailCore
- 步骤 1–8 从 trace 中直接回放（HIT / SKIP）
- 只重新执行失败步骤
- 所有输入 / 输出可离线分析

---

## 核心能力

- **确定性回放（Deterministic Replay）**  
  已成功的步骤可直接从 trace 中复用，避免重复执行。

- **审计级 Trace 记录**  
  以 append-only JSONL 形式记录每一次工具调用的输入、输出、耗时和失败类型。

- **执行护栏（Policy Gate）**  
  在执行前拦截危险或非法操作。

- **输出契约校验**  
  将“模型输出漂移”转化为机器可识别的失败类型。

- **框架无关**  
  可嵌入 LangChain、AutoGen、CrewAI 或自定义 Agent 运行时。

---

## 执行模型：Black Box 协议

FailCore 遵循严格的 **Verify → Run** 生命周期：

1. **Resolve**：为当前步骤生成确定性指纹  
2. **Validate**：执行前进行策略与不变量校验  
3. **Execute**：仅在无成功记录时才执行  
4. **Commit**：将结果写入持久化 trace  

这一模型确保：
- 可复现
- 可审计
- 可跳过已成功执行

---

## FailCore 不是什么

FailCore **不是**：

- Agent 框架  
- Planner / 任务分解系统  
- Memory 系统  
- 可观测性 SaaS  

它只做一件事：

> **确保 Agent 的执行过程是安全、可解释、可回放的。**

---

## 适合谁使用？

- 正在构建 **生产级 Agent 系统** 的工程师  
- 需要 **调试复杂执行链路** 的团队  
- 对 Agent **权限边界和审计** 有要求的场景  
- 需要在失败发生后 **定位责任与因果关系** 的系统  

---

## 参与贡献

欢迎 Issue 与 PR。  
如果你正在构建需要更强执行保障的 Agent 系统，非常欢迎交流反馈。

---

## 许可证

本项目基于 **Apache License 2.0** 发布。  
详见 [LICENSE](LICENSE)。

Copyright © 2025 ZiLing
