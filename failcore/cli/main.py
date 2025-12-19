# failcore/cli/main.py
import argparse

from failcore.cli.show import show_trace
from failcore.core.bootstrap import create_standard_executor
from failcore.core.step import Step, RunContext
from failcore.core.tools.registry import ToolRegistry


def run_demo(args):
    tools = ToolRegistry()
    tools.register("divide", lambda a, b: a / b)

    executor = create_standard_executor(trace_path=args.trace, tools=tools)
    ctx = RunContext()

    step = Step(id="s1", tool="divide", params={"a": 6, "b": 2})
    result = executor.execute(step, ctx)

    print("=== RESULT ===")
    print(result)


def main():
    parser = argparse.ArgumentParser("failcore")
    sub = parser.add_subparsers(dest="command")

    # run
    run_p = sub.add_parser("run", help="run a demo step")
    run_p.add_argument("--trace", default="trace.jsonl")

    # show
    show_p = sub.add_parser("show", help="show trace summary")
    show_p.add_argument("trace")
    show_p.add_argument(
        "--last",
        action="store_true",
        help="show only the last run",
    )

    args = parser.parse_args()

    if args.command == "show":
        show_trace(args.trace, last=args.last)
    else:
        run_demo(args)


if __name__ == "__main__":
    main()
