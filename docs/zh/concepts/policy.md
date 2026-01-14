# 策略

策略（Policy）是 FailCore 的核心机制，用于定义和执行安全规则。

---

## 什么是策略

策略是一组**验证规则**，用于在执行前检查工具调用是否允许。

策略决定：
- ✅ 哪些操作被允许
- ❌ 哪些操作被阻止
- ⚠️ 哪些操作需要警告

---

## 策略预设

FailCore 提供以下策略预设：

### safe（默认）

综合安全策略，包含文件系统和网络安全：

```python
from failcore import run

with run(policy="safe") as ctx:
    # 启用：
    # - 路径遍历保护
    # - SSRF 保护
    # - 基本资源限制
    pass
```

**启用的验证器：**
- `security_path_traversal`：路径遍历保护
- `network_ssrf`：SSRF 保护
- `resource_file_size`：文件大小限制（警告模式）

### fs_safe

文件系统安全策略：

```python
with run(policy="fs_safe", sandbox="./data") as ctx:
    # 启用：
    # - 沙箱路径保护
    # - 路径遍历保护
    # - 文件大小限制
    pass
```

**启用的验证器：**
- `security_path_traversal`：路径遍历和沙箱保护
- `resource_file_size`：文件大小限制

### net_safe

网络安全策略：

```python
with run(policy="net_safe") as ctx:
    # 启用：
    # - SSRF 保护
    # - 私有网络阻止
    # - 协议限制
    pass
```

**启用的验证器：**
- `network_ssrf`：SSRF 和私有网络保护

### shadow

观察模式策略：

```python
with run(policy="shadow") as ctx:
    # 启用：
    # - 所有验证器（观察模式）
    # - 记录决策但不阻止
    pass
```

**特点：**
- 所有验证器启用但设置为 `SHADOW` 模式
- 记录所有决策但不阻止执行
- 用于评估策略影响

### permissive

宽松策略：

```python
with run(policy="permissive") as ctx:
    # 启用：
    # - 基本安全检查（警告模式）
    # - 不阻止执行
    pass
```

**特点：**
- 大多数验证器设置为 `WARN` 模式
- 只阻止明显危险的操作

---

## 策略结构

策略由以下部分组成：

### 验证器（Validators）

验证器是执行检查的组件：

```python
ValidatorConfig(
    id="security_path_traversal",
    domain="security",
    enabled=True,
    enforcement=EnforcementMode.BLOCK,
    priority=30,
    config={
        "path_params": ["path", "file_path"],
        "sandbox_root": "./data"
    }
)
```

**字段说明：**
- `id`：验证器唯一标识
- `domain`：验证器领域（security/network/resource）
- `enabled`：是否启用
- `enforcement`：执行模式（BLOCK/WARN/SHADOW）
- `priority`：优先级（数字越小优先级越高）
- `config`：验证器配置

### 执行模式（Enforcement Mode）

- **BLOCK**：阻止执行（严格模式）
- **WARN**：警告但不阻止（宽松模式）
- **SHADOW**：只记录不阻止（观察模式）

### 全局覆盖（Global Override）

紧急情况下可以覆盖策略：

```python
OverrideConfig(
    enabled=False,  # 默认禁用
    require_token=True  # 需要令牌才能启用
)
```

---

## 策略检查流程

策略检查按固定顺序执行：

```
1. 副作用边界门（快速预检查）
   ↓
2. 语义守卫（高置信度恶意模式检测）
   ↓
3. 污点追踪/DLP（数据丢失防护）
   ↓
4. 主策略检查（用户/系统策略）
   ↓
   按优先级排序的验证器
   ↓
   第一个返回 DENY 的验证器阻止执行
```

### 验证器优先级

验证器按 `priority` 字段排序：
- 数字越小，优先级越高
- 高优先级验证器先执行
- 如果高优先级验证器返回 DENY，后续验证器不执行

---

## 策略决策

每个验证器返回一个决策：

### PolicyResult

```python
@dataclass
class PolicyResult:
    allowed: bool  # 是否允许
    reason: str  # 原因
    error_code: Optional[str]  # 错误代码
    suggestion: Optional[str]  # 修复建议
    remediation: Optional[Dict]  # 结构化修复指令
```

### 允许决策

```python
PolicyResult.allow(reason="路径在沙箱内")
```

### 拒绝决策

```python
PolicyResult.deny(
    reason="路径遍历检测到：'../../etc/passwd'",
    error_code="PATH_TRAVERSAL",
    suggestion="使用相对路径，不要使用 '..'",
    remediation={
        "action": "sanitize_path",
        "template": "移除 '..'：{sanitized_path}",
        "vars": {"sanitized_path": "etc/passwd"}
    }
)
```

---

## 自定义策略

### 从文件加载

创建策略文件 `policy.yaml`：

```yaml
version: v1
validators:
  security_path_traversal:
    enabled: true
    enforcement: BLOCK
    priority: 30
    config:
      path_params: ["path", "file_path"]
      sandbox_root: "./workspace"
metadata:
  name: "custom_policy"
  description: "自定义策略"
```

加载策略：

```python
from failcore.core.validate.loader import load_policy

policy = load_policy("policy.yaml")
```

### 程序化创建

```python
from failcore.core.validate.contracts import Policy, ValidatorConfig, EnforcementMode

policy = Policy(
    version="v1",
    validators={
        "security_path_traversal": ValidatorConfig(
            id="security_path_traversal",
            domain="security",
            enabled=True,
            enforcement=EnforcementMode.BLOCK,
            priority=30,
            config={
                "path_params": ["path"],
                "sandbox_root": "./data"
            }
        )
    },
    metadata={
        "name": "my_policy",
        "description": "我的自定义策略"
    }
)
```

---

## 策略合并

FailCore 支持策略合并：

### 活动策略 + 影子策略

```python
from failcore.core.validate.loader import load_merged_policy

# 加载合并的策略（active + shadow）
policy = load_merged_policy(use_shadow=True)
```

### 活动策略 + 紧急覆盖

```python
# 加载合并的策略（active + breakglass）
policy = load_merged_policy(use_breakglass=True)
```

合并规则：
- 影子策略：覆盖活动策略的 `enforcement` 模式为 `SHADOW`
- 紧急覆盖：临时禁用所有验证器

---

## 策略管理 CLI

### 初始化策略目录

```bash
failcore policy init
```

创建：
- `active.yaml`：活动策略
- `shadow.yaml`：影子策略
- `breakglass.yaml`：紧急覆盖

### 列出验证器

```bash
failcore policy list-validators
```

### 显示策略

```bash
failcore policy show
failcore policy show --type shadow
failcore policy show --type merged
```

### 解释策略决策

```bash
failcore policy explain --tool write_file --param path=../../etc/passwd
```

显示哪些验证器会触发以及原因。

---

## 策略最佳实践

### 1. 从预设开始

```python
# 好：使用预设
with run(policy="fs_safe") as ctx:
    pass

# 不好：从头创建
# 除非您有特殊需求
```

### 2. 逐步收紧

```python
# 阶段 1：观察模式
with run(policy="shadow") as ctx:
    # 记录所有决策，不阻止

# 阶段 2：警告模式
# 修改策略，将 enforcement 改为 WARN

# 阶段 3：阻止模式
# 修改策略，将 enforcement 改为 BLOCK
```

### 3. 测试策略

```python
def test_policy():
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
        except FailCoreError:
            pass  # 预期行为
```

### 4. 记录策略变更

策略文件应该：
- 使用版本控制
- 记录变更原因
- 包含测试用例

---

## 策略与边界

**策略（Policy）**：
- 过程式：定义如何检查
- 动态：可以基于上下文
- 复杂：可以包含条件逻辑

**边界（Boundary）**：
- 声明式：定义允许什么
- 静态：运行前定义
- 简单：是/否判断

策略在边界检查**之后**执行，提供更详细的验证。

---

## 总结

策略是 FailCore 的核心安全机制：

- ✅ 定义验证规则
- ✅ 支持多种执行模式
- ✅ 提供 LLM 友好的错误消息
- ✅ 支持策略合并和覆盖
- ✅ 完整的 CLI 管理工具

---

## 下一步

- [执行边界](../concepts/execution-boundary.md) - 了解边界如何工作
- [追踪和重放](../concepts/trace-and-replay.md) - 如何使用策略决策记录
- [文件系统安全](../guides/fs-safety.md) - 文件系统策略实践
