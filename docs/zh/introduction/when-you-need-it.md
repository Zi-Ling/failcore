# 何时需要 FailCore

FailCore 设计用于需要**执行时安全保证**的场景。

---

## 适用场景

### 1. 执行真实世界副作用的 AI Agent

当您的 agent 可以：
- 修改文件系统
- 发送网络请求
- 执行系统命令
- 调用外部 API

FailCore 提供最后一道防线，确保这些操作不会造成意外损害。

### 2. 长时间运行或自主工作流

对于无人值守的 agent 系统：
- 自动化任务
- 持续监控
- 后台处理

FailCore 可以：
- 防止资源耗尽
- 阻止成本失控
- 记录所有操作以供审计

### 3. 触及敏感资源的工具

当工具可能访问：
- 生产数据库
- 内部服务
- 用户数据
- 系统配置

FailCore 强制执行访问控制策略。

### 4. 失败必须可解释和可审计的环境

在需要：
- 合规性审计
- 事故调查
- 责任追溯

的场景中，FailCore 提供完整的执行追踪。

---

## 典型用例

### 用例 1：文件操作 Agent

```python
from failcore import run, guard

with run(policy="fs_safe", sandbox="./workspace") as ctx:
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    # 这会成功
    write_file("data/output.txt", "Hello")
    
    # 这会被阻止（路径遍历）
    write_file("../../etc/passwd", "hack")
```

**为什么需要 FailCore：**
- Agent 可能生成错误的路径
- 路径遍历攻击可能破坏系统
- FailCore 在写入前验证路径

### 用例 2：网络请求 Agent

```python
from failcore import run, guard

with run(policy="net_safe") as ctx:
    @guard()
    def fetch_url(url: str):
        import urllib.request
        with urllib.request.urlopen(url) as response:
            return response.read()
    
    # 这会成功
    fetch_url("https://api.example.com/data")
    
    # 这会被阻止（SSRF）
    fetch_url("http://169.254.169.254/latest/meta-data/")
```

**为什么需要 FailCore：**
- SSRF 攻击可能访问内部服务
- Agent 可能被诱导访问私有 IP
- FailCore 阻止私有网络访问

### 用例 3：成本控制

```python
from failcore import run, guard

with run(policy="safe", max_cost_usd=1.0) as ctx:
    @guard()
    def expensive_api_call(query: str):
        # 调用昂贵的 API
        return call_llm_api(query)
    
    # 如果总成本超过 $1.00，后续调用会被阻止
    for query in queries:
        expensive_api_call(query)
```

**为什么需要 FailCore：**
- 防止无限循环消耗成本
- 设置预算上限
- 实时监控支出

---

## 不需要 FailCore 的场景

### 纯推理 Agent

如果您的 agent 只做：
- 文本生成
- 数据分析（不写入）
- 信息检索（只读）

可能不需要 FailCore。

### 完全沙箱环境

如果您已经在：
- Docker 容器中运行
- 虚拟机中隔离
- 完全受限的环境中

FailCore 仍然有用，但优先级较低。

### 仅用于演示

如果 agent 只用于：
- 概念验证
- 演示目的
- 不接触生产环境

FailCore 可能过度设计。

---

## 决策树

**我应该使用 FailCore 吗？**

```
Agent 会执行真实世界的副作用吗？
├─ 否 → 可能不需要 FailCore
└─ 是 → 继续

这些副作用可能造成损害吗？
├─ 否 → 可能不需要 FailCore
└─ 是 → 继续

需要审计追踪吗？
├─ 否 → 考虑使用 FailCore（安全保证）
└─ 是 → 强烈推荐使用 FailCore

需要成本控制吗？
├─ 否 → 考虑使用 FailCore（安全保证）
└─ 是 → 强烈推荐使用 FailCore
```

---

## 总结

如果您的 agent **可能造成损害**，FailCore 应该在执行路径中。

FailCore 提供：
- ✅ 执行时安全保证
- ✅ 完整的操作追踪
- ✅ 成本控制
- ✅ 审计能力

**当有疑问时，使用 FailCore。**

---

## 下一步

- [安装指南](../getting-started/install.md)
- [快速开始](../getting-started/first-run.md)
- [核心概念](../concepts/execution-boundary.md)
