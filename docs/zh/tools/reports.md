# 报告

FailCore 可以生成详细的执行报告，用于分析和审计。

---

## 生成报告

### 基本用法

```bash
# 为最后一次运行生成报告
failcore report

# 从追踪文件生成报告
failcore report --trace trace.jsonl
```

### 输出

生成 HTML 文件：`report_<run_id>.html`

---

## 报告内容

### 1. 执行摘要

- Run ID
- 创建时间
- 持续时间
- 总步骤数
- 成功/失败/被阻止统计

### 2. 时间线

可视化执行时间线：
- 每个步骤的时间点
- 步骤状态（成功/失败/被阻止）
- 持续时间

### 3. 步骤详情

每个步骤的详细信息：
- 工具名称
- 参数
- 策略决策
- 执行结果
- 错误信息（如果有）

### 4. 违规统计

- 策略违规数量
- 副作用边界跨越
- 成本超限
- 异常模式

### 5. 成本分析

- 总成本
- 每个步骤的成本
- 成本趋势
- 预算使用情况

---

## 报告格式

### HTML 报告

默认生成 HTML 格式，包含：
- 交互式时间线
- 可折叠的步骤详情
- 图表和可视化
- 可打印版本

### JSON 报告

```bash
# 生成 JSON 格式（如果支持）
failcore report --format json
```

---

## 使用场景

### 1. 事后分析

```bash
# 生成报告
failcore report --trace trace.jsonl

# 在浏览器中打开
open report_abc123.html
```

### 2. 审计

```bash
# 生成审计报告
failcore audit --trace trace.jsonl

# 生成详细报告
failcore report --trace trace.jsonl
```

### 3. 分享结果

```bash
# 生成报告
failcore report --trace trace.jsonl

# 分享 HTML 文件
# report_abc123.html
```

---

## 报告示例

### 执行摘要

```
执行摘要
========

Run ID: abc123...
创建时间: 2024-01-15 10:30:00
持续时间: 12.5s
总步骤: 5

统计:
  - 成功: 3
  - 失败: 1
  - 被阻止: 1
```

### 时间线

```
时间线
======

10:30:00.000  write_file (SUCCESS)     2.3ms
10:30:00.002  read_file (SUCCESS)      1.1ms
10:30:00.003  delete_file (BLOCKED)    0.5ms
10:30:00.004  fetch_url (SUCCESS)      8.5ms
10:30:00.012  process_data (FAIL)      0.1ms
```

### 违规统计

```
违规统计
========

策略违规: 1
  - delete_file: 路径遍历检测到

副作用边界跨越: 0

成本超限: 0
```

---

## 自定义报告

### 包含成本

```bash
failcore report --trace trace.jsonl --include-cost
```

### 只显示错误

```bash
failcore report --trace trace.jsonl --errors-only
```

---

## 报告最佳实践

### 1. 定期生成

```bash
# 每天生成报告
failcore report
```

### 2. 存档报告

```bash
# 生成报告并存档
failcore report --trace trace.jsonl
mv report_*.html reports/
```

### 3. 分析趋势

```bash
# 生成多个报告
for trace in traces/*.jsonl; do
    failcore report --trace "$trace"
done

# 比较报告
```

---

## 报告 API

### 程序化生成

```python
from failcore.cli.views.trace_report import build_report_view_from_trace
from failcore.cli.renderers.html import HtmlRenderer

# 构建报告视图
view = build_report_view_from_trace("trace.jsonl")

# 渲染为 HTML
renderer = HtmlRenderer()
html = renderer.render(view)

# 保存
with open("report.html", "w") as f:
    f.write(html)
```

---

## 常见问题

### Q: 报告保存在哪里？

A: 保存在当前目录，文件名格式：`report_<run_id>.html`。

### Q: 如何自定义报告格式？

A: 使用报告 API 程序化生成自定义格式。

### Q: 报告可以导出为其他格式吗？

A: 目前只支持 HTML 格式。可以使用报告 API 生成其他格式。

---

## 总结

报告功能提供：

- ✅ 详细的执行分析
- ✅ 可视化时间线
- ✅ 违规统计
- ✅ 成本分析

---

## 下一步

- [CLI 工具](cli.md) - 了解命令行工具
- [Web UI](ui.md) - 了解 Web 界面
- [追踪和重放](../concepts/trace-and-replay.md) - 了解追踪系统
