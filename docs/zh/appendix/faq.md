# 常见问题

本文档回答 FailCore 的常见问题。

---

## 安装和设置

### Q: 如何安装 FailCore？

A: 使用 pip 安装：

```bash
pip install failcore
```

详见[安装指南](../getting-started/install.md)。

### Q: 需要哪些依赖？

A: FailCore 核心运行时无依赖。可选功能需要额外依赖：

- `failcore[proxy]`：代理模式
- `failcore[langchain]`：LangChain 集成
- `failcore[ui]`：Web UI
- `failcore[mcp]`：MCP 支持

### Q: 支持哪些 Python 版本？

A: Python 3.10 或更高版本。

---

## 使用

### Q: 如何开始使用 FailCore？

A: 查看[快速开始](../getting-started/first-run.md)指南。

### Q: @guard() 和 ctx.tool() 有什么区别？

A: 两种方式功能相同：

- `@guard()`：装饰器风格，更简洁
- `ctx.tool()`：显式注册，更明确

选择您喜欢的风格即可。

### Q: 如何自定义策略？

A: 查看[策略文档](../concepts/policy.md)。

### Q: 追踪文件保存在哪里？

A: 默认在 `<项目根目录>/.failcore/runs/<日期>/<run_id>/trace.jsonl`。

可以使用 `trace` 参数自定义路径。

---

## 策略和安全

### Q: 策略检查的开销是多少？

A: 通常 < 1ms，对性能影响可以忽略不计。

### Q: 如何禁用策略？

A: 使用 `policy=None`：

```python
with run(policy=None) as ctx:
    pass
```

**注意：** 不推荐，会失去所有保护。

### Q: 如何允许特定路径？

A: 使用 `allow_outside_root` 和 `allowed_sandbox_roots`：

```python
with run(
    policy="fs_safe",
    sandbox="/tmp/external",
    allow_outside_root=True,
    allowed_sandbox_roots=[Path("/tmp")]
) as ctx:
    pass
```

### Q: 如何测试策略？

A: 使用策略重放：

```bash
failcore replay report trace.jsonl --policy new_policy.yaml
```

---

## 追踪和重放

### Q: 如何查看追踪文件？

A: 使用 CLI：

```bash
failcore show
failcore show --run <run_id>
```

### Q: 如何重放执行？

A: 使用重放命令：

```bash
failcore replay report trace.jsonl
failcore replay mock trace.jsonl
```

### Q: 追踪文件可以删除吗？

A: 可以，但建议保留用于审计和分析。

---

## 成本控制

### Q: 如何设置成本限制？

A: 使用 `max_cost_usd` 参数：

```python
with run(max_cost_usd=10.0) as ctx:
    pass
```

### Q: 成本估算准确吗？

A: 成本估算是基于模型定价的近似值。实际成本可能因折扣、批量定价等因素而有所不同。

### Q: 如何查看成本？

A: 使用报告命令：

```bash
failcore report --include-cost
```

---

## 故障排除

### Q: 工具调用被意外阻止

A: 检查：

1. 策略配置是否正确
2. 路径是否在沙箱内
3. 使用 `failcore policy explain` 查看原因

### Q: 追踪文件未生成

A: 检查：

1. `trace` 参数是否正确
2. 是否有写入权限
3. 使用 `ctx.trace_path` 查看路径

### Q: 数据库未找到

A: 先导入追踪文件：

```bash
failcore trace ingest trace.jsonl
```

### Q: Web UI 无法启动

A: 检查：

1. 是否安装了 `failcore[ui]`
2. 端口是否被占用
3. 查看错误消息

---

## 集成

### Q: 如何与 LangChain 集成？

A: 查看 LangChain 集成文档（如果存在）或使用 `failcore[langchain]`。

### Q: 如何与 MCP 集成？

A: 查看[MCP 保护指南](../guides/mcp-guard.md)。

### Q: 可以在 Docker 中使用吗？

A: 可以，FailCore 与 Docker 兼容。详见[为什么不是 Docker](../design/why-not-docker.md)。

---

## 性能

### Q: FailCore 会影响性能吗？

A: 开销很小（< 1ms 每次检查），对大多数应用可以忽略不计。

### Q: 如何优化性能？

A: 

1. 使用合适的策略（不要过度保护）
2. 禁用不需要的功能
3. 使用异步追踪记录

---

## 最佳实践

### Q: 应该使用哪个策略？

A: 

- 文件操作：`fs_safe`
- 网络操作：`net_safe`
- 综合：`safe`

### Q: 如何测试 FailCore？

A: 

1. 编写测试用例
2. 使用策略重放
3. 查看追踪文件

### Q: 如何监控 FailCore？

A: 

1. 定期查看追踪文件
2. 使用 Web UI
3. 生成报告

---

## 其他

### Q: FailCore 是开源的吗？

A: 是的，FailCore 在 Apache-2.0 许可证下发布。

### Q: 如何贡献？

A: 查看项目仓库的贡献指南。

### Q: 如何报告问题？

A: 在项目仓库中创建 issue。

---

## 总结

如果您有其他问题，请：

1. 查看相关文档
2. 搜索 issue
3. 创建新 issue

---

## 下一步

- [术语表](glossary.md) - 了解术语
- [路线图](roadmap.md) - 了解未来计划
- [快速开始](../getting-started/first-run.md) - 开始使用
