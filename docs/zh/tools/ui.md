# Web UI

FailCore 提供 Web 界面用于查看追踪、运行和审计报告。

---

## 启动 Web UI

### 基本用法

```bash
failcore ui
```

这将：
1. 启动 Web 服务器（默认：http://127.0.0.1:8765）
2. 自动打开浏览器

### 自定义配置

```bash
# 指定端口
failcore ui --port 9000

# 指定主机
failcore ui --host 0.0.0.0

# 不自动打开浏览器
failcore ui --no-browser

# 开发模式（自动重载）
failcore ui --dev
```

---

## 功能

### 1. 运行列表

显示所有运行记录：
- Run ID
- 创建时间
- 状态
- 步骤数
- 持续时间

### 2. 运行详情

查看单个运行的详细信息：
- 执行时间线
- 所有步骤
- 策略决策
- 副作用记录
- 成本分析

### 3. 步骤详情

查看单个步骤的详细信息：
- 工具名称和参数
- 策略检查结果
- 执行结果
- 错误信息（如果有）

### 4. 审计报告

生成审计报告：
- 违规统计
- 异常模式
- 时间线分析
- 成本趋势

---

## 界面概览

### 主页面

```
FailCore Web UI
===============

最近运行:
  [Run ID] [日期] [状态] [步骤] [操作]
  abc123... 2024-01-15 SUCCESS 5 [查看] [报告]
  def456... 2024-01-15 BLOCKED 2 [查看] [报告]
```

### 运行详情页

```
运行: abc123...
日期: 2024-01-15 10:30:00
状态: SUCCESS
步骤: 5
持续时间: 12.5s

时间线:
  [10:30:00] write_file (SUCCESS)
  [10:30:02] read_file (SUCCESS)
  [10:30:04] delete_file (BLOCKED)
  ...

步骤列表:
  1. write_file
     参数: {path: "test.txt", content: "Hello"}
     结果: SUCCESS
     耗时: 2.3ms
```

### 审计报告页

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

时间线:
  [图表显示执行时间线]
```

---

## 使用场景

### 1. 查看运行历史

```bash
# 启动 UI
failcore ui

# 在浏览器中：
# 1. 查看运行列表
# 2. 点击运行查看详情
# 3. 分析执行过程
```

### 2. 调试问题

```bash
# 启动 UI
failcore ui

# 在浏览器中：
# 1. 找到失败的运行
# 2. 查看步骤详情
# 3. 检查策略决策
# 4. 查看错误信息
```

### 3. 生成报告

```bash
# 启动 UI
failcore ui

# 在浏览器中：
# 1. 选择运行
# 2. 点击"生成报告"
# 3. 下载 HTML 报告
```

---

## 键盘快捷键

- `j` / `k`：上下导航
- `Enter`：打开详情
- `Esc`：返回
- `/`：搜索

---

## 配置

### 环境变量

- `FAILCORE_UI_HOST`：默认主机
- `FAILCORE_UI_PORT`：默认端口
- `FAILCORE_DB_PATH`：数据库路径

### 配置文件

Web UI 使用与 CLI 相同的配置：
- 数据库路径：`<项目根目录>/.failcore/db.sqlite`
- 追踪目录：`<项目根目录>/.failcore/runs/`

---

## 故障排除

### 端口被占用

```bash
# 使用其他端口
failcore ui --port 9000
```

### 数据库未找到

```bash
# 先导入追踪文件
failcore trace ingest trace.jsonl

# 然后启动 UI
failcore ui
```

### 浏览器未打开

```bash
# 手动打开
# http://127.0.0.1:8765
```

---

## 最佳实践

### 1. 定期查看

```bash
# 每天查看运行历史
failcore ui
```

### 2. 分析趋势

```bash
# 使用 UI 查看成本趋势
# 识别异常模式
```

### 3. 分享报告

```bash
# 生成报告并分享
failcore report --trace trace.jsonl
```

---

## 总结

Web UI 提供：

- ✅ 直观的界面
- ✅ 实时查看
- ✅ 交互式分析
- ✅ 报告生成

---

## 下一步

- [CLI 工具](cli.md) - 了解命令行工具
- [报告](reports.md) - 了解报告功能
- [追踪和重放](../concepts/trace-and-replay.md) - 了解追踪系统
