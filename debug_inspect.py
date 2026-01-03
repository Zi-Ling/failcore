"""Debug inspect.getsource() behavior"""
import inspect

def test_func():
    def quick_tool():
        return "success"
    
    try:
        source = inspect.getsource(quick_tool)
        print("SUCCESS: Got source")
        print(source)
    except Exception as e:
        print(f"FAILED: {e}")
        print(f"Exception type: {type(e)}")

test_func()
