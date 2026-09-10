"""Run ``python -m local_editor serve`` or ``python -m local_editor mcp``."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="本地剪輯工作台與 Agent MCP")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="啟動本地剪輯工作台")
    serve.add_argument("--port", type=int, default=8321)
    serve.add_argument("--data-dir", default=".local-editor")
    serve.add_argument("--open", action="store_true", help="啟動後開啟瀏覽器")
    mcp = commands.add_parser("mcp", help="啟動 stdio MCP，連線至同一個工作台")
    mcp.add_argument("--url", default="http://127.0.0.1:8321")
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            from .server import serve_forever
            if not 0 < args.port < 65536:
                parser.error("--port 必須介於 1 與 65535")
            serve_forever(args.data_dir, args.port, open_browser=args.open)
        else:
            from .mcp import run_stdio
            return run_stdio(args.url)
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError) as exc:
        print(f"本地剪輯器：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
