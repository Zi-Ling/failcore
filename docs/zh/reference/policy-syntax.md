# 策略语法参考

FailCore 策略文件语法的完整参考。

---

## 策略文件位置

策略文件存储在：

```
.failcore/validate/<策略名称>.yaml
```

使用自定义策略：

```python
run(policy="<策略名称>")
```

---

## 基本结构

```yaml
# .failcore/validate/my_policy.yaml
validators:
  - name: security_path_traversal
    action: BLOCK
  - name: network_ssrf
    action: WARN
```

---

## 验证器配置

### 操作类型

- `BLOCK`：如果验证失败则阻止执行
- `WARN`：记录警告但允许执行
- `SHADOW`：记录决策但不阻止

### 验证器名称

可用验证器：

#### 安全验证器

- `security_path_traversal`：路径遍历保护
- `network_ssrf`：SSRF 和私有网络保护

#### 资源验证器

- `resource_file_size`：文件大小限制
- `resource_memory`：内存限制
- `resource_timeout`：超时限制

#### 成本验证器

- `cost_budget`：预算执行
- `cost_burn_rate`：消耗率限制

---

## 验证器示例

### 路径遍历保护

```yaml
validators:
  - name: security_path_traversal
    action: BLOCK
    config:
      allow_absolute: false
      sandbox_root: "./data"
```

**配置：**
- `allow_absolute`：允许绝对路径（默认：`false`）
- `sandbox_root`：沙箱根目录

### SSRF 保护

```yaml
validators:
  - name: network_ssrf
    action: BLOCK
    config:
      allow_private_ips: false
      allowed_domains:
        - "api.example.com"
        - "*.trusted-domain.com"
```

**配置：**
- `allow_private_ips`：允许私有 IP 范围（默认：`false`）
- `allowed_domains`：允许的域白名单

### 文件大小限制

```yaml
validators:
  - name: resource_file_size
    action: WARN
    config:
      max_size_bytes: 10485760  # 10MB
      check_read: true
      check_write: true
```

**配置：**
- `max_size_bytes`：最大文件大小（字节）
- `check_read`：检查读取操作（默认：`true`）
- `check_write`：检查写入操作（默认：`true`）

### 预算执行

```yaml
validators:
  - name: cost_budget
    action: BLOCK
    config:
      max_cost_usd: 10.0
      currency: "USD"
```

**配置：**
- `max_cost_usd`：最大成本（美元）
- `currency`：货币代码（默认：`"USD"`）

### 消耗率限制

```yaml
validators:
  - name: cost_burn_rate
    action: BLOCK
    config:
      max_usd_per_minute: 0.5
      window_minutes: 5
```

**配置：**
- `max_usd_per_minute`：最大消耗率
- `window_minutes`：滑动窗口大小（默认：`5`）

---

## 完整策略示例

```yaml
# .failcore/validate/production.yaml
validators:
  # 安全
  - name: security_path_traversal
    action: BLOCK
    config:
      allow_absolute: false
      sandbox_root: "./workspace"
  
  - name: network_ssrf
    action: BLOCK
    config:
      allow_private_ips: false
      allowed_domains:
        - "api.production.com"
  
  # 资源
  - name: resource_file_size
    action: WARN
    config:
      max_size_bytes: 52428800  # 50MB
  
  # 成本
  - name: cost_budget
    action: BLOCK
    config:
      max_cost_usd: 100.0
  
  - name: cost_burn_rate
    action: BLOCK
    config:
      max_usd_per_minute: 1.0
      window_minutes: 10
```

---

## 策略继承

策略可以引用其他策略：

```yaml
# .failcore/validate/custom.yaml
extends: "safe"  # 从 safe 预设继承

validators:
  - name: security_path_traversal
    action: BLOCK
    config:
      sandbox_root: "./custom-sandbox"
```

---

## 条件验证器

验证器可以有条件地启用：

```yaml
validators:
  - name: security_path_traversal
    action: BLOCK
    condition:
      effect: "fs"  # 仅用于文件系统操作
```

---

## 下一步

- [配置参考](configuration.md) - 完整配置指南
- [策略指南](../concepts/policy.md) - 策略概念
