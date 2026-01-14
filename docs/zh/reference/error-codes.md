# 错误代码

FailCore 错误代码的完整参考。

---

## 概述

FailCore 使用标准化的错误代码对失败进行分类。所有错误都是带有 `error_code` 字段的 `FailCoreError` 实例。

---

## 错误代码分类

### 通用错误

| 代码 | 描述 |
|------|------|
| `UNKNOWN` | 未知或未分类的错误 |
| `INTERNAL_ERROR` | FailCore 内部错误 |
| `INVALID_ARGUMENT` | 无效的函数参数 |
| `PRECONDITION_FAILED` | 前置条件未满足 |
| `NOT_IMPLEMENTED` | 功能未实现 |
| `TIMEOUT` | 操作超时 |

---

### 安全和验证错误

| 代码 | 描述 |
|------|------|
| `POLICY_DENIED` | 策略拒绝执行 |
| `SANDBOX_VIOLATION` | 路径超出沙箱边界 |
| `PATH_TRAVERSAL` | 检测到路径遍历（`../` 转义） |
| `PATH_INVALID` | 无效的路径格式 |
| `ABSOLUTE_PATH` | 不允许绝对路径 |
| `UNC_PATH` | 不允许 UNC 路径（Windows） |
| `NT_PATH` | 不允许 NT 路径（Windows） |
| `DEVICE_PATH` | 不允许设备路径（Windows） |
| `SYMLINK_ESCAPE` | 检测到符号链接转义 |

---

### 文件系统错误

| 代码 | 描述 |
|------|------|
| `FILE_NOT_FOUND` | 文件不存在 |
| `PERMISSION_DENIED` | 权限被拒绝 |

---

### 网络错误

| 代码 | 描述 |
|------|------|
| `SSRF_BLOCKED` | SSRF 攻击被阻止 |
| `PRIVATE_NETWORK_BLOCKED` | 私有网络访问被阻止 |

---

### 工具和运行时错误

| 代码 | 描述 |
|------|------|
| `TOOL_NOT_FOUND` | 工具未注册 |
| `TOOL_EXECUTION_FAILED` | 工具执行失败 |
| `ASYNC_SYNC_MISMATCH` | 异步/同步不匹配 |
| `TOOL_NAME_CONFLICT` | 工具名称冲突 |

---

### 远程工具错误

| 代码 | 描述 |
|------|------|
| `REMOTE_TIMEOUT` | 远程工具超时 |
| `REMOTE_UNREACHABLE` | 远程工具不可达 |
| `REMOTE_PROTOCOL_MISMATCH` | 协议不匹配 |
| `REMOTE_TOOL_NOT_FOUND` | 远程工具未找到 |
| `REMOTE_INVALID_PARAMS` | 无效的远程工具参数 |
| `REMOTE_SERVER_ERROR` | 远程服务器错误 |

---

### 资源限制错误

| 代码 | 描述 |
|------|------|
| `RESOURCE_LIMIT_TIMEOUT` | 超时限制超出 |
| `RESOURCE_LIMIT_OUTPUT` | 输出大小限制超出 |
| `RESOURCE_LIMIT_EVENTS` | 事件计数限制超出 |
| `RESOURCE_LIMIT_FILE` | 文件大小限制超出 |
| `RESOURCE_LIMIT_CONCURRENCY` | 并发限制超出 |

---

### 重试错误

| 代码 | 描述 |
|------|------|
| `RETRY_EXHAUSTED` | 所有重试尝试已用尽 |

---

### 审批错误（HITL）

| 代码 | 描述 |
|------|------|
| `APPROVAL_REQUIRED` | 需要人工审批 |
| `APPROVAL_REJECTED` | 审批被拒绝 |
| `APPROVAL_TIMEOUT` | 审批超时 |

---

### 经济/成本错误

| 代码 | 描述 |
|------|------|
| `ECONOMIC_BUDGET_EXCEEDED` | 预算限制超出 |
| `ECONOMIC_BURN_RATE_EXCEEDED` | 消耗率限制超出 |
| `ECONOMIC_TOKEN_LIMIT` | 令牌限制超出 |
| `ECONOMIC_COST_ESTIMATION_FAILED` | 成本估算失败 |
| `BURN_RATE_EXCEEDED` | 消耗率超出（别名） |

---

### 数据丢失防护（DLP）

| 代码 | 描述 |
|------|------|
| `DATA_LEAK_PREVENTED` | 数据泄露被阻止 |
| `DATA_TAINTED` | 数据被污染 |
| `SANITIZATION_REQUIRED` | 需要清理 |

---

### 语义验证

| 代码 | 描述 |
|------|------|
| `SEMANTIC_VIOLATION` | 语义验证违规 |

---

## 错误代码组

FailCore 将错误代码组织成语义组：

### 安全代码

这些代码表示安全违规，必须显式处理：

```python
from failcore.core.errors import codes

if error.error_code in codes.SECURITY_CODES:
    # 安全违规 - 显式处理
    log_security_event(error)
```

**安全代码：**
- `POLICY_DENIED`
- `SANDBOX_VIOLATION`
- `PATH_TRAVERSAL`
- `PATH_INVALID`
- `ABSOLUTE_PATH`
- `UNC_PATH`
- `NT_PATH`
- `DEVICE_PATH`
- `SYMLINK_ESCAPE`
- `SSRF_BLOCKED`
- `PRIVATE_NETWORK_BLOCKED`
- `SEMANTIC_VIOLATION`

### 操作代码

定义良好的操作状态，不应降级：

```python
if error.error_code in codes.OPERATIONAL_CODES:
    # 操作错误 - 适当处理
    handle_operational_error(error)
```

**操作代码包括：**
- 工具错误（`TOOL_NOT_FOUND`、`TOOL_EXECUTION_FAILED` 等）
- 远程错误（`REMOTE_TIMEOUT`、`REMOTE_UNREACHABLE` 等）
- 资源限制（`RESOURCE_LIMIT_*`）
- 重试错误（`RETRY_EXHAUSTED`）
- 审批错误（`APPROVAL_*`）
- 经济错误（`ECONOMIC_*`）
- DLP 错误（`DATA_*`）

### 回退代码

非安全、非决定性的回退类别：

```python
if error.error_code in codes.DEFAULT_FALLBACK_CODES:
    # 回退错误 - 可能被降级
    handle_fallback_error(error)
```

**回退代码：**
- `UNKNOWN`
- `INTERNAL_ERROR`
- `INVALID_ARGUMENT`
- `PRECONDITION_FAILED`
- `TOOL_EXECUTION_FAILED`

---

## 使用错误代码

### 检查错误代码

```python
from failcore import run, guard
from failcore.core.errors import FailCoreError, codes

try:
    with run(policy="fs_safe") as ctx:
        @guard()
        def write_file(path: str, content: str):
            with open(path, "w") as f:
                f.write(content)
        
        write_file("/etc/passwd", "hack")
except FailCoreError as e:
    if e.error_code == codes.PATH_TRAVERSAL:
        print("检测到路径遍历")
    elif e.error_code == codes.SANDBOX_VIOLATION:
        print("沙箱违规")
    elif e.error_code in codes.SECURITY_CODES:
        print("安全违规:", e.error_code)
```

### 错误代码属性

```python
error = FailCoreError(
    message="检测到路径遍历",
    error_code=codes.PATH_TRAVERSAL
)

# 检查是否为安全错误
if error.is_security:
    print("安全违规")

# 获取错误详情
details = error.to_dict()
print(details["error_code"])  # "PATH_TRAVERSAL"
```

### LLM 友好的错误消息

FailCore 错误包含 LLM 友好的字段：

```python
error = FailCoreError(
    message="检测到路径遍历",
    error_code=codes.PATH_TRAVERSAL,
    suggestion="使用相对路径，不要使用 '..'",
    hint="路径包含 '..'，试图转义沙箱",
    remediation={
        "template": "使用路径: {safe_path}",
        "vars": {"safe_path": "./data/file.txt"}
    }
)

print(error)
# [PATH_TRAVERSAL] 检测到路径遍历
#
# [Suggestion] 使用相对路径，不要使用 '..'
# [Hint] 路径包含 '..'，试图转义沙箱
# [Remediation] 使用路径: {safe_path} (vars: {'safe_path': './data/file.txt'})
```

---

## 错误代码规范化

来自上游系统的未知错误代码会被规范化，以防止分类爆炸：

```python
from failcore.core.errors.exceptions import _normalize_error_code

# 未知代码被规范化
code = _normalize_error_code("CUSTOM_UPSTREAM_ERROR")
# 返回: "UNKNOWN"

# 已知的安全代码被保留
code = _normalize_error_code("PATH_TRAVERSAL")
# 返回: "PATH_TRAVERSAL"
```

**规范化规则：**
1. 安全代码按原样保留
2. 操作代码按原样保留
3. 回退代码按原样保留
4. 未知代码降级为 `UNKNOWN`

---

## 下一步

- [配置参考](configuration.md) - 配置选项
- [故障排除](../operations/troubleshooting.md) - 常见错误场景
