# 安装

本指南介绍如何安装 FailCore。

---

## 系统要求

- Python 3.10 或更高版本
- pip 包管理器

---

## 基础安装

### 使用 pip 安装

```bash
pip install failcore
```

这将安装 FailCore 的核心运行时。

---

## 可选依赖

### 代理模式（推荐）

如果您想使用 FailCore 作为 LLM SDK 的代理：

```bash
pip install "failcore[proxy]"
```

这将安装：
- FastAPI（Web 服务器）
- Uvicorn（ASGI 服务器）

### LangChain 集成

如果您使用 LangChain：

```bash
pip install "failcore[langchain]"
```

这将安装：
- langchain-core（>=0.3.0, <2.0.0）

### Web UI

如果您想使用 Web 界面查看追踪和报告：

```bash
pip install "failcore[ui]"
```

这将安装：
- FastAPI 和 Uvicorn
- Jinja2（模板引擎）

### MCP 支持

如果您使用 Model Context Protocol：

```bash
pip install "failcore[mcp]"
```

这将安装：
- mcp（>=1.2.0）

### OpenTelemetry 集成

如果您想导出遥测数据：

```bash
pip install "failcore[otel]"
```

这将安装：
- OpenTelemetry API 和 SDK
- OTLP HTTP 导出器

---

## 验证安装

安装完成后，验证 FailCore 是否正确安装：

```bash
failcore --version
```

或者：

```bash
python -c "import failcore; print(failcore.__version__)"
```

您应该看到版本号（例如：`0.1.3`）。

---

## 开发安装

如果您想从源代码安装或贡献代码：

```bash
# 克隆仓库
git clone https://github.com/your-org/failcore.git
cd failcore

# 安装开发依赖
pip install -e ".[dev]"
```

开发依赖包括：
- pytest（测试框架）
- build（构建工具）
- twine（发布工具）
- ruff（代码检查）

---

## 常见问题

### 安装失败

如果安装失败，请检查：

1. **Python 版本**
   ```bash
   python --version
   ```
   确保是 3.10 或更高版本。

2. **pip 版本**
   ```bash
   pip --version
   ```
   建议使用最新版本的 pip。

3. **网络连接**
   确保可以访问 PyPI。

### 依赖冲突

如果遇到依赖冲突：

1. 使用虚拟环境：
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install failcore
   ```

2. 检查现有依赖：
   ```bash
   pip list
   ```

### Windows 特定问题

在 Windows 上，某些功能可能需要额外配置：

- 路径处理：FailCore 自动处理 Windows 路径格式
- 权限：确保有足够的文件系统权限

---

## 下一步

安装完成后：

- [首次运行](first-run.md) - 运行您的第一个 FailCore 程序
- [发生了什么](what-just-happened.md) - 了解发生了什么

---

## 卸载

如果需要卸载 FailCore：

```bash
pip uninstall failcore
```

注意：这将卸载 FailCore，但不会删除已生成的追踪文件。
