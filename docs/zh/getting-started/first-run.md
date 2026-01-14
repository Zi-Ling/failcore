# 首次运行

本指南将带您完成第一个 FailCore 程序。

---

## 快速示例

创建一个简单的 Python 文件 `demo.py`：

```python
from failcore import run, guard

with run(policy="fs_safe", sandbox="./data", strict=True) as ctx:
    @guard()
    def write_file(path: str, content: str):
        """写入文件"""
        with open(path, "w") as f:
            f.write(content)
    
    # 尝试写入文件
    try:
        write_file("test.txt", "Hello FailCore!")
        print("✓ 写入成功")
    except Exception as e:
        print(f"✗ 被阻止: {e}")
    
    # 尝试写入沙箱外的文件（会被阻止）
    try:
        write_file("/etc/passwd", "hack")
        print("✗ 意外成功")
    except Exception as e:
        print(f"✓ 正确阻止: {type(e).__name__}")
    
    print(f"\n追踪文件: {ctx.trace_path}")
```

运行它：

```bash
python demo.py
```

---

## 发生了什么

### 1. 创建运行上下文

```python
with run(policy="fs_safe", sandbox="./data", strict=True) as ctx:
```

这创建了一个 FailCore 运行上下文：
- `policy="fs_safe"`：使用文件系统安全策略
- `sandbox="./data"`：将操作限制在 `./data` 目录内
- `strict=True`：严格模式，违规会抛出异常

### 2. 使用 @guard() 装饰器

```python
@guard()
def write_file(path: str, content: str):
```

`@guard()` 装饰器将函数注册到 FailCore，使其：
- 在执行前进行策略检查
- 记录所有调用到追踪文件
- 在违规时阻止执行

### 3. 执行工具调用

```python
write_file("test.txt", "Hello FailCore!")
```

当您调用被 `@guard()` 装饰的函数时：
1. FailCore 检查策略（路径是否在沙箱内）
2. 如果允许，执行函数
3. 记录结果到追踪文件

### 4. 违规被阻止

```python
write_file("/etc/passwd", "hack")
```

这个调用会被阻止，因为：
- `/etc/passwd` 是绝对路径
- 不在沙箱 `./data` 内
- 违反 `fs_safe` 策略

---

## 查看追踪

运行后，您会看到追踪文件路径：

```
追踪文件: .failcore/runs/2024-01-15/abc123/trace.jsonl
```

查看追踪内容：

```bash
failcore show
```

或者：

```bash
cat .failcore/runs/2024-01-15/abc123/trace.jsonl
```

追踪文件包含：
- 每个工具调用的参数
- 策略决策
- 执行结果
- 时间戳

---

## 替代风格：显式注册

除了 `@guard()` 装饰器，您也可以显式注册工具：

```python
from failcore import run

def write_file(path: str, content: str):
    with open(path, "w") as f:
        f.write(content)

with run(policy="fs_safe", sandbox="./data") as ctx:
    # 注册工具
    ctx.tool(write_file)
    
    # 调用工具
    ctx.call("write_file", path="test.txt", content="Hello")
```

两种风格功能相同，选择您喜欢的即可。

---

## 网络安全示例

```python
from failcore import run, guard
import urllib.request

with run(policy="net_safe") as ctx:
    @guard()
    def fetch_url(url: str) -> str:
        """获取 URL 内容"""
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.read().decode('utf-8')[:200]
    
    # 这会成功（公共 URL）
    try:
        result = fetch_url("https://httpbin.org/get")
        print(f"✓ 成功: {result[:50]}...")
    except Exception as e:
        print(f"✗ 失败: {e}")
    
    # 这会被阻止（SSRF）
    try:
        result = fetch_url("http://169.254.169.254/latest/meta-data/")
        print("✗ 意外成功")
    except Exception as e:
        print(f"✓ 正确阻止 SSRF: {type(e).__name__}")
```

---

## 下一步

- [发生了什么](what-just-happened.md) - 深入了解执行流程
- [核心概念](../concepts/execution-boundary.md) - 了解执行边界
- [文件系统安全](../guides/fs-safety.md) - 文件系统保护指南

---

## 常见问题

### 为什么需要 sandbox 参数？

`sandbox` 参数定义了文件系统操作的允许范围。没有它，FailCore 无法知道哪些路径是安全的。

### strict=True 是什么意思？

`strict=True` 意味着策略违规会抛出异常。如果设置为 `False`，违规会被记录但不会阻止执行（观察模式）。

### 追踪文件在哪里？

默认情况下，追踪文件保存在：
```
<项目根目录>/.failcore/runs/<日期>/<run_id>/trace.jsonl
```

您可以使用 `trace` 参数自定义路径。
