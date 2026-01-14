# 部署模式

本指南介绍在生产环境中部署和使用 FailCore 的不同方式。

---

## 概述

FailCore 支持两种主要的部署模式：

1. **代理模式** - 透明拦截 LLM API 调用
2. **运行时模式** - 直接集成到应用程序代码中

---

## 代理模式（推荐）

代理模式是生产环境推荐的部署方式。FailCore 作为本地代理服务器运行，拦截 LLM API 请求。

### 架构

```
[您的应用程序]
        |
        v
[FailCore 代理] ← 执行检查点
        |
        v
[LLM 提供商 API]
```

### 优势

- ✅ **零代码更改** - 适用于任何 LLM SDK
- ✅ **透明拦截** - 所有工具调用自动追踪
- ✅ **生产就绪** - 专为高吞吐量场景设计
- ✅ **成本控制** - 实时预算执行
- ✅ **流式保护** - 流式传输期间的 DLP 检测

### 设置

1. **安装代理依赖：**

```bash
pip install "failcore[proxy]"
```

2. **启动代理服务器：**

```bash
failcore proxy --listen 127.0.0.1:8000
```

3. **配置您的 LLM 客户端：**

```python
# OpenAI SDK 示例
import openai

client = openai.OpenAI(
    base_url="http://127.0.0.1:8000/v1",  # 通过 FailCore 路由
    api_key="your-api-key"
)

# 所有请求现在都受到保护
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}]
)
```

### 配置

代理模式支持各种配置选项：

```bash
failcore proxy \
    --listen 127.0.0.1:8000 \
    --upstream https://api.openai.com/v1 \
    --mode strict \
    --budget 10.0
```

**选项：**
- `--listen`: 代理服务器地址（默认：127.0.0.1:8000）
- `--upstream`: 上游 LLM 提供商 URL
- `--mode`: 安全模式（`warn` 或 `strict`）
- `--budget`: 最大成本（美元）

---

## 运行时模式

运行时模式使用 `run()` 上下文管理器将 FailCore 直接集成到应用程序代码中。

### 架构

```
[您的应用程序代码]
        |
        v
[FailCore 运行时] ← 策略执行
        |
        v
[工具执行]
```

### 优势

- ✅ **细粒度控制** - 每次运行的策略配置
- ✅ **显式工具注册** - 清晰可见的受保护工具
- ✅ **灵活集成** - 适用于任何 Python 代码
- ✅ **开发友好** - 易于测试和调试

### 设置

1. **安装 FailCore：**

```bash
pip install failcore
```

2. **在代码中使用：**

```python
from failcore import run, guard

with run(policy="fs_safe", sandbox="./data") as ctx:
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    # 受保护的执行
    write_file("test.txt", "Hello, FailCore!")
```

### 配置

运行时模式支持广泛的配置：

```python
with run(
    policy="fs_safe",
    sandbox="./workspace",
    trace="custom_trace.jsonl",
    strict=True,
    max_cost_usd=5.0,
    max_tokens=10000
) as ctx:
    # 您的代码
    pass
```

---

## 混合方法

您可以组合两种模式：

- **代理模式**用于 LLM API 调用
- **运行时模式**用于自定义工具执行

示例：

```python
# 代理处理 LLM 调用
# 运行时处理自定义工具

from failcore import run, guard

# LLM 调用通过代理（单独配置）
# 自定义工具使用运行时模式

with run(policy="fs_safe") as ctx:
    @guard()
    def custom_tool(data: str):
        # 自定义逻辑
        pass
    
    custom_tool("data")
```

---

## 生产考虑

### 性能

- **代理模式**：最小开销（每个请求 < 1ms）
- **运行时模式**：策略检查每个工具调用增加 < 1ms

### 可扩展性

- **代理模式**：可处理高吞吐量场景
- **运行时模式**：适用于中等工作负载

### 监控

两种模式都生成追踪文件用于事后分析：

```bash
# 查看追踪
failcore list

# 生成报告
failcore report trace.jsonl
```

---

## 下一步

- [配置参考](../reference/configuration.md) - 详细配置选项
- [故障排除](../operations/troubleshooting.md) - 常见问题和解决方案
- [集成](../integrations/overview.md) - 框架集成
