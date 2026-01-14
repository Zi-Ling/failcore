# 故障排除

使用 FailCore 时的常见问题和解决方案。

---

## 安装问题

### 导入错误

**问题：** `ImportError: cannot import name 'run' from 'failcore'`

**解决方案：**

```bash
# 重新安装 FailCore
pip install --upgrade failcore
```

### 缺少依赖

**问题：** `ModuleNotFoundError: No module named 'langchain_core'`

**解决方案：**

```bash
# 安装所需依赖
pip install "failcore[langchain]"
```

---

## 运行时问题

### 策略未找到

**问题：** `ValueError: Failed to load policy 'custom'`

**解决方案：**

1. 检查策略文件存在：`.failcore/validate/custom.yaml`
2. 验证 YAML 语法正确
3. 检查策略名称是否与文件名匹配

```python
# 列出可用策略
from failcore.core.validate.templates import list_policies
print(list_policies())
```

### 路径解析错误

**问题：** `PathError: Path outside allowed roots`

**解决方案：**

```python
# 使用白名单允许外部路径
from pathlib import Path

with run(
    sandbox="/tmp/external",
    allow_outside_root=True,
    allowed_sandbox_roots=[Path("/tmp")]
) as ctx:
    pass
```

### 工具未注册

**问题：** `ToolNotFoundError: Tool 'my_tool' not found`

**解决方案：**

```python
# 在调用前注册工具
with run(policy="safe") as ctx:
    ctx.tool(my_tool)  # 首先注册
    ctx.call("my_tool", arg=123)  # 然后调用
```

或使用 `@guard()` 装饰器：

```python
with run(policy="safe") as ctx:
    @guard()
    def my_tool(arg: int):
        pass
    
    my_tool(123)  # 自动注册
```

---

## 策略问题

### 过于严格

**问题：** 合法操作被阻止

**解决方案：**

1. 使用 `shadow` 模式观察：

```python
with run(policy="shadow") as ctx:
    # 记录决策但不阻止
    pass
```

2. 调整验证器操作：

```yaml
# .failcore/validate/custom.yaml
validators:
  - name: security_path_traversal
    action: WARN  # 警告而不是阻止
```

### 不够严格

**问题：** 不安全操作被允许

**解决方案：**

1. 使用 `strict` 模式：

```python
with run(policy="fs_safe", strict=True) as ctx:
    pass
```

2. 将验证器设置为 `BLOCK`：

```yaml
validators:
  - name: security_path_traversal
    action: BLOCK  # 阻止而不是警告
```

---

## 代理问题

### 连接被拒绝

**问题：** `ConnectionRefusedError: [Errno 111] Connection refused`

**解决方案：**

1. 检查代理是否运行：

```bash
failcore proxy --listen 127.0.0.1:8000
```

2. 验证客户端配置：

```python
client = openai.OpenAI(
    base_url="http://127.0.0.1:8000/v1",  # 正确的 URL
    api_key="your-key"
)
```

### 上游超时

**问题：** 请求到上游提供商超时

**解决方案：**

在代理配置中增加超时：

```python
from failcore.core.config.proxy import ProxyConfig

config = ProxyConfig(
    upstream_timeout_s=120.0  # 增加超时
)
```

---

## 集成问题

### LangChain 工具未检测到

**问题：** LangChain 工具未自动检测

**解决方案：**

显式映射工具：

```python
from failcore.adapters.langchain import map_langchain_tool

with run(policy="safe") as ctx:
    spec = map_langchain_tool(lc_tool, risk="low")
    ctx.tool(spec)
```

### MCP 服务器未启动

**问题：** MCP 传输无法连接

**解决方案：**

1. 检查服务器命令是否在 PATH 中：

```python
mcp_config = McpTransportConfig(
    session=McpSessionConfig(
        command="npx",  # 验证命令存在
        args=["-y", "@modelcontextprotocol/server-filesystem", "/path"]
    )
)
```

2. 检查服务器日志中的错误

---

## 性能问题

### 执行缓慢

**问题：** 策略检查增加显著开销

**解决方案：**

1. 策略检查通常 < 1ms
2. 如果缓慢，检查：
   - 大型策略文件
   - 复杂的验证器逻辑
   - 验证器中的网络调用

### 内存使用

**问题：** 高内存使用

**解决方案：**

1. 限制追踪文件大小：

```python
with run(trace=None) as ctx:  # 禁用追踪
    pass
```

2. 减少追踪队列大小（代理模式）：

```python
config = ProxyConfig(
    trace_queue_size=1000  # 减少队列大小
)
```

---

## 追踪问题

### 追踪文件未找到

**问题：** `FileNotFoundError: trace.jsonl`

**解决方案：**

1. 检查追踪路径：

```python
with run(trace="auto") as ctx:
    print(ctx.trace_path)  # 验证路径
```

2. 使用绝对路径：

```python
with run(trace="/path/to/trace.jsonl") as ctx:
    pass
```

### 追踪文件损坏

**问题：** 追踪文件中的无效 JSON

**解决方案：**

1. 追踪文件使用 JSONL 格式（每行一个 JSON 对象）
2. 检查文件编码（应为 UTF-8）
3. 验证 JSON 语法：

```bash
# 检查追踪文件
failcore show trace.jsonl
```

---

## 成本追踪问题

### 成本未追踪

**问题：** 成本未出现在报告中

**解决方案：**

1. 确保成本追踪已启用：

```python
with run(max_cost_usd=10.0) as ctx:  # 启用成本追踪
    pass
```

2. 检查追踪文件是否包含成本事件：

```bash
failcore report trace.jsonl --cost
```

### 预算超出

**问题：** `BudgetExceededError: Budget limit reached`

**解决方案：**

1. 增加预算：

```python
with run(max_cost_usd=20.0) as ctx:  # 增加限制
    pass
```

2. 检查当前支出：

```bash
failcore report trace.jsonl --cost
```

---

## 获取帮助

### 调试模式

启用调试日志：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 查看追踪

```bash
# 列出所有追踪
failcore list

# 查看特定追踪
failcore show trace.jsonl

# 生成报告
failcore report trace.jsonl
```

### 检查配置

```python
# 列出可用策略
from failcore.core.validate.templates import list_policies
print(list_policies())

# 检查 FailCore 主目录
from failcore.utils.paths import get_failcore_home
print(get_failcore_home())
```

---

## 下一步

- [配置参考](../reference/configuration.md) - 配置选项
- [常见问题](../appendix/faq.md) - 更多常见问题
