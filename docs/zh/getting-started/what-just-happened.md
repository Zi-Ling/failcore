# 发生了什么

本指南解释 FailCore 在执行工具调用时发生了什么。

---

## 执行流程

当您调用一个被 `@guard()` 装饰的函数时，FailCore 执行以下步骤：

```
1. 工具调用请求
   ↓
2. 参数验证
   ↓
3. 策略检查
   ↓
4. 副作用边界检查
   ↓
5. 执行工具
   ↓
6. 记录结果
   ↓
7. 返回结果
```

---

## 详细步骤

### 1. 工具调用请求

```python
write_file("test.txt", "Hello")
```

当您调用函数时，`@guard()` 装饰器拦截调用：
- 捕获函数名和参数
- 创建执行上下文
- 准备策略检查

### 2. 参数验证

FailCore 验证：
- 参数类型是否正确
- 必需参数是否提供
- 参数值是否有效

如果验证失败，立即返回错误，不执行工具。

### 3. 策略检查

根据您指定的策略（如 `fs_safe`），FailCore 检查：

**文件系统策略 (`fs_safe`)**：
- 路径是否在沙箱内
- 是否包含路径遍历（`..`）
- 是否为绝对路径（如果禁止）

**网络策略 (`net_safe`)**：
- URL 是否指向私有 IP
- 协议是否允许
- 是否在允许列表中

如果策略检查失败，执行被**阻止**（BLOCKED），不会执行工具。

### 4. 副作用边界检查

FailCore 预测工具可能产生的副作用：
- 文件系统操作（读/写/删除）
- 网络请求（出站）
- 进程执行

如果副作用超出允许边界，执行被阻止。

### 5. 执行工具

如果所有检查通过，工具函数被调用：

```python
def write_file(path: str, content: str):
    with open(path, "w") as f:
        f.write(content)
```

工具正常执行，可能成功或失败。

### 6. 记录结果

无论成功或失败，FailCore 记录：
- 工具名称和参数
- 策略决策
- 执行结果
- 观察到的副作用
- 时间戳和性能指标

记录保存到追踪文件（`.jsonl` 格式）。

### 7. 返回结果

如果工具成功，返回结果。  
如果工具失败，抛出异常。  
如果被策略阻止，抛出 `FailCoreError` 异常。

---

## 执行结果状态

每个工具调用都有一个状态：

### ✅ SUCCESS

工具成功执行，返回结果。

```python
result = write_file("test.txt", "Hello")
# 状态: SUCCESS
```

### ❌ BLOCKED

策略检查失败，工具未执行。

```python
try:
    write_file("/etc/passwd", "hack")
except FailCoreError as e:
    # 状态: BLOCKED
    print(f"被阻止: {e}")
```

### ⚠️ FAIL

工具执行时出错（不是策略问题）。

```python
try:
    write_file("readonly.txt", "data")
except PermissionError as e:
    # 状态: FAIL
    print(f"执行失败: {e}")
```

---

## 追踪文件结构

追踪文件是 JSONL 格式（每行一个 JSON 对象）：

```json
{"event": "STEP_START", "step_id": "abc123", "tool": "write_file", "params": {"path": "test.txt", "content": "Hello"}}
{"event": "POLICY_CHECK", "step_id": "abc123", "decision": "ALLOW"}
{"event": "STEP_END", "step_id": "abc123", "status": "SUCCESS", "output": "..."}
```

事件类型包括：
- `STEP_START`：工具调用开始
- `POLICY_CHECK`：策略检查结果
- `SIDE_EFFECT`：观察到的副作用
- `STEP_END`：工具调用结束

---

## 策略决策流程

策略检查按固定顺序执行：

```
1. 副作用边界门（快速预检查）
   ↓
2. 语义守卫（高置信度恶意模式检测）
   ↓
3. 污点追踪/DLP（数据丢失防护）
   ↓
4. 主策略检查（用户/系统策略）
```

所有守卫必须返回 `PolicyResult`。  
只有 `PolicyStage` 决定是否阻止（返回 `StepResult`）。

---

## 示例：完整流程

```python
from failcore import run, guard
from failcore.core.errors import FailCoreError

with run(policy="fs_safe", sandbox="./data") as ctx:
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
        return f"写入 {len(content)} 字节"
    
    # 调用 1：成功
    result1 = write_file("test.txt", "Hello")
    # 流程：
    # 1. 捕获调用：write_file("test.txt", "Hello")
    # 2. 验证参数：✓
    # 3. 策略检查：路径 "test.txt" 在沙箱内 ✓
    # 4. 副作用检查：文件写入在允许范围内 ✓
    # 5. 执行：open("test.txt", "w").write("Hello") ✓
    # 6. 记录：STEP_END status=SUCCESS
    # 7. 返回："写入 5 字节"
    
    # 调用 2：被阻止
    try:
        write_file("/etc/passwd", "hack")
    except FailCoreError as e:
        pass
    # 流程：
    # 1. 捕获调用：write_file("/etc/passwd", "hack")
    # 2. 验证参数：✓
    # 3. 策略检查：路径 "/etc/passwd" 不在沙箱内 ✗
    # 4. 阻止执行，抛出 FailCoreError
    # 5. 记录：STEP_END status=BLOCKED
    # 6. 不执行工具函数
```

---

## 性能考虑

FailCore 的开销很小：

- **策略检查**：通常 < 1ms
- **追踪记录**：异步写入，不阻塞执行
- **副作用检测**：基于静态分析，无运行时开销

对于大多数应用，FailCore 的开销可以忽略不计。

---

## 下一步

- [执行边界](../concepts/execution-boundary.md) - 了解边界如何工作
- [策略](../concepts/policy.md) - 深入了解策略系统
- [追踪和重放](../concepts/trace-and-replay.md) - 如何使用追踪文件
