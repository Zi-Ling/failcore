# 部署

FailCore 的生产部署指南。

---

## 概述

本指南涵盖 FailCore 的生产部署注意事项，包括：

- 基础设施要求
- 扩展策略
- 监控和可观测性
- 安全最佳实践
- 性能优化

---

## 基础设施要求

### 最低要求

- **CPU**：2 核
- **内存**：2 GB RAM
- **存储**：10 GB（用于追踪文件）
- **网络**：到 LLM 提供商的低延迟

### 推荐要求

- **CPU**：4+ 核
- **内存**：4+ GB RAM
- **存储**：50+ GB（用于追踪文件和审计日志）
- **网络**：到 LLM 提供商的专用网络路径

---

## 部署模式

### 代理模式部署

推荐在生产环境中使用代理模式：

```bash
# 启动代理服务器
failcore proxy \
    --listen 0.0.0.0:8000 \
    --upstream https://api.openai.com/v1 \
    --mode strict \
    --budget 100.0
```

#### Docker 部署

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装 FailCore
RUN pip install "failcore[proxy]"

# 暴露代理端口
EXPOSE 8000

# 启动代理
CMD ["failcore", "proxy", "--listen", "0.0.0.0:8000"]
```

#### Systemd 服务

```ini
[Unit]
Description=FailCore Proxy
After=network.target

[Service]
Type=simple
User=failcore
WorkingDirectory=/opt/failcore
ExecStart=/usr/local/bin/failcore proxy --listen 0.0.0.0:8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 运行时模式部署

对于运行时模式，将 FailCore 集成到您的应用程序中：

```python
from failcore import run, guard

# 应用程序代码
with run(policy="fs_safe", sandbox="./data") as ctx:
    @guard()
    def my_tool():
        pass
```

---

## 扩展策略

### 水平扩展

代理模式支持水平扩展：

1. **负载均衡器**：将 FailCore 代理放在负载均衡器后面
2. **多个实例**：运行多个代理实例
3. **会话亲和性**：对有状态操作使用会话亲和性

```yaml
# Kubernetes 示例
apiVersion: apps/v1
kind: Deployment
metadata:
  name: failcore-proxy
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: failcore
        image: failcore:latest
        ports:
        - containerPort: 8000
```

### 垂直扩展

对于高吞吐量场景：

- 增加 CPU 核心
- 增加内存
- 使用更快的存储（SSD）用于追踪文件

---

## 监控

### 指标

监控关键指标：

- **请求速率**：每秒请求数
- **错误率**：错误百分比
- **延迟**：P50、P95、P99 延迟
- **成本**：总成本和消耗率
- **策略违规**：每小时的安全违规

### 日志记录

FailCore 生成结构化日志：

```python
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
```

### 追踪文件

监控追踪文件增长：

```bash
# 检查追踪文件大小
du -sh .failcore/runs/*/trace.jsonl

# 轮转旧追踪
find .failcore/runs -name "trace.jsonl" -mtime +30 -delete
```

---

## 安全最佳实践

### 网络安全

- 对代理连接使用 TLS
- 将代理访问限制为内部网络
- 使用防火墙规则限制访问

### 身份验证

- 对代理访问使用 API 密钥
- 实施速率限制
- 使用 IP 白名单

### 策略配置

- 在生产环境中使用严格策略
- 定期审查和更新策略
- 启用审计日志

```python
# 生产策略
with run(
    policy="fs_safe",
    strict=True,
    sandbox="./workspace"
) as ctx:
    pass
```

---

## 性能优化

### 追踪文件管理

- 为追踪文件使用单独的存储
- 压缩旧追踪文件
- 实施追踪轮转

```python
# 带轮转的自定义追踪路径
import datetime

trace_path = f"traces/trace_{datetime.datetime.now().strftime('%Y%m%d')}.jsonl"
with run(trace=trace_path) as ctx:
    pass
```

### 资源限制

配置适当的资源限制：

```python
with run(
    max_cost_usd=100.0,
    max_tokens=100000,
    max_usd_per_minute=1.0
) as ctx:
    pass
```

### 缓存

缓存策略配置：

```python
# 重用策略对象
from failcore.core.validate.templates import fs_safe_policy

policy = fs_safe_policy(sandbox_root="./data")

# 跨运行重用
with run(policy=policy) as ctx:
    pass
```

---

## 高可用性

### 故障转移

实施故障转移策略：

1. **多个代理**：运行多个代理实例
2. **健康检查**：监控代理健康
3. **自动故障转移**：使用负载均衡器进行故障转移

### 备份

备份关键数据：

- 追踪文件
- 策略配置
- 审计日志

```bash
# 备份追踪文件
tar -czf traces_backup_$(date +%Y%m%d).tar.gz .failcore/runs/
```

---

## 灾难恢复

### 恢复程序

1. **从备份恢复**：恢复追踪文件和配置
2. **重放追踪**：使用追踪重放进行分析
3. **策略更新**：根据事件更新策略

### 事件响应

1. **识别**：使用追踪文件识别事件
2. **分析**：从追踪生成报告
3. **修复**：更新策略和配置

---

## 生产清单

在部署到生产环境之前：

- [ ] 配置适当的策略
- [ ] 设置监控和告警
- [ ] 配置资源限制
- [ ] 设置备份程序
- [ ] 测试故障转移场景
- [ ] 审查安全设置
- [ ] 记录部署程序
- [ ] 培训运维团队

---

## 下一步

- [部署模式](../getting-started/deployment-patterns.md) - 部署模式概述
- [日志和审计](logging-audit.md) - 日志和审计配置
- [故障排除](troubleshooting.md) - 常见部署问题
