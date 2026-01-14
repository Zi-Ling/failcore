# 为什么不是 Docker

FailCore 不依赖 Docker 或容器化，而是使用轻量级的运行时保护。

---

## 设计理念

FailCore 的设计理念是：

- ✅ **轻量级**：无需容器运行时
- ✅ **快速**：低开销，适合生产环境
- ✅ **简单**：易于集成和部署
- ✅ **确定性**：可预测的行为

---

## Docker 的局限性

### 1. 性能开销

Docker 容器带来性能开销：
- 虚拟化层
- 网络隔离
- 文件系统挂载

对于 AI agent 的频繁工具调用，这些开销可能不可接受。

### 2. 部署复杂性

Docker 需要：
- Docker 守护进程
- 容器镜像管理
- 网络配置
- 卷挂载

增加了部署和维护的复杂性。

### 3. 资源限制

Docker 的资源限制可能：
- 限制并发
- 影响性能
- 难以调优

### 4. 调试困难

容器化环境：
- 日志隔离
- 调试工具受限
- 难以访问主机资源

---

## FailCore 的替代方案

### 1. 沙箱隔离

FailCore 使用**文件系统沙箱**：

```python
with run(policy="fs_safe", sandbox="./workspace") as ctx:
    # 所有文件操作限制在沙箱内
    pass
```

**优势：**
- 轻量级（无虚拟化）
- 快速（直接文件系统访问）
- 简单（只需指定目录）

### 2. 策略保护

FailCore 使用**策略驱动**的保护：

```python
with run(policy="net_safe") as ctx:
    # 策略自动阻止 SSRF
    pass
```

**优势：**
- 细粒度控制
- 可配置
- 可审计

### 3. 进程隔离（可选）

对于需要更强隔离的场景，FailCore 支持进程隔离：

```python
from failcore.core.executor.process import ProcessExecutor

executor = ProcessExecutor(
    working_dir="./workspace",
    timeout_s=60
)
```

**优势：**
- 可选功能
- 不影响性能（默认不使用）
- 提供额外保护层

---

## 何时使用 Docker

虽然 FailCore 不依赖 Docker，但在以下场景 Docker 仍然有用：

### 1. 完全隔离

如果需要完全隔离（例如，运行不受信任的代码），Docker 可能更合适。

### 2. 环境一致性

如果需要确保环境一致性（例如，CI/CD），Docker 可能更合适。

### 3. 多租户

如果需要多租户隔离，Docker 可能更合适。

---

## FailCore + Docker

FailCore 可以与 Docker 一起使用：

```dockerfile
FROM python:3.11

# 安装 FailCore
RUN pip install failcore

# 在容器内使用 FailCore
# FailCore 提供额外的保护层
```

**优势：**
- Docker 提供环境隔离
- FailCore 提供执行时保护
- 双重保护

---

## 性能对比

### FailCore 沙箱

- 开销：< 1ms 每次检查
- 启动时间：即时
- 资源使用：最小

### Docker 容器

- 开销：10-100ms 每次调用
- 启动时间：1-5 秒
- 资源使用：中等

---

## 总结

FailCore 选择不使用 Docker 的原因：

- ✅ 性能：更低的开销
- ✅ 简单：更易于集成
- ✅ 灵活：可配置的保护
- ✅ 快速：即时启动

对于大多数 AI agent 场景，FailCore 的轻量级保护已经足够。

---

## 下一步

- [为什么不只是提示](why-not-only-prompt.md) - 了解 FailCore 的设计理念
- [设计哲学](philosophy.md) - 深入了解 FailCore 的设计
