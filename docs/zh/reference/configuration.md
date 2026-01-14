# 配置参考

FailCore 配置选项的完整参考。

---

## 运行时配置

### `run()` 参数

`run()` 函数接受以下参数：

#### 策略配置

```python
run(
    policy: str = "safe",  # 策略名称或 None
    strict: bool = True,    # 启用严格验证
)
```

**策略选项：**
- `"safe"`（默认）：组合 fs_safe + net_safe
- `"fs_safe"`：仅文件系统安全
- `"net_safe"`：仅网络安全
- `"shadow"`：观察模式（不阻止）
- `"permissive"`：最小限制
- `None`：无策略（不推荐）

#### 路径配置

```python
run(
    sandbox: Optional[str] = None,  # 沙箱根目录
    trace: str = "auto",            # 追踪文件路径
    allow_outside_root: bool = False,  # 允许外部路径
    allowed_trace_roots: Optional[list] = None,  # 追踪白名单
    allowed_sandbox_roots: Optional[list] = None,  # 沙箱白名单
)
```

**路径解析规则：**

1. **仅名称**（无路径分隔符）：
   - `sandbox="data"` → `<project>/.failcore/runs/<run>/sandbox/data/`
   - `trace="trace.jsonl"` → `<project>/.failcore/runs/<run>/trace.jsonl`

2. **相对路径**（包含 `/` 或 `\`）：
   - `sandbox="./workspace"` → `<project>/workspace/`
   - `trace="artifacts/demo.jsonl"` → `<project>/artifacts/demo.jsonl`

3. **绝对路径**：
   - `sandbox="/tmp/sandbox"` → `/tmp/sandbox/`（需要 `allow_outside_root=True`）
   - `trace="/var/log/trace.jsonl"` → `/var/log/trace.jsonl`（需要白名单）

**特殊值：**
- `trace="auto"`（默认）：自动生成的路径
- `trace=None`：禁用追踪

#### 成本控制

```python
run(
    max_cost_usd: Optional[float] = None,      # 最大总成本
    max_tokens: Optional[int] = None,          # 最大令牌数
    max_usd_per_minute: Optional[float] = None,  # 最大消耗率
)
```

**示例：**
```python
# 预算限制
run(max_cost_usd=10.0)  # 在 $10.00 时停止

# 令牌限制
run(max_tokens=10000)  # 在 10k 令牌时停止

# 消耗率限制
run(max_usd_per_minute=0.5)  # 最大 $0.50/分钟
```

#### 运行元数据

```python
run(
    run_id: Optional[str] = None,  # 自定义运行 ID
    tags: Optional[Dict[str, str]] = None,  # 用于过滤的标签
    auto_ingest: bool = True,  # 自动将追踪导入数据库
)
```

**示例：**
```python
# 自定义运行 ID
run(run_id="production-run-001")

# 用于过滤的标签
run(tags={"environment": "prod", "version": "1.0"})

# 禁用自动导入
run(auto_ingest=False)
```

---

## 代理配置

### 命令行选项

```bash
failcore proxy [OPTIONS]
```

**选项：**

- `--listen ADDRESS`（默认：`127.0.0.1:8000`）
  - 代理服务器监听地址

- `--upstream URL`（可选）
  - 覆盖上游 LLM 提供商 URL

- `--mode MODE`（默认：`warn`）
  - 安全模式：`warn` 或 `strict`

- `--trace-dir PATH`（默认：`.failcore/proxy`）
  - 追踪文件目录

- `--budget FLOAT`（可选）
  - 最大成本（美元）

- `--run-id ID`（可选）
  - 自定义运行 ID

### 程序化配置

```python
from failcore.core.config.proxy import ProxyConfig

config = ProxyConfig(
    host="127.0.0.1",
    port=8000,
    upstream_timeout_s=60.0,
    upstream_max_retries=2,
    enable_streaming=True,
    streaming_chunk_size=8192,
    streaming_strict_mode=False,
    enable_dlp=True,
    dlp_strict_mode=False,
    trace_queue_size=10000,
    drop_on_full=True,
    allowed_providers=set(),  # 空 = 允许所有
    run_id=None,
    budget=None,
)
```

---

## 策略配置

### 策略预设

FailCore 提供内置策略预设：

#### `safe`（默认）

```python
run(policy="safe")
```

**启用的验证器：**
- `security_path_traversal`：路径遍历保护
- `network_ssrf`：SSRF 保护
- `resource_file_size`：文件大小限制（警告模式）

#### `fs_safe`

```python
run(policy="fs_safe", sandbox="./data")
```

**启用的验证器：**
- `security_path_traversal`：路径遍历和沙箱保护
- `resource_file_size`：文件大小限制

#### `net_safe`

```python
run(policy="net_safe")
```

**启用的验证器：**
- `network_ssrf`：SSRF 和私有网络保护

#### `shadow`

```python
run(policy="shadow")
```

**功能：**
- 所有验证器在 `SHADOW` 模式下启用
- 记录决策但不阻止
- 用于策略评估

#### `permissive`

```python
run(policy="permissive")
```

**功能：**
- 大多数验证器在 `WARN` 模式下
- 最小阻止
- 适用于开发

### 自定义策略

在 `.failcore/validate/<name>.yaml` 创建自定义策略文件：

```yaml
# .failcore/validate/custom.yaml
validators:
  - name: security_path_traversal
    action: BLOCK
  - name: network_ssrf
    action: WARN
```

使用自定义策略：

```python
run(policy="custom")
```

---

## Guard 配置

### `guard()` 参数

```python
guard(
    fn: Optional[Callable] = None,
    risk: RiskType = "medium",
    effect: Optional[EffectType] = None,
    action: Optional[str] = None,
    description: str = "",
)
```

**参数：**

- `risk`：风险级别（`"low"`、`"medium"`、`"high"`）
- `effect`：效果类型（`"read"`、`"fs"`、`"net"`、`"exec"`）
- `action`：执行模式（`"block"`、`"warn"`、`"shadow"`）
- `description`：工具描述

**示例：**

```python
# 低风险读取操作
guard(read_file, risk="low", effect="read")

# 高风险写入操作
guard(write_file, risk="high", effect="fs", action="block")

# 网络操作
guard(http_request, risk="medium", effect="net")
```

---

## 环境变量

FailCore 遵循以下环境变量：

### `FAILCORE_HOME`

默认 FailCore 主目录：

```bash
export FAILCORE_HOME=/path/to/failcore
```

默认：`<project>/.failcore`

### `FAILCORE_POLICY`

默认策略名称：

```bash
export FAILCORE_POLICY=fs_safe
```

### `FAILCORE_STRICT`

默认启用严格模式：

```bash
export FAILCORE_STRICT=1
```

---

## 配置文件

### 策略文件

位置：`.failcore/validate/<name>.yaml`

```yaml
validators:
  - name: security_path_traversal
    action: BLOCK
    config:
      allow_absolute: false
  - name: network_ssrf
    action: WARN
```

### 追踪配置

追踪存储在：`.failcore/runs/<date>/<run_id>_<time>/`

结构：
```
.failcore/
  runs/
    20240101/
      run001_120000/
        trace.jsonl
        sandbox/
```

---

## 下一步

- [策略语法](policy-syntax.md) - 策略文件格式
- [故障排除](../operations/troubleshooting.md) - 常见问题
