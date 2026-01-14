# Validate Core：FailCore 的决策引擎

## 1. 为什么 FailCore 要有 Validate Core？

FailCore 的目标不是"执行 agent"，而是在执行前做确定性决策。

**Validate Core** 是那个唯一可以独立运行、无副作用的决策引擎。

### 核心价值

Validate Core answers only one question:

> **"Given this context and this policy, should this action be allowed?"**

这是 FailCore 安全性的基石：在执行任何工具调用之前，Validate Core 必须给出明确的决策（allow / warn / block），并提供可审计的证据。

---

## 2. Validate Core 的硬边界定义（Hard Boundary）

这是整篇文档的灵魂，也是未来抽取、重构、拒绝 feature creep 的最高法条。

### 硬标准

Validate Core 必须满足：

- **输入**：PolicyV1 (JSON/YAML) + ContextV1 (JSON)
- **输出**：DecisionV1[] (JSON)
- **无 I/O**：不进行文件读写、网络请求
- **无全局状态**：不依赖全局变量、单例模式
- **无运行时依赖**：不依赖 executor / trace / ui / guard / runtime

### 设计原则

1. **纯函数式**：给定相同的 Policy 和 Context，总是产生相同的 Decision
2. **语言无关**：所有数据契约都是 JSON 可序列化的
3. **可测试性**：可以在任何环境中独立运行和测试
4. **可抽取性**：未来可以抽取为独立的 Rust/WASM/Mobile SDK

---

## 3. 当前代码的可抽取性检查（Reality Check）

### 3.1 Dependency Boundary（依赖边界）

#### Core 文件分类

- **Core（必须可抽取）**：
  - `contracts/` - Policy/Context/Decision 定义
  - `validator.py` - BaseValidator 接口
  - `engine.py` - ValidationEngine
  - `registry.py` - ValidatorRegistry
  - `loader.py` - Policy 加载/序列化（core 层为纯函数）
  - `deduplication.py` - 决策去重
  - `explain.py` - 决策解释
  - `templates.py` - 预设策略

- **Builtin（可选随包带走）**：
  - `builtin/` - 各种 validators 实现

#### 检查结果

✅ **已修复：contract.py 已在 builtin/output 目录**

- **文件位置**：`failcore/core/validate/builtin/output/contract.py`
- **状态**：已移动到 builtin 层（符合可抽取要求）
- **实现**：已改为标准 BaseValidator 实现（OutputContractValidator）
- **依赖**：依赖 `failcore.core.contract`（builtin 层允许，不影响 core 抽取）

✅ **通过：core 文件依赖纯净**

- `contracts/`：只依赖标准库 + Pydantic（可选）
- `validator.py`：只依赖 contracts
- `engine.py`：只依赖 contracts + validator
- `registry.py`：只依赖 validator
- `loader.py`：只依赖 contracts + 标准库（yaml, json）

---

### 3.2 Side Effects Audit（副作用审计）

这一节是 validate-core 是否"真 core"的关键。所有副作用必须由宿主注入。

#### 文件 I/O（loader）

✅ **已修复：loader.py 文件 I/O 已分离**

- **Core 层（I/O-free）**：
  - `parse_policy_from_str()` - 从字符串解析（纯函数）
  - `parse_policy_from_dict()` - 从字典解析（纯函数）
  - `serialize_policy_to_str()` - 序列化为字符串（纯函数）
  - `serialize_policy_to_dict()` - 序列化为字典（纯函数）

- **API 层（with I/O）**：
  - `load_policy()`, `save_policy()`, `load_merged_policy()` 等使用 core 层函数

- **抽取策略**：可以只抽取 core 层函数，API 层作为可选工具层

#### 时间依赖（datetime.now）

✅ **已修复：engine.py 时间依赖**

- `engine.py`：`_apply_override()` 和 `_has_active_exception()` 已改为从 `context.metadata` 注入 `timestamp`
- 使用 `MetaKeys.TIMESTAMP` 常量（避免魔术字符串）
- 无 `datetime.now()` fallback（fail-closed：如果 context.metadata 中没有提供 timestamp，拒绝 override）

✅ **已修复：contracts/v1/policy.py ExceptionV1.is_expired()**

- `is_expired()` 接受 `current_time` 参数（由调用方从 `context.metadata` 提供）
- 无 `datetime.now()` fallback（fail-closed：如果 `current_time` 为 None，返回 True）

#### 环境变量依赖（os.environ）

✅ **已修复：engine.py 环境变量依赖**

- `engine.py`：`_apply_override()` 已改为从 `context.metadata` 注入 `override_token`
- 使用 `MetaKeys.OVERRIDE_TOKEN` 常量（避免魔术字符串）
- 无 `os.environ.get()` fallback（fail-closed：如果 context.metadata 中没有提供 override_token，拒绝 override）

---

### 3.3 Global State Audit（全局状态）

这一节非常重要，很多项目死在这里。全局状态是抽取的杀手。

#### Global Registry

✅ **已修复：registry.py 全局状态**

- 已移除 `_global_registry` 全局变量
- 已移除 `get_global_registry()`、`set_global_registry()`、`reset_global_registry()` 函数
- `ValidatorRegistry` 现在必须显式实例化并传入 `ValidationEngine`

✅ **Registry 单例上移到 API 层**

- `api/context.py` 持有应用级 registry（`_get_app_registry()`）
- core 层只接受显式传入，保持可抽取性
- 性能优化：应用级单例可以复用，但 core 层不依赖它

#### 其他全局状态

✅ **通过：其他 core 文件无全局状态**

- `engine.py`：无全局变量
- `contracts/`：无全局变量（纯数据模型）
- `validator.py`：无全局变量（抽象基类）

---

### 3.4 Data Contract Check（语言无关性）

这是未来 Rust / WASM / Mobile 的基础。所有数据契约必须是 JSON 可序列化的。

#### JSON 可序列化检查

✅ **通过：所有字段 JSON 可序列化**

- `PolicyV1`：所有字段为 JSON 基础类型（str, int, bool, dict, list）
- `ContextV1`：所有字段为 JSON 基础类型（tool: str, params: dict, result: Any）
- `DecisionV1`：所有字段为 JSON 基础类型（code: str, decision: str, evidence: dict）

#### 类型泄漏检查

✅ **通过：core 接口无运行时对象泄漏**

- `ContextV1`：只包含 JSON 可序列化字段（tool, params, result, step_id, session_id, state, metadata）
- `DecisionV1`：只包含 JSON 可序列化字段（code, decision, risk_level, evidence, message）
- 无 `Step`、`Run`、`Tool` 等运行时对象引用

#### Validator 接口统一

✅ **通过：统一 BaseValidator 接口**

- 所有 validators 实现 `BaseValidator` 接口
- `evaluate(context: Context) -> List[Decision]` 统一签名
- `engine.py` 使用 `registry` 映射，不硬编码导入

#### 版本字段（低优先级）

⚠️ **版本字段缺失（低优先级）**

- `PolicyV1`、`ContextV1`、`DecisionV1` 缺少 `version` 字段
- **影响**：长期演进可能需要版本兼容性处理
- **优先级**：低（不影响当前抽取）

---

## 4. 当前结论：是否可抽取？

### Current Status

✅ **Extractable validate-core**

### 修复完成情况

#### 高优先级（阻塞抽取 - 已完成）

- ✅ 移除全局 registry（registry 单例上移到 API 层）
- ✅ 移除时间副作用（改为从 context.metadata 注入，使用 MetaKeys 常量，无 fallback）
- ✅ 移除环境变量依赖（改为从 context.metadata 注入，使用 MetaKeys 常量，无 fallback）
- ✅ Loader 去 I/O（core 层提供纯解析函数，API 层负责 I/O）

#### 中优先级（已修复）

- ✅ contract.py 已重构为标准 BaseValidator 实现（OutputContractValidator）
- ✅ 移除了 ValidationResult/PreconditionValidator/PostconditionValidator
- ✅ 使用 ContextV1 和 Decision 统一接口
- ✅ 移除了 strict_mode 参数（由 engine 处理）
- ✅ 统一了 code 命名（FC_OUTPUT_CONTRACT_*）
- ✅ 最小化了 evidence（无 raw_excerpt）
- ✅ 明确了 schema 是 JSON Schema（docstring 说明）
- ✅ Metadata Key 常量化（定义 MetaKeys 常量，避免魔术字符串）

#### 低优先级（影响长期演进）

- ⚠️ 添加 version 字段
- ⚠️ 版本兼容性处理

### 修复后状态

✅ **可抽取**（核心验证逻辑已满足硬标准）

核心验证逻辑（contracts + validator + engine + registry）已满足硬标准，可以独立抽取。

---

## 5. 为什么现在不抽取，但要"为抽取而设计"

### 核心论点

**抽取 ≠ 现在就做**

但如果现在不约束边界，将来一定抽不出来。

### 设计哲学

> **We do not extract validate-core today, but we design FailCore as if we will.**

### 为什么现在不抽取？

1. **开发效率**：当前在 FailCore 内部开发，共享代码和工具链更高效
2. **迭代速度**：与 executor、trace、ui 等模块紧密集成，便于快速迭代
3. **测试便利**：可以在完整环境中进行端到端测试

### 为什么要"为抽取而设计"？

1. **边界清晰**：硬边界定义帮助我们拒绝不合理的 feature creep
2. **架构健康**：强制依赖注入、无全局状态、无副作用，让代码更易测试和维护
3. **未来选项**：当需要时（Rust 实现、WASM SDK、Mobile SDK），可以快速抽取
4. **技术债务控制**：避免"先实现，后重构"的常见陷阱

### 设计约束的价值

- **拒绝不合理需求**：当有人提出"在 validate-core 里加个文件读写"时，硬边界帮助我们说"不"
- **保持代码质量**：强制纯函数、依赖注入、无副作用，让代码更可靠
- **降低重构成本**：如果将来需要抽取，成本会很低

---

## 6. 非目标（Non-Goals）

明确写清楚 validate-core 不做什么，这会帮你以后拒绝很多"顺手加一下"的需求。

### Validate Core 不做什么

- ❌ **不执行 tool**：Validate Core 只做决策，不执行任何工具调用
- ❌ **不做 trace**：Validate Core 不记录执行轨迹，不依赖 trace 系统
- ❌ **不关心 UI**：Validate Core 不生成 UI 组件，不依赖 UI 框架
- ❌ **不访问系统资源**：Validate Core 不读写文件、不访问网络、不访问数据库
- ❌ **不依赖 LLM**：Validate Core 是确定性决策引擎，不调用 LLM API
- ❌ **不做执行编排**：Validate Core 不管理执行流程，不处理并发、重试等

### 这些功能在哪里？

- **Tool 执行**：`failcore/core/executor/`
- **Trace 记录**：`failcore/core/trace/`
- **UI 渲染**：`failcore/web/`、`failcore/cli/renderers/`
- **系统资源访问**：由宿主（FailCore executor）注入到 Context.metadata
- **LLM 调用**：`failcore/core/tools/`、外部 LLM SDK
- **执行编排**：`failcore/core/executor/`

### 边界清晰的好处

当有人提出以下需求时，我们可以明确拒绝：

- "在 validate-core 里加个文件读取功能" → ❌ 违反无 I/O 原则
- "在 validate-core 里加个 trace 记录" → ❌ 违反无 trace 依赖原则
- "在 validate-core 里加个 LLM 调用" → ❌ 违反确定性决策原则

---

## 总结

Validate Core 是 FailCore 的决策引擎，它的硬边界定义帮助我们：

1. **保持架构清晰**：明确什么属于 core，什么不属于
2. **控制技术债务**：避免不合理的功能蔓延
3. **保持抽取选项**：未来可以快速抽取为独立模块
4. **提升代码质量**：强制纯函数、依赖注入、无副作用

**记住**：Validate Core answers only one question: "Given this context and this policy, should this action be allowed?"
