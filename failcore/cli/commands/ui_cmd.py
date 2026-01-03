# failcore/cli/commands/ui_cmd.py
"""
Web UI command for FailCore.

Launches a FastAPI + HTMX web interface for viewing traces, runs, and audit reports.
"""

import sys
import webbrowser
from pathlib import Path


def register_command(subparsers):
    """Register the 'ui' command."""
    parser = subparsers.add_parser(
        "ui",
        help="Launch web UI for viewing traces and reports"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind the server (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to bind the server (default: 8765)"
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open browser automatically"
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Enable development mode (auto-reload)"
    )
    parser.set_defaults(func=run_ui)


def run_ui(args):
    """Run the FailCore web UI."""
    try:
        import uvicorn
        from failcore.web.app import create_app
    except ImportError:
        print("Error: Web UI dependencies not installed.", file=sys.stderr)
        print("Install with: pip install failcore[ui]", file=sys.stderr)
        return 1
    
    host = args.host
    port = args.port
    
    print(f"🚀 Starting FailCore Web UI...")
    print(f"📍 URL: http://{host}:{port}")
    print(f"📊 View traces, runs, and audit reports in your browser")
    print()
    
    # Open browser if not disabled
    if not args.no_browser:
        url = f"http://{host}:{port}"
        print(f"🌐 Opening browser: {url}")
        webbrowser.open(url)
    
    # Create FastAPI app
    app = create_app()
    
    # Run uvicorn server
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        reload=args.dev,
    )
    
    return 0


__all__ = ["register_command", "run_ui"]
