# CLI 工具

FailCore 提供命令行工具用于管理追踪、生成报告和分析执行。

---

## 命令概览

```bash
failcore <command> [options]
```

主要命令：
- `list` - 列出最近的运行
- `show` - 显示运行详情
- `report` - 生成 HTML 报告
- `audit` - 审计追踪文件
- `trace` - 追踪文件管理
- `replay` - 重放执行
- `policy` - 策略管理
- `ui` - 启动 Web UI

---

## list - 列出运行

列出最近的运行记录。

### 用法

```bash
failcore list
failcore list --limit 20
```

### 输出

```
Run ID                    Date       Status    Steps
abc123...                 2024-01-15 SUCCESS   5
def456...                 2024-01-15 BLOCKED   2
```

### 选项

- `--limit <n>`：显示最近 n 条记录（默认：10）

---

## show - 显示详情

显示运行或步骤的详细信息。

### 用法

```bash
# 显示最后一次运行
failcore show

# 显示特定运行
failcore show --run <run_id>

# 显示步骤列表
failcore show --steps

# 只显示错误/被阻止的步骤
failcore show --errors

# 显示特定步骤
failcore show --step <step_id>

# 详细输出
failcore show --verbose
```

### 输出示例

```
Run: abc123...
Date: 2024-01-15 10:30:00
Status: SUCCESS
Steps: 5
Duration: 12.5s

Steps:
  1. write_file (SUCCESS) - 2.3ms
  2. read_file (SUCCESS) - 1.1ms
  3. delete_file (BLOCKED) - 0.5ms
```

### 选项

- `--run <run_id>`：显示特定运行
- `--last`：显示最后一次运行（默认）
- `--steps`：显示步骤列表
- `--errors`：只显示错误/被阻止的步骤
- `--step <step_id>`：显示特定步骤详情
- `--verbose, -v`：详细输出

---

## report - 生成报告

生成 HTML 执行报告。

### 用法

```bash
# 为最后一次运行生成报告
failcore report

# 从追踪文件生成报告
failcore report --trace trace.jsonl
```

### 输出

生成 HTML 文件，包含：
- 执行摘要
- 时间线
- 步骤详情
- 违规统计
- 成本分析

### 选项

- `--trace <file>`：指定追踪文件路径
- `--html`：生成 HTML 格式（默认）

---

## audit - 审计追踪

分析追踪文件，识别违规和异常。

### 用法

```bash
# 审计最后一次运行
failcore audit

# 审计特定追踪文件
failcore audit --trace trace.jsonl

# 显示最近的违规
failcore audit --recent
```

### 输出

```
审计报告
========

违规统计:
  - 策略违规: 2
  - 副作用边界跨越: 1
  - 成本超限: 0

异常模式:
  - 路径遍历尝试: 1
  - SSRF 尝试: 1
```

### 选项

- `--trace <file>`：指定追踪文件
- `--recent`：显示最近的违规

---

## trace - 追踪管理

管理追踪文件。

### 子命令

#### ingest - 导入追踪

```bash
# 导入追踪文件到数据库
failcore trace ingest trace.jsonl
```

#### list - 列出追踪

```bash
# 列出所有追踪文件
failcore trace list
```

---

## replay - 重放执行

重放历史执行。

### 子命令

#### report - 报告模式

```bash
# 使用新策略重放
failcore replay report trace.jsonl --policy new_policy.yaml
```

#### mock - 模拟模式

```bash
# 模拟执行（不实际运行工具）
failcore replay mock trace.jsonl
```

### 选项

- `--policy <file>`：使用新策略
- `--mode <mode>`：重放模式（report/mock）

---

## policy - 策略管理

管理验证策略。

### 子命令

#### init - 初始化策略目录

```bash
# 创建策略文件
failcore policy init
```

创建：
- `active.yaml`：活动策略
- `shadow.yaml`：影子策略
- `breakglass.yaml`：紧急覆盖

#### list-validators - 列出验证器

```bash
# 列出所有可用验证器
failcore policy list-validators
```

#### show - 显示策略

```bash
# 显示活动策略
failcore policy show

# 显示影子策略
failcore policy show --type shadow

# 显示合并策略
failcore policy show --type merged
```

#### explain - 解释策略决策

```bash
# 解释为什么工具被阻止
failcore policy explain --tool write_file --param path=../../etc/passwd
```

### 选项

- `--type <type>`：策略类型（active/shadow/breakglass/merged）
- `--format <format>`：输出格式（yaml/json）

---

## ui - Web UI

启动 Web 界面。

### 用法

```bash
# 启动 Web UI
failcore ui

# 指定端口
failcore ui --port 9000

# 不自动打开浏览器
failcore ui --no-browser

# 开发模式
failcore ui --dev
```

### 选项

- `--host <host>`：绑定主机（默认：127.0.0.1）
- `--port <port>`：绑定端口（默认：8765）
- `--no-browser`：不自动打开浏览器
- `--dev`：开发模式（自动重载）

---

## 常用组合

### 查看最近的运行

```bash
# 列出运行
failcore list

# 查看详情
failcore show --run <run_id>

# 生成报告
failcore report --trace <trace_file>
```

### 调试问题

```bash
# 查看错误
failcore show --errors

# 审计追踪
failcore audit

# 解释策略决策
failcore policy explain --tool <tool> --param <param>
```

### 策略测试

```bash
# 初始化策略
failcore policy init

# 查看策略
failcore policy show

# 使用新策略重放
failcore replay report trace.jsonl --policy new_policy.yaml
```

---

## 环境变量

- `FAILCORE_DB_PATH`：数据库路径
- `FAILCORE_TRACE_DIR`：追踪文件目录
- `FAILCORE_POLICY_DIR`：策略文件目录

---

## 常见问题

### Q: 数据库在哪里？

A: 默认在 `<项目根目录>/.failcore/db.sqlite`。使用 `FAILCORE_DB_PATH` 环境变量自定义。

### Q: 如何导入追踪文件？

A: 使用 `failcore trace ingest <trace_file>`。

### Q: 报告保存在哪里？

A: 报告保存在当前目录，文件名格式：`report_<run_id>.html`。

---

## 总结

CLI 工具提供：

- ✅ 运行管理
- ✅ 追踪查看
- ✅ 报告生成
- ✅ 策略管理
- ✅ Web UI

---

## 下一步

- [Web UI](ui.md) - 了解 Web 界面
- [报告](reports.md) - 了解报告功能
- [策略管理](../concepts/policy.md) - 深入了解策略
