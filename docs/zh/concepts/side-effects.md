# 副作用

副作用（Side Effects）是 FailCore 追踪和控制的执行结果。

---

## 什么是副作用

副作用是工具执行时对**外部世界**产生的改变：

- 修改文件系统
- 发送网络请求
- 启动进程
- 修改环境变量

**纯函数**（只计算，不改变外部状态）没有副作用。

---

## 副作用类别

FailCore 将副作用分为以下类别：

### 1. 文件系统（FILESYSTEM）

文件系统操作：

- **读取**：`filesystem.read`
  - 读取文件内容
  - 列出目录
  - 检查文件存在

- **写入**：`filesystem.write`
  - 创建文件
  - 修改文件
  - 追加内容

- **删除**：`filesystem.delete`
  - 删除文件
  - 删除目录
  - 清空目录

### 2. 网络（NETWORK）

网络操作：

- **出站**：`network.egress`
  - HTTP/HTTPS 请求
  - WebSocket 连接
  - 套接字连接

- **DNS**：`network.dns`
  - DNS 查询
  - 域名解析

### 3. 进程（PROCESS）

进程操作：

- **启动**：`process.spawn`
  - 创建子进程
  - 执行命令

- **终止**：`process.kill`
  - 终止进程
  - 发送信号

---

## 副作用检测

FailCore 使用**两阶段检测**：

### 阶段 1：预测（Pre-execution）

在执行前，FailCore 分析工具调用：

```python
@guard()
def write_file(path: str, content: str):
    with open(path, "w") as f:
        f.write(content)
```

当调用 `write_file("test.txt", "data")` 时：
- 工具名：`write_file`
- 参数：`{"path": "test.txt", "content": "data"}`
- 预测副作用：`filesystem.write` → `test.txt`

### 阶段 2：观察（Post-execution）

执行后，FailCore 观察实际发生的副作用：

```python
# 实际执行
with open("test.txt", "w") as f:
    f.write("data")

# 观察到的副作用
observed_side_effects = [
    SideEffectEvent(
        type="filesystem.write",
        target="test.txt",
        tool="write_file"
    )
]
```

---

## 副作用记录

所有副作用都记录到追踪文件：

```json
{
  "event": "SIDE_EFFECT",
  "type": "filesystem.write",
  "target": "test.txt",
  "category": "filesystem",
  "tool": "write_file",
  "step_id": "abc123",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### 追踪文件中的副作用

```jsonl
{"event": "STEP_START", "tool": "write_file", "params": {"path": "test.txt"}}
{"event": "SIDE_EFFECT", "type": "filesystem.write", "target": "test.txt"}
{"event": "STEP_END", "status": "SUCCESS"}
```

---

## 副作用边界

副作用边界定义了**允许的副作用**：

```python
from failcore import run
from failcore.core.errors.side_effect import SideEffectBoundaryCrossedError

# 只允许文件系统读取
with run(policy="fs_safe") as ctx:
    @guard()
    def read_file(path: str):
        with open(path, "r") as f:
            return f.read()
    
    # 允许：读取在边界内
    read_file("data.txt")
    
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    # 阻止：写入不在边界内（如果边界只允许读取）
    try:
        write_file("output.txt", "data")
    except SideEffectBoundaryCrossedError:
        print("写入超出边界")
```

---

## 副作用审计

FailCore 提供副作用审计功能：

### 查看副作用

```bash
failcore show <trace_file>
```

输出包括：
- 所有观察到的副作用
- 副作用类型和目标
- 发生时间

### 审计报告

```bash
failcore report <trace_file>
```

生成审计报告，包括：
- 副作用摘要
- 违规统计
- 时间线

---

## 副作用检测机制

### 静态分析

FailCore 使用静态分析预测副作用：

```python
# 工具名和参数分析
tool = "write_file"
params = {"path": "test.txt"}

# 检测规则
if tool in ["write_file", "create_file"]:
    side_effect = detect_filesystem_side_effect(tool, params, "write")
    # 返回: SideEffectEvent(type="filesystem.write", target="test.txt")
```

### 运行时观察

执行后观察实际副作用：

```python
# 文件系统监控（如果启用）
# 网络监控（如果启用）
# 进程监控（如果启用）
```

---

## 副作用类型定义

### 文件系统副作用

```python
FILESYSTEM_READ = "filesystem.read"
FILESYSTEM_WRITE = "filesystem.write"
FILESYSTEM_DELETE = "filesystem.delete"
FILESYSTEM_METADATA = "filesystem.metadata"  # 读取元数据
```

### 网络副作用

```python
NETWORK_EGRESS = "network.egress"
NETWORK_DNS = "network.dns"
NETWORK_INGRESS = "network.ingress"  # 监听端口
```

### 进程副作用

```python
PROCESS_SPAWN = "process.spawn"
PROCESS_KILL = "process.kill"
PROCESS_SIGNAL = "process.signal"
```

---

## 副作用元数据

每个副作用事件包含元数据：

```python
@dataclass
class SideEffectEvent:
    type: SideEffectType
    target: Optional[str] = None  # 目标（路径/URL/命令）
    tool: Optional[str] = None  # 工具名
    step_id: Optional[str] = None  # 步骤 ID
    metadata: Dict[str, Any] = None  # 额外元数据
```

### 元数据示例

```json
{
  "type": "filesystem.write",
  "target": "test.txt",
  "tool": "write_file",
  "step_id": "abc123",
  "metadata": {
    "file_size": 1024,
    "permissions": "0644",
    "created": true
  }
}
```

---

## 副作用与策略

副作用检查在策略检查之前：

```
1. 预测副作用
   ↓
2. 检查副作用边界
   ↓
3. 如果超出边界 → 阻止
4. 如果在边界内 → 继续策略检查
   ↓
5. 执行工具
   ↓
6. 观察实际副作用
   ↓
7. 记录副作用
```

---

## 最佳实践

### 1. 明确声明副作用

在工具元数据中声明副作用：

```python
from failcore import run, guard
from failcore.core.errors.side_effect import SideEffectBoundaryCrossedError

with run(policy="fs_safe") as ctx:
    @guard(risk="high", effect="fs")
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
```

### 2. 最小副作用

设计工具时，尽量减少副作用：

```python
# 好：副作用明确
def read_config(path: str) -> dict:
    # 只读取，不修改
    with open(path, "r") as f:
        return json.load(f)

# 不好：副作用不明确
def process_file(path: str):
    # 读取还是写入？不清楚
    pass
```

### 3. 副作用测试

测试副作用是否正确检测：

```python
def test_side_effect_detection():
    with run(policy="fs_safe") as ctx:
        @guard()
        def write_file(path: str, content: str):
            with open(path, "w") as f:
                f.write(content)
        
        write_file("test.txt", "data")
        
        # 检查追踪文件中的副作用记录
        import json
        events = []
        with open(ctx.trace_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        side_effects = [e for e in events if e.get("event") == "SIDE_EFFECT"]
        assert len(side_effects) > 0
        assert side_effects[0]["type"] == "filesystem.write"
```

---

## 总结

副作用是 FailCore 的核心概念：

- ✅ 两阶段检测：预测 + 观察
- ✅ 完整记录：所有副作用都记录到追踪文件
- ✅ 边界控制：通过边界限制允许的副作用
- ✅ 审计支持：完整的副作用历史用于审计

---

## 下一步

- [执行边界](../concepts/execution-boundary.md) - 了解如何定义副作用边界
- [策略](../concepts/policy.md) - 了解策略如何控制副作用
- [追踪和重放](../concepts/trace-and-replay.md) - 如何使用副作用记录
