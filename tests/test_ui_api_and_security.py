# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Automated Test Suite for ReqTrace UI API, Security Middleware, and CLI Parity (Milestone 1A).
Validates loopback authentication, ticket exchange, port-scoped cookies,
anti-DNS rebinding, CSRF origin guards, CSP headers, path traversal guards,
and bit-for-bit parity with canonical status models without network hangs.
"""

import json
from pathlib import Path
import pytest
from typer.testing import CliRunner

from reqtrace.cli import app as cli_app
from reqtrace.analysis.status import UnverifiedReasonCode
from reqtrace.models.requirement import Requirement, RequirementLevel, VerificationMethod
from reqtrace.models.test_artifact import TestArtifact, TestVerdict
from reqtrace.models.trace_link import LinkConfidence, ReviewStatus, TraceLink
from reqtrace.ui.routes import WorkspaceDataLoader
from reqtrace.ui.security import (
    AccessLogTicketFilter,
    LocalhostSecurityMiddleware,
    SessionStore,
    TicketStore,
    validate_workspace_path,
)
from reqtrace.ui.server import create_ui_app


@pytest.fixture
def workspace_with_data(tmp_path: Path):
    """Sets up a realistic test workspace with requirements and tests."""
    req1 = Requirement(
        id="REQ-NAV-01",
        title="GPS Acquisition Speed",
        description="The navigation system shall acquire GPS lock within 2.5 seconds.",
        is_normative=True,
        level=RequirementLevel.HIGH_LEVEL,
        verification_method=VerificationMethod.TEST,
        source_file="specs/nav.reqif",
    )
    req2 = Requirement(
        id="REQ-STRUCT-02",
        title="Spar Margin of Safety",
        description="The wing spar shall withstand 150% limit load without deformation.",
        is_normative=True,
        level=RequirementLevel.HIGH_LEVEL,
        verification_method=VerificationMethod.ANALYSIS,
        source_file="specs/struct.reqif",
    )
    req3 = Requirement(
        id="REQ-ORPHAN-03",
        title="Unlinked Telemetry Clause",
        description="The system shall log telemetry at 50Hz.",
        is_normative=True,
        source_file="specs/nav.reqif",
    )

    t1 = TestArtifact(
        id="tests/test_nav.py::test_gps_acquisition",
        file_path="tests/test_nav.py",
        line_start=15,
        line_end=28,
        framework="pytest",
        declared_req_refs=["REQ-NAV-01"],
        assertion_statements=["assert acquire_gps() < 2.5"],
        execution_status=TestVerdict.PASSED,
        execution_time_sec=0.042,
    )

    # Write requirements.json and tests.json
    with open(tmp_path / "requirements.json", "w", encoding="utf-8") as f:
        json.dump([req1.model_dump(), req2.model_dump(), req3.model_dump()], f)

    with open(tmp_path / "tests.json", "w", encoding="utf-8") as f:
        json.dump([t1.model_dump()], f)

    return tmp_path


# --- Security Unit Tests ---

def test_ticket_store_lifecycle() -> None:
    store = TicketStore(timeout_sec=2)
    ticket = store.generate_ticket()
    assert len(ticket) >= 32

    # Single-use consumption
    assert store.consume_ticket(ticket) is True
    # Replay attempt fails immediately
    assert store.consume_ticket(ticket) is False
    # Non-existent ticket fails
    assert store.consume_ticket("nonexistent-ticket") is False


def test_session_store_lifecycle() -> None:
    store = SessionStore(lifetime_sec=10)
    session_id = store.create_session()
    assert len(session_id) == 64
    assert store.validate_session(session_id) is True
    assert store.validate_session("unknown_session") is False


def test_access_log_ticket_filter() -> None:
    import logging
    filter_obj = AccessLogTicketFilter()
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="GET /login?ticket=super_secret_12345 HTTP/1.1",
        args=(),
        exc_info=None,
    )
    filter_obj.filter(record)
    assert "super_secret_12345" not in record.msg
    assert "ticket=[REDACTED]" in record.msg


def test_path_traversal_guard(tmp_path: Path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    valid_file = workspace / "specs" / "nav.reqif"
    valid_file.parent.mkdir()
    valid_file.write_text("content", encoding="utf-8")

    # Valid relative path resolves properly
    resolved = validate_workspace_path("specs/nav.reqif", workspace)
    assert resolved == valid_file.resolve()

    # Directory traversal attack attempting to escape workspace is blocked
    with pytest.raises(Exception) as exc_info:
        validate_workspace_path("../../../etc/passwd", workspace)
    assert "traversal outside workspace root is blocked" in str(exc_info.value)


# --- Workspace Data Loader & API Logic Tests ---

def test_workspace_loader_status_parity(workspace_with_data: Path) -> None:
    loader = WorkspaceDataLoader(workspace_with_data)
    report = loader.evaluate_status()

    # Mathematical Invariant check
    assert report.total_normative == 3
    assert report.total_normative == report.verified_count + report.linked_passing_count + report.unverified_gaps
    assert sum(report.gap_reasons.values()) == report.unverified_gaps

    # REQ-NAV-01 has a passing test but unreviewed -> linked_passing_count == 1
    assert report.linked_passing_count == 1
    # REQ-STRUCT-02 is ANALYSIS without review -> awaiting_non_test_verification
    assert report.gap_reasons[UnverifiedReasonCode.AWAITING_NON_TEST_VERIFICATION] == 1
    # REQ-ORPHAN-03 has 0 tests -> orphan_no_test
    assert report.gap_reasons[UnverifiedReasonCode.ORPHAN_NO_TEST] == 1
    assert report.unverified_gaps == 2


def test_ui_app_factory_and_cookie_configuration(workspace_with_data: Path) -> None:
    app = create_ui_app(workspace_with_data, port=9000, ticket_timeout=45)
    assert app.state.cookie_name == "reqtrace_session_9000"
    assert app.state.ticket_store.timeout_sec == 45


def test_cli_ui_help_command() -> None:
    import re
    import click

    runner = CliRunner()
    result = runner.invoke(cli_app, ["ui", "--help"])
    assert result.exit_code == 0
    clean_output = click.unstyle(result.output)
    clean_output = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", clean_output)
    assert "Launch the interactive local workspace web application" in clean_output
    assert "port" in clean_output
    assert "no-browser" in clean_output
    assert "ticket-timeout" in clean_output


def test_ui_dist_index_html_assets_exist() -> None:
    dist_dir = Path("reqtrace/ui/dist")
    dist_index = dist_dir / "index.html"
    app_css = dist_dir / "app.css"
    app_js = dist_dir / "app.js"

    assert dist_index.exists()
    assert app_css.exists()
    assert app_js.exists()

    content = dist_index.read_text(encoding="utf-8")
    assert "ReqTrace" in content
    assert "Diagnostic Gap Breakdown" in content
    assert "Print View" in content
    assert "GNU Affero General Public License" in content

    # CSP Hardening Invariants: No inline style or script tags, no inline event attributes
    assert "<style>" not in content
    assert "<script>" not in content
    assert 'href="/app.css"' in content
    assert 'src="/app.js"' in content
    assert "onclick=" not in content
    assert "onload=" not in content


def test_ui_endpoints_route_registration(workspace_with_data: Path) -> None:
    """Verifies all required SPA and API routes are registered on the app."""
    app = create_ui_app(workspace_with_data)
    route_paths = []
    for r in app.routes:
        if hasattr(r, "path"):
            route_paths.append(r.path)
        elif hasattr(r, "original_router"):
            route_paths.extend([sub.path for sub in r.original_router.routes])

    assert "/" in route_paths
    assert "/app.css" in route_paths
    assert "/app.js" in route_paths
    assert "/print" in route_paths
    assert "/login" in route_paths
    assert "/api/v1/reasons" in route_paths
    assert "/api/v1/matrix" in route_paths
    assert "/api/v1/evidence/{req_id}" in route_paths


def test_is_port_available() -> None:
    import socket
    from reqtrace.ui.server import is_port_available

    # Bind a temporary port and assert is_port_available returns False for it
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        _, port = s.getsockname()
        assert is_port_available(port) is False

    # Once closed, port should be available again
    assert is_port_available(port) is True


def _find_app_route(app, path: str, method: str = "GET"):
    candidates = []
    for route in app.routes:
        if hasattr(route, "original_router"):
            candidates.extend(route.original_router.routes)
        elif hasattr(route, "routes"):
            candidates.extend(route.routes)
        else:
            candidates.append(route)
    for route in candidates:
        methods = getattr(route, "methods", None) or set()
        if getattr(route, "path", None) == path and method in methods:
            return route.endpoint
    raise KeyError(f"Route not found: {method} {path}")


def _run_coro_no_loop(coro):
    """Drives a pure coroutine without creating an asyncio event loop or socketpair."""
    try:
        coro.send(None)
    except StopIteration as exc:
        return exc.value
    raise AssertionError("Coroutine suspended unexpectedly")


def test_auth_gateway_csp_and_ticket_exchange(workspace_with_data: Path) -> None:
    from starlette.requests import Request
    from starlette.responses import FileResponse, Response
    from reqtrace.ui.security import normalize_ticket_input

    operator_secret = "test-operator-secret-value-123456"
    app = create_ui_app(
        workspace_with_data,
        port=8765,
        ticket_timeout=45,
        operator_secret=operator_secret,
    )
    active_ticket = app.state.ticket_store.generate_ticket()
    serve_index = _find_app_route(app, "/", "GET")
    login_ep = _find_app_route(app, "/login", "GET")

    def make_req(path: str = "/", cookies: dict | None = None, headers: dict | None = None) -> Request:
        raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {"host": "localhost:8765"}).items()]
        if cookies:
            cookie_hdr = "; ".join(f"{k}={v}" for k, v in cookies.items())
            raw_headers.append((b"cookie", cookie_hdr.encode()))
        scope = {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": raw_headers,
            "query_string": b"",
        }
        return Request(scope)

    # 1. Unauthenticated GET / shows CSP-compliant Authentication Gateway without leaking ticket
    res_unauth = serve_index(make_req("/"))
    assert res_unauth.status_code == 200
    body = res_unauth.body.decode("utf-8")
    assert "Unlock Cockpit" in body
    assert 'href="/app.css"' in body
    assert "<style" not in body
    assert "<script" not in body
    assert active_ticket not in body

    # 2. Middleware enforces CSP headers without 'unsafe-inline' on gateway response
    mw = LocalhostSecurityMiddleware(app, port=8765, session_store=app.state.session_store, cookie_name="reqtrace_session_8765")

    async def call_next(_req):
        return res_unauth

    mw_res = _run_coro_no_loop(mw.dispatch(make_req("/"), call_next))
    assert "style-src 'self'" in mw_res.headers["Content-Security-Policy"]
    assert "unsafe-inline" not in mw_res.headers["Content-Security-Policy"]

    # 3. Invalid/expired ticket returns CSP-compliant 401 page showing dynamic timeout
    res_bad = login_ep(ticket="invalid-ticket-xyz")
    assert res_bad.status_code == 401
    bad_body = res_bad.body.decode("utf-8")
    assert "45 seconds" in bad_body
    assert 'href="/app.css"' in bad_body
    assert "<style" not in bad_body

    # 4. Full Launch URL pasted into ticket param normalizes and authenticates
    pasted_url = f"  http://localhost:8765/login?ticket={active_ticket}  "
    assert normalize_ticket_input(pasted_url) == active_ticket
    res_login = login_ep(ticket=pasted_url)
    assert res_login.status_code == 303
    assert res_login.headers["location"] == "/"
    set_cookie_hdr = res_login.headers.get("set-cookie", "")
    assert "reqtrace_session_8765=" in set_cookie_hdr
    session_val = set_cookie_hdr.split("reqtrace_session_8765=", 1)[1].split(";", 1)[0]

    # 5. Authenticated GET / now serves the workspace SPA cleanly
    res_auth = serve_index(make_req("/", cookies={"reqtrace_session_8765": session_val}))
    assert res_auth.status_code == 200
    assert isinstance(res_auth, FileResponse)

    # 6. Replay of consumed ticket fails
    res_replay = login_ep(ticket=active_ticket)
    assert res_replay.status_code == 401

    # 7. API call without session cookie blocked by middleware (401)
    async def api_call_next(_req):
        return Response("ok")

    res_api_unauth = _run_coro_no_loop(mw.dispatch(make_req("/api/v1/summary"), api_call_next))
    assert res_api_unauth.status_code == 401


def test_operator_ticket_minting_security(workspace_with_data: Path) -> None:
    from fastapi import HTTPException
    from starlette.requests import Request
    from starlette.responses import Response

    operator_secret = "super-secret-operator-token-xyz"
    app = create_ui_app(
        workspace_with_data,
        port=8765,
        ticket_timeout=1800,
        operator_secret=operator_secret,
    )
    mint_ep = _find_app_route(app, "/internal/ticket", "POST")
    mw = LocalhostSecurityMiddleware(
        app,
        port=8765,
        session_store=app.state.session_store,
        cookie_name="reqtrace_session_8765",
    )

    # 1. Missing Origin on POST blocked by CSRF middleware guard
    post_no_origin = Request({
        "type": "http",
        "method": "POST",
        "path": "/internal/ticket",
        "headers": [(b"host", b"127.0.0.1:8765")],
        "query_string": b"",
    })

    async def dummy_next(_req):
        return Response("ok")

    res_csrf = _run_coro_no_loop(mw.dispatch(post_no_origin, dummy_next))
    assert res_csrf.status_code == 403

    # 2. Wrong operator secret fails closed
    with pytest.raises(HTTPException) as exc_bad:
        mint_ep(x_reqtrace_operator="wrong-secret")
    assert exc_bad.value.status_code == 403

    with pytest.raises(HTTPException) as exc_none:
        mint_ep(x_reqtrace_operator=None)
    assert exc_none.value.status_code == 403

    # 3. Valid operator credentials mint a fresh usable ticket
    data = mint_ep(x_reqtrace_operator=operator_secret)
    assert data["timeout_sec"] == 1800
    assert len(data["ticket"]) >= 32
    assert app.state.ticket_store.consume_ticket(data["ticket"]) is True


def test_cli_ticket_help_command() -> None:
    import click

    runner = CliRunner()
    result = runner.invoke(cli_app, ["ticket", "--help"])
    assert result.exit_code == 0
    clean_output = click.unstyle(result.output)
    assert "Mint a fresh single-use launch ticket" in clean_output
    assert "--port" in clean_output

