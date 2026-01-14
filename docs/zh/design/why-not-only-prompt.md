# 为什么不只是提示

FailCore 不依赖提示工程，而是提供执行时的安全保证。

---

## 问题：提示的局限性

### 1. 提示无法强制执行

提示只是**建议**，不是**保证**：

```python
# 提示可能说：
"只使用相对路径，不要使用绝对路径"

# 但模型仍然可能生成：
write_file("/etc/passwd", "hack")
```

**问题：**
- 模型可能忽略提示
- 提示可能被误解
- 提示无法强制执行

### 2. 提示无法检测执行时错误

即使提示正确，执行时的值可能仍然错误：

```python
# 提示：删除临时文件
# 模型生成：delete_file("temp.txt")
# 实际执行：delete_file("/project")  # 路径错误
```

**问题：**
- 提示无法检测执行时的值
- 错误只在执行时发现
- 为时已晚

### 3. 提示无法提供审计

提示无法提供：
- 执行记录
- 策略决策
- 违规追踪

**问题：**
- 无法事后分析
- 无法审计
- 无法调试

---

## FailCore 的解决方案

### 1. 执行时强制执行

FailCore 在**执行时**检查，而不是依赖提示：

```python
with run(policy="fs_safe", sandbox="./data") as ctx:
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    # 即使模型生成错误的路径，也会被阻止
    write_file("/etc/passwd", "hack")  # 被阻止
```

**优势：**
- 强制执行
- 无法绕过
- 确定性保证

### 2. 策略驱动

FailCore 使用**策略**而不是提示：

```python
# 策略定义规则
policy = fs_safe_policy(sandbox_root="./data")

# 策略自动执行
with run(policy=policy) as ctx:
    pass
```

**优势：**
- 可配置
- 可测试
- 可审计

### 3. 完整追踪

FailCore 记录所有执行：

```python
with run(policy="fs_safe") as ctx:
    write_file("test.txt", "Hello")
    
# 追踪文件包含：
# - 所有工具调用
# - 策略决策
# - 执行结果
```

**优势：**
- 完整记录
- 可审计
- 可调试

---

## 提示 vs FailCore

### 提示方法

```python
# 在提示中说明规则
prompt = """
规则：
1. 只使用相对路径
2. 不要访问 /etc
3. 不要访问私有 IP
"""

# 依赖模型遵守规则
result = llm.call(prompt)
```

**问题：**
- 无法强制执行
- 无法检测违规
- 无法提供保证

### FailCore 方法

```python
# 策略定义规则
with run(policy="fs_safe", sandbox="./data") as ctx:
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    # 自动强制执行
    write_file("/etc/passwd", "hack")  # 被阻止
```

**优势：**
- 强制执行
- 自动检测
- 提供保证

---

## 提示 + FailCore

提示和 FailCore 可以**互补**：

```python
# 提示：指导模型行为
prompt = """
使用相对路径，例如 'data/file.txt'
"""

# FailCore：强制执行
with run(policy="fs_safe", sandbox="./data") as ctx:
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    # 提示帮助模型生成正确的路径
    # FailCore 确保即使路径错误也会被阻止
    result = llm.call(prompt)
    write_file(result.path, result.content)
```

**优势：**
- 提示：提高正确率
- FailCore：提供最后一道防线

---

## 实际案例

### 案例 1：路径遍历

**提示方法：**
```python
prompt = "不要使用 .. 路径"
# 模型可能仍然生成：../../etc/passwd
```

**FailCore 方法：**
```python
with run(policy="fs_safe") as ctx:
    write_file("../../etc/passwd", "hack")  # 自动阻止
```

### 案例 2：SSRF

**提示方法：**
```python
prompt = "不要访问私有 IP"
# 模型可能仍然生成：http://169.254.169.254
```

**FailCore 方法：**
```python
with run(policy="net_safe") as ctx:
    fetch_url("http://169.254.169.254")  # 自动阻止
```

---

## 总结

FailCore 不依赖提示的原因：

- ✅ **强制执行**：策略自动执行，无法绕过
- ✅ **执行时检查**：在值执行时检查，而不是生成时
- ✅ **完整追踪**：记录所有执行，可审计
- ✅ **确定性保证**：提供可预测的行为

**提示 + FailCore = 最佳实践**

- 提示：提高正确率
- FailCore：提供安全保证

---

## 下一步

- [为什么不是 Docker](why-not-docker.md) - 了解 FailCore 的设计选择
- [设计哲学](philosophy.md) - 深入了解 FailCore 的设计
