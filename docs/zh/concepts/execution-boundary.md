# 执行边界

执行边界（Execution Boundary）是 FailCore 的核心概念，定义了允许的操作范围。

---

## 什么是执行边界

执行边界是一个**声明式的规范**，定义了在运行期间允许的副作用类别和类型。

它类似于"允许列表"：
- 定义哪些操作是允许的
- 所有其他操作都被禁止
- 在运行前静态定义，运行时不可变

---

## 边界类型

### 副作用类别（Categories）

FailCore 识别以下副作用类别：

- **FILESYSTEM**：文件系统操作
  - 读取文件
  - 写入文件
  - 删除文件
  - 创建目录

- **NETWORK**：网络操作
  - 出站 HTTP/HTTPS 请求
  - DNS 查询
  - 套接字连接

- **PROCESS**：进程操作
  - 启动进程
  - 终止进程
  - 发送信号

### 副作用类型（Types）

每个类别下有具体的类型：

```python
# 文件系统类型
FILESYSTEM_READ = "filesystem.read"
FILESYSTEM_WRITE = "filesystem.write"
FILESYSTEM_DELETE = "filesystem.delete"

# 网络类型
NETWORK_EGRESS = "network.egress"
NETWORK_DNS = "network.dns"

# 进程类型
PROCESS_SPAWN = "process.spawn"
PROCESS_KILL = "process.kill"
```

---

## 边界定义

### 使用预设边界

FailCore 提供预设边界：

```python
from failcore import run

# 只允许文件系统操作
with run(policy="fs_safe") as ctx:
    # 允许文件读写
    # 禁止网络和进程操作
    pass

# 只允许网络操作
with run(policy="net_safe") as ctx:
    # 允许网络请求
    # 禁止文件系统和进程操作
    pass

# 允许所有安全操作
with run(policy="safe") as ctx:
    # 允许文件系统和网络操作
    # 禁止进程操作
    pass
```

### 自定义边界

您也可以创建自定义边界：

```python
from failcore.core.config.boundaries import get_boundary

# 创建只读文件系统边界
boundary = get_boundary(
    allowed_categories=["FILESYSTEM"],
    allowed_types=["filesystem.read"],  # 只允许读取
    blocked_types=["filesystem.write", "filesystem.delete"]
)
```

---

## 边界检查流程

当工具调用发生时：

```
1. 预测副作用
   ↓
2. 检查副作用类型是否在允许列表中
   ↓
3. 如果在 → 允许执行
4. 如果不在 → 阻止执行
```

### 示例

```python
from failcore import run, guard

# 定义只读边界
with run(policy="fs_safe") as ctx:
    @guard()
    def read_file(path: str):
        with open(path, "r") as f:
            return f.read()
    
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    # 这会成功（读取在边界内）
    read_file("data.txt")
    
    # 这会被阻止（写入不在边界内）
    try:
        write_file("output.txt", "data")
    except FailCoreError:
        print("写入被边界阻止")
```

---

## 边界 vs 策略

**边界（Boundary）**：
- 声明式：定义允许什么
- 静态：运行前定义
- 简单：是/否判断

**策略（Policy）**：
- 过程式：定义如何检查
- 动态：可以基于上下文
- 复杂：可以包含条件逻辑

边界是**快速预检查**，策略是**详细验证**。

---

## 边界违规

当操作超出边界时：

1. **检测**：FailCore 检测到副作用类型不在允许列表中
2. **阻止**：执行被立即阻止，工具函数不运行
3. **记录**：违规记录到追踪文件
4. **异常**：抛出 `SideEffectBoundaryCrossedError`

### 违规记录

追踪文件中的违规记录：

```json
{
  "event": "POLICY_DENIED",
  "reason": "Side-effect boundary crossed",
  "side_effect_type": "filesystem.write",
  "allowed_categories": ["FILESYSTEM"],
  "allowed_types": ["filesystem.read"],
  "blocked_type": "filesystem.write"
}
```

---

## 边界配置

### 在 run() 中配置

```python
from failcore import run

with run(
    policy="fs_safe",
    # 边界通过策略隐式定义
) as ctx:
    pass
```

### 显式边界

```python
from failcore.core.config.boundaries import get_boundary
from failcore.core.executor.executor import Executor

boundary = get_boundary("strict")  # 或 "permissive", "readonly"

executor = Executor(
    side_effect_boundary=boundary,
    # ...
)
```

---

## 边界预设

FailCore 提供以下边界预设：

### strict

最严格边界：
- 只允许明确声明的副作用
- 所有其他操作被阻止

### permissive

宽松边界：
- 允许大多数常见操作
- 只阻止明显危险的操作

### readonly

只读边界：
- 只允许读取操作
- 禁止所有写入操作

---

## 最佳实践

### 1. 最小权限原则

只允许必要的副作用：

```python
# 好：只允许需要的操作
with run(policy="fs_safe") as ctx:  # 只允许文件系统
    pass

# 不好：允许所有操作
with run(policy=None) as ctx:  # 无边界
    pass
```

### 2. 明确边界

使用明确的边界定义：

```python
# 好：明确指定允许的操作
boundary = get_boundary(
    allowed_types=["filesystem.read", "filesystem.write"]
)

# 不好：使用过于宽泛的边界
boundary = get_boundary("permissive")  # 可能允许过多
```

### 3. 测试边界

验证边界按预期工作：

```python
def test_boundary():
    with run(policy="fs_safe") as ctx:
        # 应该成功
        read_file("data.txt")
        
        # 应该被阻止
        try:
            write_file("/etc/passwd", "hack")
            assert False, "应该被阻止"
        except FailCoreError:
            pass  # 预期行为
```

---

## 总结

执行边界是 FailCore 的第一道防线：

- ✅ 声明式定义允许的操作
- ✅ 快速预检查，在策略检查之前
- ✅ 简单有效，易于理解
- ✅ 提供清晰的违规报告

边界 + 策略 = 多层安全保护。

---

## 下一步

- [副作用](../concepts/side-effects.md) - 了解副作用如何被检测和记录
- [策略](../concepts/policy.md) - 深入了解策略系统
- [文件系统安全](../guides/fs-safety.md) - 文件系统边界实践
