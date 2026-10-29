#!/usr/bin/env python3
"""Entry point for `nix run`. resale-watch [serve|web|poll|mcp]
serve (default): web UI + poll loop in one process.
Env: DB (default $XDG_DATA_HOME/resale-watch/searches.db), HOST, PORT, POLL_TICK_S; see README for the rest."""
import os, sys, threading, time, traceback

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if "DB" not in os.environ:
        d = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "resale-watch")
        os.makedirs(d, exist_ok=True)
        os.environ["DB"] = os.path.join(d, "searches.db")
    import poller  # reads DB at import
    poller.connect().close()
    if cmd == "poll":
        poller.main()
    elif cmd == "mcp":
        import mcp_server
        mcp_server.mcp.run(transport=os.environ.get("MCP_TRANSPORT", "stdio"))
    elif cmd in ("serve", "web"):
        if cmd == "serve":
            threading.Thread(target=poll_loop, args=(poller,), daemon=True).start()
        import uvicorn, web
        host, port = os.environ.get("HOST", "127.0.0.1"), int(os.environ.get("PORT", "8080"))
        print(f"db {os.environ['DB']}  ui http://{host}:{port}", file=sys.stderr)
        uvicorn.run(web.app, host=host, port=port)
    else:
        sys.exit(__doc__)

def poll_loop(poller):
    # Tick only checks which searches are due; per-search interval_s gates real requests
    tick = int(os.environ.get("POLL_TICK_S", "60"))
    while True:
        try: poller.main()
        except Exception: traceback.print_exc()
        time.sleep(tick)

if __name__ == "__main__":
    main()
