# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
FastAPI Server and Uvicorn Runner for ReqTrace UI.
Binds strictly to IPv4 127.0.0.1, injects security middleware, mounts SPA assets,
and launches browser session with single-use ticket.
"""

import json
import logging
import os
import secrets
import socket
import sys
import tempfile
import webbrowser
from pathlib import Path
from typing import Optional
import uvicorn
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from reqtrace.ui.routes import create_api_router
from reqtrace.ui.security import (
    AccessLogTicketFilter,
    LocalhostSecurityMiddleware,
    SessionStore,
    TicketStore,
)


def _write_operator_state(port: int, operator_secret: str) -> Path:
    """Writes owner-only operator runtime credentials for `reqtrace ticket`."""
    payload = json.dumps({
        "port": port,
        "operator_secret": operator_secret,
        "pid": os.getpid(),
    })
    for candidate_dir in (
        Path.home() / ".reqtrace",
        Path(tempfile.gettempdir()) / "reqtrace_operator",
    ):
        try:
            candidate_dir.mkdir(parents=True, exist_ok=True)
            state_path = candidate_dir / f"operator_{port}.json"
            state_path.write_text(payload, encoding="utf-8")
            try:
                os.chmod(state_path, 0o600)
            except OSError:
                pass
            return state_path
        except OSError:
            continue
    raise OSError("Unable to write operator runtime state file.")


def find_operator_state_path(port: int) -> Optional[Path]:
    """Locates the active operator state file for a running UI port."""
    for candidate_dir in (
        Path.home() / ".reqtrace",
        Path(tempfile.gettempdir()) / "reqtrace_operator",
    ):
        state_path = candidate_dir / f"operator_{port}.json"
        if state_path.is_file():
            return state_path
    return None


def create_ui_app(
    workspace_root: Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    ticket_timeout: int = 60,
    ticket_store: Optional[TicketStore] = None,
    session_store: Optional[SessionStore] = None,
    operator_secret: Optional[str] = None,
) -> FastAPI:
    """
    Factory creating a fully configured, hardened FastAPI instance
    for the ReqTrace local workspace cockpit.
    """
    app = FastAPI(
        title="ReqTrace UI",
        description="Localhost Audit Matrix & Evidence Cockpit",
        version="0.1.0",
        docs_url=None,       # Disable Swagger UI in production local app for security
        redoc_url=None,
        openapi_url=None,
    )

    t_store = ticket_store or TicketStore(timeout_sec=ticket_timeout)
    s_store = session_store or SessionStore()
    cookie_name = f"reqtrace_session_{port}"

    # Build allowed hosts for Anti-DNS Rebinding
    allowed_hosts = {
        f"127.0.0.1:{port}",
        f"localhost:{port}",
        "127.0.0.1",
        "localhost",
        f"[::1]:{port}",
        "[::1]",
    }
    if host not in {"127.0.0.1", "localhost"}:
        allowed_hosts.add(f"{host}:{port}")
        allowed_hosts.add(host)
        allowed_hosts.add(f"0.0.0.0:{port}")
        allowed_hosts.add("0.0.0.0")

    # 1. Attach Localhost Security Middleware
    app.add_middleware(
        LocalhostSecurityMiddleware,
        port=port,
        session_store=s_store,
        cookie_name=cookie_name,
        allowed_hosts=allowed_hosts,
    )

    # 2. Attach API Router
    api_router = create_api_router(
        workspace_root,
        t_store,
        s_store,
        cookie_name,
        operator_secret=operator_secret,
    )
    app.include_router(api_router)

    # 3. Mount Static Assets & SPA Fallback
    dist_dir = Path(__file__).parent / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    index_file = dist_dir / "index.html"

    @app.get("/app.css", include_in_schema=False)
    async def serve_css():
        css_file = dist_dir / "app.css"
        if css_file.exists():
            return FileResponse(css_file, media_type="text/css")
        return Response("", media_type="text/css")

    @app.get("/app.js", include_in_schema=False)
    async def serve_js():
        js_file = dist_dir / "app.js"
        if js_file.exists():
            return FileResponse(js_file, media_type="application/javascript")
        return Response("", media_type="application/javascript")

    @app.get("/", include_in_schema=False)
    def serve_index(request: Request):
        session_cookie = request.cookies.get(cookie_name)
        if not session_cookie or not s_store.validate_session(session_cookie):
            return HTMLResponse(
                content=f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>ReqTrace - Authentication Gateway</title>
  <link rel="stylesheet" href="/app.css" />
</head>
<body class="auth-gateway-body">
  <div class="auth-gateway-card">
    <h1>🎯 ReqTrace Local Cockpit</h1>
    <p>Single-use launch ticket authentication is required to access this air-gapped verification workspace.</p>
    <hr class="auth-gateway-divider" />
    <form action="/login" method="GET">
      <input type="text" name="ticket" class="auth-gateway-input" placeholder="Paste Ticket or full Launch URL from logs" required />
      <button type="submit" class="auth-gateway-submit">Unlock Cockpit</button>
    </form>
    <div class="auth-gateway-steps">
      <div class="auth-gateway-steps-title">How to get your Launch Ticket:</div>
      <ul class="auth-gateway-list">
        <li><strong>Docker Desktop:</strong> Open <strong>Containers → reqtrace-cockpit → Logs</strong> and copy the <code>Ticket</code> or <code>Launch URL</code>.</li>
        <li><strong>Docker CLI Logs:</strong> Run <code>docker logs reqtrace-cockpit</code></li>
        <li><strong>Generate New Ticket Anytime:</strong> Run <code>docker exec reqtrace-cockpit reqtrace ticket</code> (or <code>reqtrace ticket</code> locally).</li>
        <li><strong>Auto-Open Script:</strong> Launch with <code>.\\docker-run.ps1 -Detach</code> or <code>./docker-run.sh -d</code></li>
      </ul>
    </div>
    <div class="auth-gateway-info">Initial launch tickets expire after {t_store.timeout_sec}s for security. Sessions persist for 24 hours via HttpOnly cookie.</div>
  </div>
</body>
</html>""",
                status_code=status.HTTP_200_OK,
            )

        if index_file.exists():
            return FileResponse(index_file)
        return HTMLResponse("<h1>ReqTrace UI: Assets Building</h1>")

    if (dist_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=dist_dir / "assets"), name="assets")

    # Store references for testing/inspection
    app.state.ticket_store = t_store
    app.state.session_store = s_store
    app.state.cookie_name = cookie_name

    return app


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Checks whether the requested loopback port is available for binding."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            s.bind((host, port))
            return True
    except OSError:
        return False


def run_server(
    workspace_root: Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
    ticket_timeout: int = 60,
) -> None:
    """
    Starts the ReqTrace UI on <host>:<port>, generating a launch ticket
    and opening the local user's browser.
    """
    if not is_port_available(port, host=host):
        print("\n" + "=" * 68)
        print(f"  ❌ Port {port} on {host} is already in use by another running instance or process.")
        print("  Suggested fix: Launch on another port using --port, e.g.:")
        print(f"    reqtrace ui --port {port + 1}")
        print("=" * 68 + "\n")
        sys.exit(1)

    ticket_store = TicketStore(timeout_sec=ticket_timeout)
    session_store = SessionStore()
    operator_secret = secrets.token_urlsafe(32)
    app = create_ui_app(
        workspace_root=workspace_root,
        host=host,
        port=port,
        ticket_timeout=ticket_timeout,
        ticket_store=ticket_store,
        session_store=session_store,
        operator_secret=operator_secret,
    )

    operator_state_path: Optional[Path] = None
    try:
        operator_state_path = _write_operator_state(port, operator_secret)
    except OSError:
        operator_state_path = None

    # Generate one-time launch ticket
    ticket = ticket_store.generate_ticket()
    client_host = "localhost" if host in {"0.0.0.0", "127.0.0.1"} else host
    launch_url = f"http://{client_host}:{port}/login?ticket={ticket}"

    # Install access log filter to redact ticket from uvicorn log lines
    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.addFilter(AccessLogTicketFilter())

    print("\n" + "=" * 68)
    print("  🎯 ReqTrace Local Cockpit")
    print("  Status: Zero-Egress Air-Gapped Local Web Application")
    print(f"  Workspace:    {workspace_root.resolve()}")
    print(f"  Listening on: http://{host}:{port}")
    print(f"  Launch URL:   {launch_url}")
    print(f"  Ticket:       {ticket}")
    print(f"  Note: Ticket valid for {ticket_timeout}s. Scoped cookie: reqtrace_session_{port}")
    print("  Hint: Mint another ticket anytime via: reqtrace ticket")
    print("=" * 68 + "\n")

    if open_browser:
        webbrowser.open(launch_url)

    # Run uvicorn bound to configured host
    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
        )
    finally:
        if operator_state_path and operator_state_path.exists():
            try:
                operator_state_path.unlink()
            except OSError:
                pass

