# 追踪和重放

FailCore 记录所有执行到追踪文件，支持事后分析和重放。

---

## 什么是追踪

追踪（Trace）是执行过程的完整记录：

- 每个工具调用
- 策略决策
- 执行结果
- 观察到的副作用
- 时间戳和性能指标

追踪文件是 JSONL 格式（每行一个 JSON 对象）。

---

## 追踪文件格式

### 事件类型

追踪文件包含以下事件类型：

#### STEP_START

工具调用开始：

```json
{
  "event": "STEP_START",
  "step_id": "abc123",
  "tool": "write_file",
  "params": {"path": "test.txt", "content": "Hello"},
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### POLICY_CHECK

策略检查结果：

```json
{
  "event": "POLICY_CHECK",
  "step_id": "abc123",
  "decision": "ALLOW",
  "validator": "security_path_traversal",
  "reason": "路径在沙箱内"
}
```

#### SIDE_EFFECT

观察到的副作用：

```json
{
  "event": "SIDE_EFFECT",
  "step_id": "abc123",
  "type": "filesystem.write",
  "target": "test.txt",
  "category": "filesystem"
}
```

#### STEP_END

工具调用结束：

```json
{
  "event": "STEP_END",
  "step_id": "abc123",
  "status": "SUCCESS",
  "output": "写入 5 字节",
  "duration_ms": 12.5
}
```

#### POLICY_DENIED

策略拒绝：

```json
{
  "event": "POLICY_DENIED",
  "step_id": "abc123",
  "reason": "路径遍历检测到",
  "error_code": "PATH_TRAVERSAL",
  "suggestion": "使用相对路径，不要使用 '..'"
}
```

---

## 追踪文件位置

默认情况下，追踪文件保存在：

```
<项目根目录>/.failcore/runs/<日期>/<run_id>/trace.jsonl
```

### 自定义追踪路径

```python
from failcore import run

# 使用自定义路径
with run(trace="my_trace.jsonl") as ctx:
    pass

# 禁用追踪
with run(trace=None) as ctx:
    pass
```

---

## 查看追踪

### CLI 命令

#### 列出所有追踪

```bash
failcore list
```

输出：
```
Run ID                    Date       Status    Steps
abc123...                 2024-01-15 SUCCESS   5
def456...                 2024-01-15 BLOCKED   2
```

#### 显示追踪详情

```bash
failcore show <run_id>
```

或：

```bash
failcore show <trace_file>
```

显示：
- 所有步骤
- 策略决策
- 执行结果
- 副作用

#### 生成报告

```bash
failcore report <run_id>
```

生成 HTML 报告，包括：
- 执行摘要
- 时间线
- 违规统计
- 成本分析

---

## 重放

重放（Replay）允许您：

1. **策略重放**：使用新策略重新评估历史执行
2. **逻辑重放**：零成本调试（不执行工具）
3. **确定性重放**：可重复的执行

### 重放模式

#### REPORT 模式

审计模式，只报告会发生什么：

```bash
failcore replay report <trace_file>
```

输出：
- 哪些步骤会被新策略阻止
- 哪些步骤会通过
- 策略差异

#### MOCK 模式

模拟模式，注入历史输出：

```bash
failcore replay mock <trace_file>
```

特点：
- 不执行实际工具
- 使用历史输出
- 用于测试和调试

### 重放示例

```python
from failcore.core.replay import Replayer, ReplayMode

# 创建重放器
replayer = Replayer("trace.jsonl", mode=ReplayMode.REPORT)

# 重放步骤
result = replayer.replay_step(
    step_id="abc123",
    tool="write_file",
    params={"path": "test.txt", "content": "Hello"},
    fingerprint={"tool": "write_file", "params_hash": "..."}
)

# 检查结果
if result.hit:
    print(f"匹配历史执行：{result.historical_output}")
else:
    print(f"新执行：{result.current_output}")
```

---

## 追踪分析

### 查看违规

```bash
failcore audit <trace_file>
```

分析追踪文件，识别：
- 策略违规
- 副作用边界跨越
- 异常模式

### 成本分析

```bash
failcore report <trace_file> --include-cost
```

显示：
- 总成本
- 每个步骤的成本
- 成本趋势

---

## 追踪文件结构

完整的追踪文件示例：

```jsonl
{"event": "RUN_START", "run_id": "abc123", "policy": "fs_safe", "timestamp": "2024-01-15T10:30:00Z"}
{"event": "STEP_START", "step_id": "step1", "tool": "write_file", "params": {"path": "test.txt", "content": "Hello"}}
{"event": "POLICY_CHECK", "step_id": "step1", "decision": "ALLOW", "validator": "security_path_traversal"}
{"event": "SIDE_EFFECT", "step_id": "step1", "type": "filesystem.write", "target": "test.txt"}
{"event": "STEP_END", "step_id": "step1", "status": "SUCCESS", "output": "写入 5 字节", "duration_ms": 12.5}
{"event": "STEP_START", "step_id": "step2", "tool": "write_file", "params": {"path": "../../etc/passwd", "content": "hack"}}
{"event": "POLICY_CHECK", "step_id": "step2", "decision": "DENY", "validator": "security_path_traversal", "reason": "路径遍历检测到"}
{"event": "POLICY_DENIED", "step_id": "step2", "error_code": "PATH_TRAVERSAL", "suggestion": "使用相对路径"}
{"event": "STEP_END", "step_id": "step2", "status": "BLOCKED", "duration_ms": 0.5}
{"event": "RUN_END", "run_id": "abc123", "status": "PARTIAL", "total_steps": 2, "blocked_steps": 1}
```

---

## 追踪最佳实践

### 1. 保留追踪文件

追踪文件包含完整的执行历史，应该：
- 版本控制（如果敏感，加密存储）
- 定期归档
- 设置保留策略

### 2. 使用标签

```python
from failcore import run

with run(tags={"env": "production", "version": "1.0"}) as ctx:
    pass
```

标签用于过滤和搜索追踪。

### 3. 定期审查

```bash
# 查看最近的违规
failcore audit --recent

# 生成周报
failcore report --since 7d
```

### 4. 重放测试

在部署新策略前，使用重放测试：

```bash
# 使用新策略重放历史追踪
failcore replay report <trace_file> --policy new_policy.yaml
```

---

## 追踪文件大小

追踪文件通常很小：

- 每个步骤：~1-5 KB
- 1000 个步骤：~1-5 MB
- 压缩后：~10-20% 原始大小

对于大型运行，考虑：
- 压缩追踪文件
- 定期清理旧追踪
- 使用外部存储

---

## 追踪 API

### 程序化访问

```python
import json

# 读取追踪文件
with open("trace.jsonl", "r") as f:
    for line in f:
        event = json.loads(line)
        if event["event"] == "STEP_END":
            print(f"步骤 {event['step_id']}: {event['status']}")
```

### 使用 TraceRepo

```python
from failcore.web.repos.trace_repo import TraceRepo

repo = TraceRepo()
events = repo.load_trace_events("abc123")

for event in events:
    if event["event"] == "POLICY_DENIED":
        print(f"违规: {event['reason']}")
```

---

## 总结

追踪和重放是 FailCore 的核心功能：

- ✅ 完整执行记录
- ✅ 策略重放测试
- ✅ 零成本调试
- ✅ 审计和分析支持
- ✅ 成本追踪

---

## 下一步

- [CLI 工具](../tools/cli.md) - 了解追踪相关的 CLI 命令
- [报告](../tools/reports.md) - 如何生成和分析报告
- [策略](../concepts/policy.md) - 如何使用追踪测试策略变更
