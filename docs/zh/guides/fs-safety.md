# 文件系统安全

本指南介绍如何使用 FailCore 保护文件系统操作。

---

## 概述

文件系统安全策略（`fs_safe`）提供：

- ✅ 沙箱路径保护
- ✅ 路径遍历防护
- ✅ 文件大小限制
- ✅ 绝对路径阻止

---

## 基本用法

### 启用文件系统安全

```python
from failcore import run, guard

with run(policy="fs_safe", sandbox="./data") as ctx:
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    # 这会成功（在沙箱内）
    write_file("test.txt", "Hello")
    
    # 这会被阻止（路径遍历）
    try:
        write_file("../../etc/passwd", "hack")
    except PolicyDeny:
        print("路径遍历被阻止")
```

---

## 沙箱配置

### 默认沙箱

如果不指定 `sandbox`，FailCore 使用默认沙箱：

```
<项目根目录>/.failcore/sandbox/
```

### 自定义沙箱

```python
# 相对路径
with run(policy="fs_safe", sandbox="./workspace") as ctx:
    pass

# 绝对路径（需要 allow_outside_root=True）
with run(
    policy="fs_safe",
    sandbox="/tmp/my_sandbox",
    allow_outside_root=True,
    allowed_sandbox_roots=[Path("/tmp")]
) as ctx:
    pass
```

### 沙箱规则

1. **所有文件操作必须在沙箱内**
   - 读取、写入、删除都受限制
   - 路径必须解析到沙箱目录内

2. **路径遍历被阻止**
   - `../` 序列被检测并阻止
   - 即使最终路径在沙箱内，路径遍历也被阻止

3. **绝对路径被阻止**
   - 默认情况下，绝对路径被阻止
   - 除非明确允许外部路径

---

## 路径验证

### 允许的路径

```python
with run(policy="fs_safe", sandbox="./data") as ctx:
    @guard()
    def read_file(path: str):
        with open(path, "r") as f:
            return f.read()
    
    # ✅ 相对路径（在沙箱内）
    read_file("test.txt")
    read_file("subdir/file.txt")
    
    # ✅ 相对路径（解析后在沙箱内）
    read_file("data/test.txt")  # 如果 sandbox="./data"
```

### 被阻止的路径

```python
with run(policy="fs_safe", sandbox="./data") as ctx:
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    # ❌ 路径遍历
    try:
        write_file("../../etc/passwd", "hack")
    except PolicyDeny as e:
        print(f"被阻止: {e.result.reason}")
        # 输出: 被阻止: 路径遍历检测到：'../../etc/passwd'
    
    # ❌ 绝对路径
    try:
        write_file("/etc/passwd", "hack")
    except PolicyDeny as e:
        print(f"被阻止: {e.result.reason}")
        # 输出: 被阻止: 绝对路径不允许：'/etc/passwd'
    
    # ❌ 超出沙箱
    try:
        write_file("../outside.txt", "data")
    except PolicyDeny as e:
        print(f"被阻止: {e.result.reason}")
        # 输出: 被阻止: 路径将在沙箱外创建：'../outside.txt'
```

---

## 文件大小限制

`fs_safe` 策略包含文件大小限制：

```python
# 默认限制：50MB
with run(policy="fs_safe", sandbox="./data") as ctx:
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    # 小文件：成功
    write_file("small.txt", "Hello")
    
    # 大文件：可能被警告或阻止（取决于配置）
    large_content = "x" * (100 * 1024 * 1024)  # 100MB
    try:
        write_file("large.txt", large_content)
    except PolicyDeny:
        print("文件太大")
```

### 自定义文件大小限制

```python
from failcore.core.validate.templates import fs_safe_policy
from failcore.core.validate.contracts import EnforcementMode

# 创建自定义策略
policy = fs_safe_policy(sandbox_root="./data")
policy.validators["resource_file_size"].config["max_bytes"] = 10 * 1024 * 1024  # 10MB
policy.validators["resource_file_size"].enforcement = EnforcementMode.BLOCK
```

---

## 路径参数名称

FailCore 自动检测以下参数名称中的路径：

- `path`
- `file_path`
- `filename`
- `file`
- `output_path`
- `dst`
- `destination`
- `source`
- `src`

### 自定义路径参数

如果您的工具使用不同的参数名，可以在策略中配置：

```yaml
validators:
  security_path_traversal:
    config:
      path_params: ["custom_path_param", "another_param"]
```

---

## 错误消息

FailCore 提供 LLM 友好的错误消息：

```python
try:
    write_file("../../etc/passwd", "hack")
except PolicyDeny as e:
    print(e.result.reason)
    # 输出: 路径遍历检测到：'../../etc/passwd'
    
    print(e.result.suggestion)
    # 输出: 使用相对路径，不要使用 '..' - 示例：'data/file.txt' 而不是 '../../etc/passwd'
    
    print(e.result.remediation)
    # 输出: {'action': 'sanitize_path', 'template': "移除 '..'：{sanitized_path}", 'vars': {'sanitized_path': 'etc/passwd'}}
```

---

## 最佳实践

### 1. 始终指定沙箱

```python
# 好：明确指定沙箱
with run(policy="fs_safe", sandbox="./workspace") as ctx:
    pass

# 不好：使用默认沙箱（可能不明确）
with run(policy="fs_safe") as ctx:
    pass
```

### 2. 使用相对路径

```python
# 好：相对路径
write_file("data/output.txt", "content")

# 不好：绝对路径
write_file("/absolute/path/file.txt", "content")
```

### 3. 测试路径验证

```python
def test_path_validation():
    with run(policy="fs_safe", sandbox="./test") as ctx:
        @guard()
        def write_file(path: str, content: str):
            with open(path, "w") as f:
                f.write(content)
        
        # 应该成功
        write_file("test.txt", "data")
        
        # 应该被阻止
        try:
            write_file("../../etc/passwd", "hack")
            assert False, "应该被阻止"
        except PolicyDeny:
            pass  # 预期行为
```

### 4. 监控追踪文件

```python
with run(policy="fs_safe", sandbox="./data") as ctx:
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    write_file("test.txt", "Hello")
    
    # 查看追踪文件
    print(f"追踪文件: {ctx.trace_path}")
    # 运行: failcore show {ctx.trace_path}
```

---

## 高级配置

### 允许外部路径

```python
from pathlib import Path

with run(
    policy="fs_safe",
    sandbox="/tmp/external",
    allow_outside_root=True,
    allowed_sandbox_roots=[Path("/tmp")]
) as ctx:
    # 现在可以使用 /tmp 下的路径
    pass
```

### 自定义策略

```python
from failcore.core.validate.templates import fs_safe_policy
from failcore.core.validate.contracts import EnforcementMode

# 创建自定义文件系统策略
policy = fs_safe_policy(sandbox_root="./data")

# 修改验证器配置
policy.validators["security_path_traversal"].config["sandbox_root"] = "./custom_sandbox"
policy.validators["resource_file_size"].config["max_bytes"] = 10 * 1024 * 1024  # 10MB
policy.validators["resource_file_size"].enforcement = EnforcementMode.BLOCK

# 使用自定义策略
# 注意：需要通过 Executor 直接使用，run() API 目前只支持预设名称
```

---

## 常见问题

### Q: 为什么相对路径也被阻止？

A: 如果相对路径解析后超出沙箱，会被阻止。确保所有路径都在沙箱内。

### Q: 如何允许特定外部路径？

A: 使用 `allow_outside_root=True` 和 `allowed_sandbox_roots` 参数。

### Q: 文件大小限制可以禁用吗？

A: 可以，将 `resource_file_size` 验证器的 `enforcement` 设置为 `SHADOW` 或禁用该验证器。

---

## 总结

文件系统安全策略提供：

- ✅ 沙箱隔离
- ✅ 路径遍历防护
- ✅ 文件大小限制
- ✅ LLM 友好的错误消息

---

## 下一步

- [网络控制](network-control.md) - 了解网络安全保护
- [策略](../concepts/policy.md) - 深入了解策略系统
- [执行边界](../concepts/execution-boundary.md) - 了解边界如何工作
