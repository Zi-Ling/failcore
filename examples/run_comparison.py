#!/usr/bin/env python3
"""
运行 LangChain 对比示例，展示 FailCore v0.1.2 的优势

Usage:
    python examples/run_comparison.py
"""

import subprocess
import sys
import os

def run_example(script_name: str, title: str):
    """运行示例脚本"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")
    
    result = subprocess.run(
        [sys.executable, script_name],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        capture_output=False
    )
    
    return result.returncode == 0

def main():
    print("=" * 80)
    print("  FailCore v0.1.2 - LangChain Integration Comparison")
    print("=" * 80)
    
    examples_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 运行纯 LangChain 示例
    success1 = run_example(
        os.path.join(examples_dir, "langchain.py"),
        "示例 1: 纯 LangChain (无 trace)"
    )
    
    # 运行 FailCore 集成示例
    success2 = run_example(
        os.path.join(examples_dir, "langchain_with_failcore.py"),
        "示例 2: LangChain + FailCore v0.1.2 (完整 trace)"
    )
    
    # 总结
    print("\n" + "=" * 80)
    print("  对比总结")
    print("=" * 80)
    print("\n纯 LangChain:")
    print("  ❌ 无 trace - 无法审计和重放")
    print("  ❌ 异常处理 - 难以定位问题")
    print("  ❌ 无策略控制 - 无法限制工具行为")
    print("  ❌ 无资源追踪 - 不知道消耗了多少 token/成本")
    
    print("\nFailCore v0.1.2 集成:")
    print("  ✅ 完整 trace - 可分析、可重放、可审计")
    print("  ✅ 结构化错误 - 明确的错误类型和严重级别")
    print("  ✅ 策略沙箱 - 防止越权操作")
    print("  ✅ 资源监控 - token、时间、成本统计")
    print("  ✅ 来源追踪 - provenance tracking")
    print("  ✅ 契约验证 - 自动检测输出漂移")
    
    print("\n查看生成的 trace:")
    print("  failcore show")
    print("  failcore list")
    print("  failcore validate .failcore/examples/langchain_demo.jsonl")
    
    print("\n" + "=" * 80)
    
    return 0 if (success1 or success2) else 1

if __name__ == "__main__":
    sys.exit(main())

