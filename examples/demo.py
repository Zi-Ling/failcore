"""
Minimal FailCore Demo - Just 10 lines of code
"""

from failcore import Session

with Session() as session:
    session.register("add", lambda a, b: a + b)
    session.register("divide", lambda a, b: a / b)

    session.call("add", a=1, b=2)
    session.call("divide", a=10, b=0)

print("Run `failcore show` to inspect the trace.")
