# 集成概述

FailCore 与流行的 LLM 框架和协议集成，提供执行时安全。

---

## 支持的集成

FailCore 目前支持：

1. **LangChain** - LangChain 工具和代理集成
2. **MCP** - Model Context Protocol 支持

---

## 集成理念

FailCore 的集成方法遵循以下原则：

### 执行主权

- FailCore 控制**执行**，而不是规划
- 所有工具调用都通过 FailCore 的验证引擎
- 框架提供工具定义，FailCore 强制执行安全

### 零破坏性更改

- 集成是**增量的**，不是替换
- 现有代码继续工作
- FailCore 在不改变行为的情况下增加安全性

### 透明保护

- 工具调用自动受到保护
- 无需为每个工具手动配置策略
- 策略统一应用于所有工具

---

## LangChain 集成

FailCore 提供与 LangChain 工具和代理的无缝集成。

**功能：**
- 自动 LangChain 工具检测
- BaseTool 兼容性用于代理
- 完整的异步支持
- 参数模式保留

**参见：** [LangChain 集成](langchain.md)

---

## MCP 集成

FailCore 支持 Model Context Protocol (MCP) 用于远程工具执行。

**功能：**
- MCP 客户端实现
- MCP 工具的策略保护
- SSRF 和网络安全
- 远程调用的成本追踪

**参见：** [MCP 集成](mcp.md)

---

## 选择集成

### 使用 LangChain 集成当：

- 您使用 LangChain 代理
- 您需要 BaseTool 兼容性
- 您想要自动工具检测

### 使用 MCP 集成当：

- 您使用 MCP 服务器
- 您需要远程工具执行
- 您想要协议级保护

### 同时使用当：

- 您有混合架构
- 某些工具是本地的（LangChain），其他是远程的（MCP）

---

## 下一步

- [LangChain 集成](langchain.md) - LangChain 特定指南
- [MCP 集成](mcp.md) - MCP 特定指南
- [部署模式](../getting-started/deployment-patterns.md) - 如何部署
