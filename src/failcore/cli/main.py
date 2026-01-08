# failcore/cli/main.py
import argparse

from failcore.cli.commands import sample_cmd
from failcore.cli.commands import validate_cmd
from failcore.cli.commands import list_cmd
from failcore.cli.commands import show_cmd
from failcore.cli.commands import report_cmd
from failcore.cli.commands import audit_cmd
from failcore.cli.commands import trace_cmd
from failcore.cli.commands import replay_cmd
from failcore.cli.commands import run_cmd
from failcore.cli.commands import ui_cmd
from failcore.cli.commands import proxy_cmd
from failcore.cli.commands import service_cmd


def main():
    parser = argparse.ArgumentParser(
        "failcore",
        description="FailCore - Observable and replayable tool execution engine"
    )
    sub = parser.add_subparsers(dest="command")

    # Register all commands
    sample_cmd.register_command(sub)
    validate_cmd.register_command(sub)
    list_cmd.register_command(sub)
    show_cmd.register_command(sub)
    report_cmd.register_command(sub)
    audit_cmd.register_command(sub)
    run_cmd.register_command(sub)
    ui_cmd.register_command(sub)
    proxy_cmd.register_command(sub)
    service_p = service_cmd.register_command(sub)
    trace_p = trace_cmd.register_command(sub)
    replay_p = replay_cmd.register_command(sub)

    args = parser.parse_args()

    # If no command provided, show help
    if not args.command:
        parser.print_help()
        return

    # Handle subcommands with nested parsers
    if args.command == "trace" and not args.trace_command:
        trace_p.print_help()
        return
    
    if args.command == "replay" and not args.replay_command:
        replay_p.print_help()
        return
    
    if args.command == "service" and not args.service_command:
        service_p.print_help()
        return

    # Call the registered function
    if hasattr(args, 'func'):
        return args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

