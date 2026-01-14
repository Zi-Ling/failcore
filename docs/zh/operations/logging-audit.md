# 日志和审计

FailCore 日志和审计功能指南。

---

## 概述

FailCore 提供全面的日志和审计功能：

- **结构化日志** - JSON 格式的日志
- **追踪文件** - 完整的执行记录
- **审计日志** - 策略决策和紧急解锁激活
- **成本追踪** - 经济活动日志

---

## 日志记录

### 日志级别

FailCore 使用标准 Python 日志级别：

- `DEBUG`：详细的诊断信息
- `INFO`：一般信息消息
- `WARNING`：警告消息
- `ERROR`：错误消息
- `CRITICAL`：严重错误

### 配置日志

```python
import logging

# 基本配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

# FailCore 特定日志记录器
logger = logging.getLogger('failcore')
logger.setLevel(logging.INFO)
```

### 结构化日志

FailCore 日志是结构化的，便于解析：

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "logger": "failcore.core.executor",
  "message": "工具执行已开始",
  "run_id": "run-001",
  "step_id": "step-001",
  "tool": "write_file"
}
```

### 日志输出

日志写入到：

- **控制台**：标准输出（默认）
- **文件**：配置文件处理器
- **外部系统**：使用日志处理器（例如 syslog、云日志）

```python
import logging
from logging.handlers import RotatingFileHandler

# 带轮转的文件处理器
handler = RotatingFileHandler(
    'failcore.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
handler.setFormatter(
    logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
)

logger = logging.getLogger('failcore')
logger.addHandler(handler)
```

---

## 追踪文件

### 追踪文件格式

追踪文件是 JSONL 格式（每行一个 JSON 对象）：

```json
{"event": "STEP_START", "step_id": "abc123", "tool": "write_file", ...}
{"event": "POLICY_CHECK", "step_id": "abc123", "decision": "ALLOW", ...}
{"event": "STEP_END", "step_id": "abc123", "status": "SUCCESS", ...}
```

### 追踪文件位置

默认位置：

```
<项目>/.failcore/runs/<日期>/<run_id>_<时间>/trace.jsonl
```

自定义位置：

```python
with run(trace="/var/log/failcore/trace.jsonl") as ctx:
    pass
```

### 追踪文件管理

#### 轮转

实施追踪文件轮转：

```python
import datetime
from pathlib import Path

# 每日轮转
date = datetime.datetime.now().strftime('%Y%m%d')
trace_path = f"traces/trace_{date}.jsonl"

with run(trace=trace_path) as ctx:
    pass
```

#### 压缩

压缩旧追踪文件：

```bash
# 压缩超过 7 天的追踪文件
find .failcore/runs -name "trace.jsonl" -mtime +7 -exec gzip {} \;
```

#### 清理

删除旧追踪文件：

```bash
# 删除超过 30 天的追踪文件
find .failcore/runs -name "trace.jsonl" -mtime +30 -delete
```

---

## 审计日志

### 策略审计

FailCore 记录所有策略决策：

```python
from failcore.core.validate.audit import get_audit_logger

audit_logger = get_audit_logger()

# 策略决策自动记录
with run(policy="fs_safe") as ctx:
    pass
```

### 紧急解锁审计

紧急解锁激活会被审计：

```python
from failcore.core.validate.audit import get_audit_logger

audit_logger = get_audit_logger()

# 记录紧急解锁激活
record = audit_logger.log_breakglass_activation(
    policy=policy,
    enabled_by="admin@example.com",
    reason="紧急维护",
    token_used="breakglass-token-123"
)

# 获取审计记录
audit_record = audit_logger.get_breakglass_audit(policy)
```

### 审计记录格式

```json
{
  "enabled_at": "2024-01-15T10:30:00Z",
  "enabled_by": "admin@example.com",
  "reason": "紧急维护",
  "expires_at": "2024-01-15T11:30:00Z",
  "token_used": "breakglass-token-123",
  "affected_validators": ["security_path_traversal"],
  "affected_decisions": ["BLOCK"]
}
```

---

## 成本追踪

### 成本日志

成本信息记录在追踪文件中：

```json
{
  "event": "COST_TRACKED",
  "step_id": "abc123",
  "cost_usd": 0.001,
  "tokens": 100,
  "model": "gpt-4"
}
```

### 成本报告

生成成本报告：

```bash
# 生成成本报告
failcore report trace.jsonl --cost

# 输出：
# 总成本: $10.50
# 总令牌数: 105,000
# 每个请求的平均成本: $0.10
```

---

## 与外部系统集成

### 云日志

与云日志服务集成：

```python
import logging
from google.cloud import logging as cloud_logging

# Google Cloud Logging
client = cloud_logging.Client()
client.setup_logging()

logger = logging.getLogger('failcore')
logger.info("FailCore 已启动")
```

### SIEM 集成

将日志导出到 SIEM 系统：

```python
import logging
from logging.handlers import SysLogHandler

# Syslog 处理器
handler = SysLogHandler(address=('syslog.example.com', 514))
logger = logging.getLogger('failcore')
logger.addHandler(handler)
```

### 监控系统

将指标导出到监控系统：

```python
# Prometheus 指标
from prometheus_client import Counter, Histogram

tool_calls = Counter('failcore_tool_calls_total', '总工具调用数')
tool_duration = Histogram('failcore_tool_duration_seconds', '工具调用持续时间')
```

---

## 最佳实践

### 日志保留

- **开发**：7 天
- **预发布**：30 天
- **生产**：90+ 天（合规要求）

### 日志安全

- 加密静态日志文件
- 使用安全日志传输（TLS）
- 限制日志文件访问
- 清理敏感数据

### 性能

- 在高吞吐量场景中使用异步日志
- 实施日志缓冲
- 为日志使用单独的存储
- 监控日志文件增长

---

## 合规性

### 审计要求

FailCore 审计日志支持合规要求：

- **谁**：做出决策的用户/系统
- **什么**：策略决策或紧急解锁激活
- **何时**：操作的时间戳
- **为什么**：原因/理由
- **哪里**：运行 ID 和步骤 ID

### 保留策略

实施保留策略：

```python
# 保留审计日志 7 年（合规）
import shutil
from datetime import datetime, timedelta

cutoff_date = datetime.now() - timedelta(days=2555)  # 7 年

for audit_file in Path('.failcore/audit').glob('*.jsonl'):
    if datetime.fromtimestamp(audit_file.stat().st_mtime) < cutoff_date:
        # 归档而不是删除
        shutil.move(audit_file, f'archive/{audit_file.name}')
```

---

## 下一步

- [部署](deployment.md) - 生产部署
- [故障排除](troubleshooting.md) - 常见日志问题
- [追踪和重放](../concepts/trace-and-replay.md) - 追踪文件使用
