"""Debug ProcessExecutor"""

from failcore.core.executor.process_executor import ProcessExecutor

def quick_tool():
    return "success"

executor = ProcessExecutor(
    working_dir="./test_workspace",
    timeout_s=5
)

result = executor.execute(quick_tool, {})
print("Result:", result)
print("OK:", result["ok"])
if not result["ok"]:
    print("Error:", result.get("error"))
