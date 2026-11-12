# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Security Middleware and Localhost Protection for ReqTrace UI.
Enforces loopback isolation, single-use launch tickets, port-scoped HttpOnly cookies,
anti-DNS rebinding, CSRF guards, hardened CSP, and path traversal protection.
"""

import logging
import secrets
import time
from pathlib import Path
from typing import Dict, Optional, Set
from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


class TicketStore:
    """
    Manages single-use launch tickets with configurable expiration.
    Prevents ticket reuse and Shoulder-Surfing attacks.
    """

    def __init__(self, timeout_sec: int = 60) -> None:
        self.timeout_sec = timeout_sec
        # Maps ticket string to creation timestamp (float)
        self._tickets: Dict[str, float] = {}

    def generate_ticket(self) -> str:
        ticket = secrets.token_urlsafe(32)
        self._tickets[ticket] = time.time()
        return ticket

    def consume_ticket(self, ticket: str) -> bool:
        """
        Validates and immediately consumes a launch ticket (single-use).
        Returns True if valid and not expired, False otherwise.
        """
        self._purge_expired()
        created_at = self._tickets.pop(ticket, None)
        if created_at is None:
            return False
        return (time.time() - created_at) <= self.timeout_sec

    def _purge_expired(self) -> None:
        now = time.time()
        expired = [t for t, ts in self._tickets.items() if (now - ts) > self.timeout_sec]
        for t in expired:
            self._tickets.pop(t, None)


def normalize_ticket_input(raw_ticket: Optional[str]) -> Optional[str]:
    """
    Normalizes user-submitted launch tickets, handling whitespace and allowing
    users to paste either the raw ticket token or the full Launch URL.
    """
    if not raw_ticket:
        return None
    cleaned = raw_ticket.strip()
    if not cleaned:
        return None
    if "ticket=" in cleaned:
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(cleaned)
        qs = parse_qs(parsed.query)
        if "ticket" in qs and qs["ticket"]:
            return qs["ticket"][0].strip()
        # Fallback if fragment/partial URL pasted without scheme
        after_eq = cleaned.split("ticket=", 1)[1].split("&", 1)[0]
        return after_eq.strip() or None
    return cleaned


class SessionStore:
    """
    Tracks active loopback browser sessions.
    Sessions expire after inactivity (default: 24 hours).
    """

    def __init__(self, lifetime_sec: int = 86400) -> None:
        self.lifetime_sec = lifetime_sec
        self._sessions: Dict[str, float] = {}

    def create_session(self) -> str:
        session_id = secrets.token_hex(32)
        self._sessions[session_id] = time.time()
        return session_id

    def validate_session(self, session_id: str) -> bool:
        created_at = self._sessions.get(session_id)
        if not created_at:
            return False
        if (time.time() - created_at) > self.lifetime_sec:
            self._sessions.pop(session_id, None)
            return False
        return True


class AccessLogTicketFilter(logging.Filter):
    """
    Filters uvicorn access logs to redact launch tickets from appearing
    in server logs, terminal output, or process supervisors.
    Preserves uvicorn's expected 5-tuple record.args formatting.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        import re
        if isinstance(record.args, tuple) and len(record.args) >= 3:
            full_path = str(record.args[2])
            if "ticket=" in full_path:
                redacted_path = re.sub(r"ticket=[A-Za-z0-9_\-]+", "ticket=[REDACTED]", full_path)
                args_list = list(record.args)
                args_list[2] = redacted_path
                record.args = tuple(args_list)
        elif "ticket=" in str(record.msg):
            record.msg = re.sub(r"ticket=[A-Za-z0-9_\-]+", "ticket=[REDACTED]", str(record.msg))
        return True


class LocalhostSecurityMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive Localhost Defense-in-Depth Middleware:
    1. Validates Host header against loopback port (anti-DNS rebinding).
    2. Validates Origin/Referer on mutating requests (anti-CSRF).
    3. Validates port-specific session cookie for protected API routes.
    4. Injects hardened Content-Security-Policy (CSP) headers without 'unsafe-inline'.
    """

    def __init__(
        self,
        app,
        port: int,
        session_store: SessionStore,
        cookie_name: str,
        allowed_hosts: Optional[Set[str]] = None,
    ) -> None:
        super().__init__(app)
        self.port = port
        self.session_store = session_store
        self.cookie_name = cookie_name
        self.allowed_hosts: Set[str] = set(allowed_hosts) if allowed_hosts else {
            f"127.0.0.1:{port}",
            f"localhost:{port}",
            "127.0.0.1",
            "localhost",
            f"[::1]:{port}",
            "[::1]",
        }

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        host_header = request.headers.get("host", "").lower().strip()

        # 1. Host Validation (Anti-DNS Rebinding)
        if host_header and host_header not in self.allowed_hosts:
            return Response(
                content="403 Forbidden: Invalid Host Header (Anti-DNS Rebinding Guard)",
                status_code=status.HTTP_403_FORBIDDEN,
                media_type="text/plain",
            )

        # 2. Mutating Request Origin Guard (Anti-CSRF)
        if request.method in {"POST", "PUT", "DELETE", "PATCH"}:
            origin = request.headers.get("origin")
            referer = request.headers.get("referer")
            if not origin and not referer:
                return Response(
                    content="403 Forbidden: Missing Origin and Referer on Mutating Request",
                    status_code=status.HTTP_403_FORBIDDEN,
                    media_type="text/plain",
                )
            # Verify origin matches loopback if provided
            if origin:
                origin_clean = origin.replace("http://", "").replace("https://", "").lower().strip("/")
                if origin_clean not in self.allowed_hosts:
                    return Response(
                        content="403 Forbidden: Cross-Origin Mutating Request Blocked",
                        status_code=status.HTTP_403_FORBIDDEN,
                        media_type="text/plain",
                    )

        # 3. Session Cookie Authentication on Protected Endpoints
        path = request.url.path
        is_public = (
            path == "/login"
            or path == "/app.css"
            or path == "/app.js"
            or path.startswith("/static")
            or path == "/favicon.ico"
            or path == "/print"
        )

        if not is_public and path.startswith("/api/v1"):
            session_cookie = request.cookies.get(self.cookie_name)
            if not session_cookie or not self.session_store.validate_session(session_cookie):
                return Response(
                    content='{"detail": "401 Unauthorized: Valid loopback session required. Launch via `reqtrace ui`."}',
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    media_type="application/json",
                )

        # 4. Invoke route handler
        response = await call_next(request)

        # 5. Inject Hardened Security Headers
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
            "form-action 'self'; frame-ancestors 'none';"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response


def validate_workspace_path(file_path: Path | str, workspace_root: Path) -> Path:
    """
    Guards against directory traversal attacks by resolving symlinks and asserting
    that target path resides strictly within the active workspace root.
    """
    resolved_root = workspace_root.resolve()
    resolved_path = (resolved_root / file_path).resolve()
    if not resolved_path.is_relative_to(resolved_root):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security violation: path traversal outside workspace root is blocked: {file_path}",
        )
    return resolved_path

