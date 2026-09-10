"""Development test host: forwards MCP JSON-RPC only, with no editor logic.

Usage: python scripts/mcp_acceptance_client.py tools/list '{}'
       python scripts/mcp_acceptance_client.py tools/call '{"name":...,"arguments":...}'
Native MCP content is preserved verbatim so a test host can display image/audio.
This is acceptance infrastructure; normal users connect their MCP client directly.
"""
import json
import subprocess
import sys
from pathlib import Path


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    method = sys.argv[1]
    params = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    url = sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:8321"
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-11-25", "capabilities": {},
            "clientInfo": {"name": "code-blind-acceptance-host", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": method, "params": params},
    ]
    process = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", "local_editor", "mcp", "--url", url],
        input="\n".join(json.dumps(m, ensure_ascii=False) for m in messages) + "\n",
        capture_output=True, text=True, encoding="utf-8", timeout=150,
        cwd=Path(__file__).resolve().parents[1])
    responses = [json.loads(line) for line in process.stdout.splitlines() if line.strip()]
    response = next((r for r in responses if r.get("id") == 2), None)
    if response is None:
        raise RuntimeError(process.stderr or "MCP did not return a response")
    print(json.dumps(response, ensure_ascii=False, separators=(",", ":")))
    return 1 if "error" in response or response.get("result", {}).get("isError") else 0


if __name__ == "__main__":
    raise SystemExit(main())
