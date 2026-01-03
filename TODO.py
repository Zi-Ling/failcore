failcore/
├─ core/
│  ├─ tools/
│  │  ├─ __init__.py
│  │  ├─ invoker.py
│  │  ├─ provider.py
│  │  ├─ registry.py
│  │  ├─ spec.py
│  │  ├─ schema.py
│  │  ├─ metadata.py
│  │
│  │  └─ runtime/                        # ⭐ Tool Execution Runtime（最终命名）
│  │     ├─ __init__.py                   # 导出 ToolRuntime / CallContext / ToolResult
│  │     ├─ runtime.py                    # Runtime 主入口（原 gateway）
│  │     ├─ types.py                      # CallContext / ToolResult / ToolEvent / Error
│  │     ├─ errors.py                     # （可选）Runtime 级错误（非 transport 私有）
│  │
│  │     ├─ middleware/                   # ⭐ 可插拔治理（FailCore 灵魂）
│  │     │  ├─ __init__.py
│  │     │  ├─ base.py                    # Middleware Protocol
│  │     │  ├─ audit.py                   # ⭐ 审计（原 audit，已正名）
│  │     │  ├─ policy.py                  # Policy Gate（执行前拦截）
│  │     │  ├─ replay.py                  # Replay / Mock / Short-circuit
│  │     │  └─ receipt.py                 # 副作用收据汇总（可选）
│  │
│  │     ├─ transports/                   # ⭐ 抽象层（接口 + 工厂）
│  │     │  ├─ __init__.py
│  │     │  ├─ base.py                    # BaseTransport 接口
│  │     │  └─ factory.py                 # TransportFactory（延迟 import infra）
│  │
│  │     └─ registry/                     # （可选）运行时辅助
│  │        ├─ __init__.py
│  │        ├─ cache.py                   # tool list / schema cache
│  │        └─ normalize.py               # schema_view 最小平移（保留 raw）
│
│  ├─ policy/                             # 现有模块（不动）
│  ├─ audit/                              # ⭐ 原 audit → audit（核心实现）
│  ├─ replay/
│  ├─ trace/
│  ├─ executor/
│  ├─ step/
│  ├─ validate/
│  ├─ schemas/
│  └─ state/
│
├─ infra/
│  └─ transport/                          # ⭐ 具体协议 / IO / 进程细节
│     ├─ __init__.py
│     │
│     ├─ mcp/
│     │  ├─ __init__.py
│     │  ├─ transport.py                  # McpTransport(BaseTransport)
│     │  ├─ session.py                    # ⭐ Session / Process Manager（原 process）
│     │  ├─ codec.py                      # JSON-RPC 编解码 / id 路由
│     │  └─ security.py                   # ⭐ MCP 协议级安全防护
│     │
│     └─ proxy/
│        ├─ __init__.py
│        └─ transport.py                  # ProxyTransport（未来实现）
│
├─ cli/                                   # ⭐（预留）命令行 / Inspector
│  ├─ __init__.py
│  ├─ audit.py                            # failcore audit ...
│  └─ inspect.py                         # MCP Inspector / Viewer（未来）
│
├─ README.md
└─ pyproject.toml



#方案1 显式 run：（同一个 trace / sandbox / policy）
from failcore import run

with run(policy="fs_safe", sandbox="./sandbox", strict=True) as ctx:
    ctx.tool(write_file)
    ctx.call("write_file", path="a.txt", content="hi")
    print(ctx.trace_path)

#方案2 run + guard：（@guard() 自动继承 run 配置）
from failcore import run, guard

with run(policy="fs_safe", sandbox="./sandbox", strict=True) as ctx:
    @guard()
    def write_file(path: str, content: str):
        ...

    write_file("a.txt", "hi")
    print(ctx.trace_path)
