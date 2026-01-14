# LangChain 集成

本指南介绍如何将 FailCore 与 LangChain 工具和代理一起使用。

---

## 概述

FailCore 提供与 LangChain 的无缝集成：

- ✅ 自动 LangChain 工具检测
- ✅ 用于代理的 BaseTool 兼容性
- ✅ 完整的异步支持
- ✅ 参数模式保留
- ✅ 零破坏性更改

---

## 安装

安装 LangChain 支持：

```bash
pip install "failcore[langchain]"
```

这将安装：
- `langchain-core` (>=0.3.0, <2.0.0)

---

## 基本用法

### 方法 1：自动检测（推荐）

FailCore 自动检测 LangChain 工具：

```python
from failcore import run, guard
from langchain_core.tools import tool

@tool
def multiply(x: int) -> int:
    """乘以 2"""
    return x * 2

# guard() 自动检测 LangChain 工具
with run(policy="safe") as ctx:
    safe_tool = guard(multiply, risk="low", effect="read")
    result = safe_tool(x=5)  # ✅ 受保护的执行
```

### 方法 2：代理兼容性

对于 LangChain 代理，使用 `guard_tool()`：

```python
from failcore import run, guard
from failcore.adapters.langchain import guard_tool
from langchain_core.tools import tool

@tool
def write_file(path: str, content: str) -> str:
    """将内容写入文件"""
    with open(path, "w") as f:
        f.write(content)
    return f"已写入 {path}"

with run(policy="fs_safe", sandbox="./data") as ctx:
    # 首先注册工具
    guard(write_file, risk="high", effect="fs")
    
    # 为代理创建 BaseTool 外观
    lc_tool = guard_tool("write_file", description="安全写入文件")
    
    # 与 LangChain 代理一起使用
    from langchain.agents import create_agent
    agent = create_agent(tools=[lc_tool])
    result = agent.invoke({"input": "将 hello 写入 test.txt"})
```

---

## 高级用法

### 自定义工具注册

您可以显式注册工具：

```python
from failcore import run, guard
from failcore.adapters.langchain import map_langchain_tool

@tool
def my_tool(x: int) -> int:
    """我的工具"""
    return x * 2

with run(policy="safe") as ctx:
    # 将 LangChain 工具映射到 ToolSpec
    spec = map_langchain_tool(
        my_tool,
        risk="low",
        effect="read"
    )
    
    # 注册并使用
    ctx.tool(spec)
    result = ctx.call("my_tool", x=5)
```

### 异步支持

FailCore 完全支持异步 LangChain 工具：

```python
from failcore import run, guard
from langchain_core.tools import tool

@tool
async def async_tool(data: str) -> str:
    """异步工具"""
    await asyncio.sleep(0.1)
    return f"已处理: {data}"

async def main():
    with run(policy="safe") as ctx:
        safe_tool = guard(async_tool, risk="low")
        result = await safe_tool(data="test")  # ✅ 异步工作
```

---

## 代理集成

### 创建受保护的代理

```python
from failcore import run, guard
from failcore.adapters.langchain import guard_tool
from langchain.agents import create_agent

@tool
def read_file(path: str) -> str:
    """读取文件内容"""
    with open(path, "r") as f:
        return f.read()

@tool
def write_file(path: str, content: str) -> str:
    """将内容写入文件"""
    with open(path, "w") as f:
        f.write(content)
    return "已写入"

with run(policy="fs_safe", sandbox="./workspace") as ctx:
    # 注册工具
    guard(read_file, risk="low", effect="read")
    guard(write_file, risk="high", effect="fs")
    
    # 创建 BaseTool 外观
    tools = [
        guard_tool("read_file", description="读取文件"),
        guard_tool("write_file", description="写入文件")
    ]
    
    # 使用受保护工具创建代理
    agent = create_agent(tools=tools)
    
    # 代理调用自动受到保护
    result = agent.invoke({
        "input": "读取 config.txt 并写入 backup.txt"
    })
```

### 工具模式保留

在 `run()` 内创建 `guard_tool()` 时，参数模式会被保留：

```python
with run(policy="fs_safe") as ctx:
    guard(write_file, risk="high", effect="fs")
    
    # ✅ 完整模式支持（推荐）
    lc_tool = guard_tool("write_file", description="写入文件")
    # LangChain 可以看到参数类型并验证输入
```

如果在 `run()` 外创建，模式可能受限：

```python
# ⚠️ 模式支持受限
lc_tool = guard_tool("write_file", description="写入文件")

with run(policy="fs_safe") as ctx:
    guard(write_file, risk="high", effect="fs")
    # 工具工作但 AI 代理看不到参数类型
```

**最佳实践：** 始终在 `guard()` 注册后在 `run()` 内创建 `guard_tool()`。

---

## 策略配置

### 每个工具的策略

您可以为每个工具指定策略：

```python
with run(policy="safe") as ctx:
    # 低风险工具
    read_tool = guard(read_file, risk="low", effect="read")
    
    # 高风险工具，严格策略
    write_tool = guard(
        write_file,
        risk="high",
        effect="fs",
        action="block"  # 严格阻止
    )
```

### 上下文级策略

策略应用于上下文中的所有工具：

```python
# 此上下文中的所有工具使用 fs_safe 策略
with run(policy="fs_safe", sandbox="./data") as ctx:
    guard(read_file)
    guard(write_file)
    # 两者都受 fs_safe 保护
```

---

## 错误处理

FailCore 错误与 LangChain 兼容：

```python
from failcore import run, guard
from failcore.core.errors import FailCoreError

@tool
def risky_tool(path: str) -> str:
    """风险操作"""
    pass

try:
    with run(policy="fs_safe", strict=True) as ctx:
        safe_tool = guard(risky_tool, risk="high")
        result = safe_tool(path="/etc/passwd")  # 可能被阻止
except FailCoreError as e:
    print(f"被阻止: {e}")
```

---

## 最佳实践

### 1. 首先注册工具

在创建 `guard_tool()` 之前始终使用 `guard()` 注册工具：

```python
# ✅ 正确
with run(policy="fs_safe") as ctx:
    guard(write_file)  # 首先注册
    lc_tool = guard_tool("write_file")  # 然后创建外观
```

### 2. 使用适当的策略

将策略与工具风险级别匹配：

```python
# 低风险：读取操作
guard(read_file, risk="low", effect="read")

# 高风险：写入操作
guard(write_file, risk="high", effect="fs", action="block")
```

### 3. 保留模式

在 `run()` 内创建 `guard_tool()` 以获得完整模式支持：

```python
# ✅ 推荐
with run(policy="fs_safe") as ctx:
    guard(write_file)
    lc_tool = guard_tool("write_file")  # 完整模式
```

---

## 故障排除

### 工具未检测到

如果 LangChain 工具未自动检测：

```python
# 显式映射工具
from failcore.adapters.langchain import map_langchain_tool

spec = map_langchain_tool(my_tool, risk="low")
ctx.tool(spec)
```

### 模式问题

如果缺少参数模式：

```python
# 在 run() 上下文内创建 guard_tool()
with run(policy="safe") as ctx:
    guard(my_tool)
    lc_tool = guard_tool("my_tool")  # ✅ 模式保留
```

---

## 下一步

- [集成概述](overview.md) - 其他集成
- [配置参考](../reference/configuration.md) - 配置选项
- [策略指南](../concepts/policy.md) - 策略配置
