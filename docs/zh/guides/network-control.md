# 网络控制

本指南介绍如何使用 FailCore 保护网络操作，防止 SSRF 攻击。

---

## 概述

网络安全策略（`net_safe`）提供：

- ✅ SSRF 防护
- ✅ 私有网络阻止
- ✅ 协议限制
- ✅ 域名白名单（可选）

---

## 基本用法

### 启用网络安全

```python
from failcore import run, guard
from failcore.core.errors import FailCoreError
import urllib.request

with run(policy="net_safe") as ctx:
    @guard()
    def fetch_url(url: str) -> str:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.read().decode('utf-8')
    
    # 这会成功（公共 URL）
    result = fetch_url("https://httpbin.org/get")
    
    # 这会被阻止（SSRF）
    try:
        fetch_url("http://169.254.169.254/latest/meta-data/")
    except FailCoreError:
        print("SSRF 被阻止")
```

---

## SSRF 防护

### 被阻止的地址

`net_safe` 策略自动阻止以下地址：

1. **本地回环**
   - `127.0.0.1`
   - `localhost`
   - `::1`

2. **私有网络**
   - `10.0.0.0/8`
   - `172.16.0.0/12`
   - `192.168.0.0/16`

3. **链路本地**
   - `169.254.0.0/16`

4. **AWS 元数据服务**
   - `169.254.169.254`

### 示例

```python
with run(policy="net_safe") as ctx:
    @guard()
    def fetch_url(url: str):
        import urllib.request
        with urllib.request.urlopen(url) as response:
            return response.read()
    
    # ❌ 本地回环
    try:
        fetch_url("http://127.0.0.1:8080/api")
    except FailCoreError as e:
        print(f"被阻止: {e.message}")
        # 输出: 被阻止: 私有网络访问被阻止：'127.0.0.1'
    
    # ❌ 私有网络
    try:
        fetch_url("http://192.168.1.1/admin")
    except FailCoreError:
        print("私有网络被阻止")
    
    # ❌ AWS 元数据
    try:
        fetch_url("http://169.254.169.254/latest/meta-data/")
    except FailCoreError:
        print("AWS 元数据服务被阻止")
    
    # ✅ 公共 URL
    result = fetch_url("https://api.example.com/data")
```

---

## 协议限制

### 允许的协议

默认只允许：
- `http`
- `https`

### 被阻止的协议

以下协议被阻止：
- `file://`
- `ftp://`
- `gopher://`
- 其他非 HTTP 协议

### 示例

```python
with run(policy="net_safe") as ctx:
    @guard()
    def fetch_url(url: str):
        import urllib.request
        with urllib.request.urlopen(url) as response:
            return response.read()
    
    # ✅ HTTP
    fetch_url("http://example.com")
    
    # ✅ HTTPS
    fetch_url("https://example.com")
    
    # ❌ 文件协议
    try:
        fetch_url("file:///etc/passwd")
    except FailCoreError:
        print("文件协议被阻止")
```

---

## 端口限制

### 允许的端口

默认允许：
- `80` (HTTP)
- `443` (HTTPS)
- `8080` (HTTP 备用)
- `8443` (HTTPS 备用)

### 自定义端口

```python
from failcore.core.validate.templates import net_safe_policy

# 创建自定义策略
policy = net_safe_policy()
policy.validators["network_ssrf"].config["allowed_ports"] = [80, 443, 3000, 8000]
```

---

## 域名白名单

### 启用白名单

```python
from failcore.core.validate.templates import net_safe_policy

# 创建带白名单的策略
policy = net_safe_policy(allowlist=[
    "https://api.example.com/*",
    "https://*.trusted.com/*",
    "https://service.internal.com/*"
])
```

### 白名单格式

支持以下格式：
- 精确匹配：`https://api.example.com`
- 路径通配符：`https://api.example.com/*`
- 子域名通配符：`https://*.example.com/*`

### 示例

```python
# 使用白名单策略
policy = net_safe_policy(allowlist=[
    "https://api.example.com/*",
    "https://*.trusted.com/*"
])

# 只有白名单中的 URL 被允许
# 所有其他 URL（包括公共 URL）被阻止
```

---

## URL 参数检测

FailCore 自动检测以下参数名称中的 URL：

- `url`
- `uri`
- `endpoint`
- `host`

### 自定义 URL 参数

```yaml
validators:
  network_ssrf:
    config:
      url_params: ["custom_url_param", "api_endpoint"]
```

---

## 错误消息

FailCore 提供详细的错误消息：

```python
try:
    fetch_url("http://169.254.169.254/latest/meta-data/")
except FailCoreError as e:
    print(e.message)
    # 输出: 私有网络访问被阻止：'169.254.169.254'
    
    if e.suggestion:
        print(e.suggestion)
        # 输出: 仅使用公共互联网 URL。私有 IP 和 localhost 因安全原因被阻止。
    
    print(e.result.error_code)
    # 输出: SSRF_BLOCKED
```

---

## 最佳实践

### 1. 始终使用 net_safe 策略

```python
# 好：启用网络安全
with run(policy="net_safe") as ctx:
    pass

# 不好：无网络保护
with run(policy="fs_safe") as ctx:
    # 网络操作不受保护
    pass
```

### 2. 使用 HTTPS

```python
# 好：HTTPS
fetch_url("https://api.example.com/data")

# 不好：HTTP（如果可能，使用 HTTPS）
fetch_url("http://api.example.com/data")
```

### 3. 测试 SSRF 防护

```python
def test_ssrf_protection():
    with run(policy="net_safe") as ctx:
        @guard()
        def fetch_url(url: str):
            import urllib.request
            with urllib.request.urlopen(url) as response:
                return response.read()
        
        # 应该成功
        fetch_url("https://httpbin.org/get")
        
        # 应该被阻止
        try:
            fetch_url("http://169.254.169.254/latest/meta-data/")
            assert False, "应该被阻止"
        except FailCoreError:
            pass  # 预期行为
```

### 4. 监控网络请求

```python
with run(policy="net_safe") as ctx:
    @guard()
    def fetch_url(url: str):
        import urllib.request
        with urllib.request.urlopen(url) as response:
            return response.read()
    
    fetch_url("https://api.example.com/data")
    
    # 查看追踪文件
    print(f"追踪文件: {ctx.trace_path}")
    # 运行: failcore show {ctx.trace_path}
```

---

## 高级配置

### 禁用内部网络阻止

```python
from failcore.core.validate.templates import net_safe_policy

# 创建允许内部网络的策略（不推荐）
policy = net_safe_policy()
policy.validators["network_ssrf"].config["block_internal"] = False
```

### 自定义协议列表

```python
from failcore.core.validate.templates import net_safe_policy

# 允许 FTP（不推荐）
policy = net_safe_policy()
policy.validators["network_ssrf"].config["allowed_schemes"] = ["http", "https", "ftp"]
```

### 禁止用户信息

默认禁止 URL 中包含凭据（如 `http://user:pass@example.com`）：

```python
# 默认禁止
policy.validators["network_ssrf"].config["forbid_userinfo"] = True
```

---

## 常见问题

### Q: 为什么公共 URL 也被阻止？

A: 如果启用了域名白名单，只有白名单中的 URL 被允许。禁用白名单或添加 URL 到白名单。

### Q: 如何允许特定内部服务？

A: 不推荐，但如果必须，可以：
1. 禁用 `block_internal`
2. 或使用代理/网关将内部服务暴露为公共 URL

### Q: DNS 重绑定攻击如何防护？

A: FailCore 的当前实现不解析 DNS。如果需要更强的防护，在应用层添加 DNS 解析和缓存。

---

## 总结

网络安全策略提供：

- ✅ SSRF 防护
- ✅ 私有网络阻止
- ✅ 协议限制
- ✅ 可选的域名白名单

---

## 下一步

- [文件系统安全](fs-safety.md) - 了解文件系统保护
- [成本控制](cost-guard.md) - 了解成本限制
- [策略](../concepts/policy.md) - 深入了解策略系统
