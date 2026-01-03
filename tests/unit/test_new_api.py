"""
测试新的 FailCore API
验证 run + guard 方案是否正常工作
"""

# 方案1：显式 run（同一个 trace / sandbox / policy）
def test_explicit_run():
    from failcore import run
    
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
        return f"写入文件：{path}"
    
    with run(policy="fs_safe", sandbox="./data", strict=True) as ctx:
        ctx.tool(write_file)
        result = ctx.call("write_file", path="../../a.txt", content="hi")
        print(f"执行结果：{result}")
        print(f"追踪路径：{ctx.trace_path}")


# 方案2：session + guard（@guard() 自动继承 session 配置）
def test_guard_decorator():
    from failcore import run, guard
    
    with run(policy="fs_safe", sandbox="./data", strict=True) as ctx:
        @guard()
        def write_file(path: str, content: str):
            with open(path, "w") as f:
                f.write(content)
            return f"写入文件：{path}"
        
        result = write_file(path="../../a.txt", content="hi")
        print(f"执行结果：{result}")
        print(f"追踪路径：{ctx.trace_path}")


# 方案3：支持不带括号的装饰器
def test_guard_no_parens():
    from failcore import run, guard
    
    with run(policy="fs_safe", sandbox="./data") as ctx:
        @guard
        def read_config():
            return {"version": "1.0"}
        
        result = read_config()
        print(f"执行结果：{result}")


if __name__ == "__main__":
    print("=" * 60)
    print("测试方案1：显式 run")
    print("=" * 60)
    test_explicit_run()
    
    print("\n" + "=" * 60)
    print("测试方案2：guard 装饰器")
    print("=" * 60)
    test_guard_decorator()
    
    print("\n" + "=" * 60)
    print("测试方案3：guard 不带括号")
    print("=" * 60)
    test_guard_no_parens()
    
    print("\n所有测试完成！")
