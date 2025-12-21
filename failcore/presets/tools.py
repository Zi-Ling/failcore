# failcore/presets/tools.py
"""
Tool Presets - Demo tool collections

These are minimal tool sets for testing and demonstration.
NOT intended as builtin tools.
"""


def demo_tools():
    """
    Demo tool set - for testing and demonstration only
    
    Tool names are prefixed with "demo." to clearly identify demo traffic
    in traces, policies, and validators.
    
    Includes:
    - demo.divide: Division (demonstrates failure on divide-by-zero)
    - demo.echo: Echo input (demonstrates success)
    - demo.fail: Intentional failure (for testing error handling)
    
    Returns:
        dict: Tool name -> tool function mapping
    
    Example:
        >>> from failcore import Session, presets
        >>> session = Session()
        >>> for name, fn in presets.demo_tools().items():
        ...     session.register(name, fn)
        >>> result = session.call("demo.divide", a=6, b=2)
    
    Note:
        These are not builtin tools, just a demo collection.
        In real projects, users should register their own tools.
        
        The "demo." prefix ensures:
        - Clear identification in traces
        - Policy/validator rules can easily target/exclude demos
        - No confusion with production tools
    """
    def divide(a: float, b: float) -> float:
        """Division (fails when b=0)"""
        return a / b
    
    def echo(text: str) -> str:
        """Echo input text"""
        return text
    
    def fail(message: str = "Intentional failure") -> None:
        """Intentionally fail"""
        raise RuntimeError(message)
    
    # Suggestion #6: Prefix all demo tools with "demo."
    return {
        "demo.divide": divide,
        "demo.echo": echo,
        "demo.fail": fail,
    }


__all__ = ["demo_tools"]

