"""Minimal MCP client bridge for the three research services used by discover mode.

- StdioMCPClient: spawns a local MCP server (webresearch-mcp) and speaks
  newline-delimited JSON-RPC 2.0 over stdin/stdout.
- SseMCPClient: connects to a running FastMCP SSE server (scholartrace,
  scholaranalysis): GET the event stream, POST requests to the session
  endpoint, match responses by id.

Both expose the same two methods: ``list_tools()`` and ``call_tool()``.

All configuration comes from environment variables (see .env.example):
ARC_MCP_WEBRESEARCH_CMD, ARC_SCHOLARTRACE_URL/TOKEN,
ARC_SCHOLARANALYSIS_URL/TOKEN, ARC_MCP_CALL_TIMEOUT_SECONDS.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

_JSONRPC_VERSION = "2.0"
_PROTOCOL_VERSION = "2024-11-05"
_CLIENT_INFO = {"name": "arc-discover", "version": "0.1.0"}

DEFAULT_WEBRESEARCH_CMD = (
    "/home/g203/zhanghaonan/webresearch-mcp/.venv/bin/python -m webresearch_mcp.server"
)
# Loopback on purpose: this host cannot hairpin to its own external IP
# (10.134.132.166), while the services listen on 0.0.0.0.
DEFAULT_SCHOLARTRACE_URL = "http://127.0.0.1:8001/sse"
DEFAULT_SCHOLARANALYSIS_URL = "http://127.0.0.1:8005/sse"


class MCPError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Shared JSON-RPC helpers
# ---------------------------------------------------------------------------

def build_request(req_id: int, method: str, params: dict[str, Any] | None = None) -> str:
    payload: dict[str, Any] = {
        "jsonrpc": _JSONRPC_VERSION,
        "id": req_id,
        "method": method,
    }
    if params is not None:
        payload["params"] = params
    return json.dumps(payload, ensure_ascii=False)


def extract_text_content(result: Any) -> str:
    """Concatenate the text parts of a tools/call result."""
    if not isinstance(result, dict):
        return ""
    if result.get("isError"):
        parts = [
            c.get("text", "") for c in result.get("content", []) if isinstance(c, dict)
        ]
        raise MCPError("tool call returned an error: " + " ".join(p for p in parts if p))
    parts: list[str] = []
    for item in result.get("content", []):
        if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
            parts.append(str(item["text"]))
    return "\n".join(parts)


def parse_sse_block(lines: list[str]) -> tuple[str, str] | None:
    """Parse one SSE block (lines between blank lines) into (event, data).

    Returns None for keepalive/comment-only blocks.
    """
    event = ""
    data: list[str] = []
    for line in lines:
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data.append(line[len("data:"):].strip())
    if not event and not data:
        return None
    return event, "\n".join(data)


def split_command(command: str) -> list[str]:
    return shlex.split(command)


# ---------------------------------------------------------------------------
# stdio transport (webresearch-mcp)
# ---------------------------------------------------------------------------

class StdioMCPClient:
    def __init__(self, command: str, startup_timeout: float = 30.0) -> None:
        self._argv = split_command(command)
        self._startup_timeout = startup_timeout
        self._proc: subprocess.Popen[str] | None = None
        self._next_id = 1
        self._lock = threading.Lock()

    def start(self) -> None:
        try:
            self._proc = subprocess.Popen(
                self._argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise MCPError(f"failed to spawn MCP server ({' '.join(self._argv)}): {exc}") from exc
        self._initialize(timeout=self._startup_timeout)

    def _ensure_started(self) -> subprocess.Popen[str]:
        if self._proc is None or self._proc.poll() is not None:
            raise MCPError("stdio MCP server is not running")
        return self._proc

    def _transact(self, method: str, params: dict[str, Any] | None, timeout: float) -> Any:
        proc = self._ensure_started()
        with self._lock:
            req_id = self._next_id
            self._next_id += 1
            request = build_request(req_id, method, params)
            try:
                assert proc.stdin is not None and proc.stdout is not None
                proc.stdin.write(request + "\n")
                proc.stdin.flush()
                deadline = time.monotonic() + timeout
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise MCPError(f"timed out waiting for response to {method}")
                    # Line-buffered read cannot be interrupted portably; rely on
                    # the process being alive and the deadline check above.
                    line = proc.stdout.readline()
                    if not line:
                        raise MCPError("MCP server closed its stdout")
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        message = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if message.get("id") != req_id:
                        continue
                    if "error" in message:
                        raise MCPError(f"{method} failed: {message['error']}")
                    return message.get("result")
            except BrokenPipeError as exc:
                raise MCPError(f"MCP server pipe broke during {method}") from exc

    def _initialize(self, timeout: float) -> None:
        params = {
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": _CLIENT_INFO,
        }
        self._transact("initialize", params, timeout)
        proc = self._ensure_started()
        assert proc.stdin is not None
        proc.stdin.write(json.dumps({
            "jsonrpc": _JSONRPC_VERSION,
            "method": "notifications/initialized",
        }) + "\n")
        proc.stdin.flush()

    def list_tools(self, timeout: float = 30.0) -> list[dict[str, Any]]:
        result = self._transact("tools/list", {}, timeout)
        if isinstance(result, dict):
            return [t for t in result.get("tools", []) if isinstance(t, dict)]
        return []

    def call_tool(self, name: str, arguments: dict[str, Any], timeout: float = 600.0) -> str:
        result = self._transact(
            "tools/call", {"name": name, "arguments": arguments}, timeout)
        return extract_text_content(result)

    def close(self) -> None:
        if self._proc is not None:
            try:
                if self._proc.stdin is not None:
                    self._proc.stdin.close()
            except Exception:
                pass
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None


# ---------------------------------------------------------------------------
# SSE transport (scholartrace / scholaranalysis)
# ---------------------------------------------------------------------------

class SseMCPClient:
    def __init__(self, sse_url: str, token: str, connect_timeout: float = 15.0) -> None:
        self._sse_url = sse_url.rstrip("/")
        self._token = token.strip()
        self._connect_timeout = connect_timeout
        self._messages_url: str | None = None
        self._next_id = 1
        self._responses: dict[int, dict[str, Any]] = {}
        self._cond = threading.Condition()
        self._reader_thread: threading.Thread | None = None
        self._response: requests.Response | None = None
        self._closed = False

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "text/event-stream"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def connect(self) -> None:
        try:
            session = requests.Session()
            resp = session.get(
                self._sse_url,
                headers=self._headers(),
                timeout=(self._connect_timeout, None),
                stream=True,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise MCPError(f"cannot connect to MCP SSE endpoint {self._sse_url}: {exc}") from exc

        self._response = resp
        # The endpoint announcement and all later JSON-RPC responses arrive on
        # the same event stream; a background thread owns the iteration.
        self._reader_thread = threading.Thread(target=self._read_loop, args=(resp,), daemon=True)
        self._reader_thread.start()

        with self._cond:
            if not self._messages_url:
                self._cond.wait(self._connect_timeout)
            if not self._messages_url:
                self.close()
                raise MCPError(
                    f"MCP SSE endpoint {self._sse_url} did not announce a session endpoint "
                    f"within {self._connect_timeout:.0f}s")

        self._request("initialize", {
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": _CLIENT_INFO,
        }, timeout=self._connect_timeout)
        self._notify("notifications/initialized")

    def _read_loop(self, response: requests.Response) -> None:
        block: list[str] = []
        try:
            for raw_line in response.iter_lines(decode_unicode=True):
                if self._closed:
                    return
                if raw_line is None or raw_line == "":
                    if block:
                        parsed = parse_sse_block(block)
                        block = []
                        if parsed is not None:
                            self._handle_event(parsed[0], parsed[1])
                    continue
                block.append(raw_line)
        except Exception:
            if not self._closed:
                # Stream broke; wake anything waiting so it can fail loudly.
                with self._cond:
                    self._cond.notify_all()

    def _handle_event(self, event: str, data: str) -> None:
        with self._cond:
            if event == "endpoint" and data:
                if not self._messages_url:
                    parsed_url = urlparse(self._sse_url)
                    root = f"{parsed_url.scheme}://{parsed_url.netloc}"
                    self._messages_url = (
                        data if data.startswith("http") else urljoin(root + "/", data)
                    )
                self._cond.notify_all()
                return
            if event not in ("message", "response", ""):
                return
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                return
            if not isinstance(message, dict) or "id" not in message:
                return
            self._responses[int(message["id"])] = message
            self._cond.notify_all()

    def _request(self, method: str, params: dict[str, Any] | None, timeout: float) -> Any:
        if not self._messages_url:
            raise MCPError("SSE client is not connected")
        with self._cond:
            req_id = self._next_id
            self._next_id += 1
        body = json.loads(build_request(req_id, method, params))
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            resp = requests.post(self._messages_url, json=body, headers=headers, timeout=timeout)
        except requests.RequestException as exc:
            raise MCPError(f"SSE MCP request {method} failed to post: {exc}") from exc
        if resp.status_code not in (200, 202):
            raise MCPError(f"SSE MCP request {method} rejected: HTTP {resp.status_code} {resp.text[:200]}")

        deadline = time.monotonic() + timeout
        with self._cond:
            while req_id not in self._responses:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise MCPError(f"timed out waiting for SSE response to {method}")
                self._cond.wait(remaining)
            message = self._responses.pop(req_id)
        if "error" in message:
            raise MCPError(f"{method} failed: {message['error']}")
        return message.get("result")

    def _notify(self, method: str) -> None:
        if not self._messages_url:
            raise MCPError("SSE client is not connected")
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            requests.post(
                self._messages_url,
                json={"jsonrpc": _JSONRPC_VERSION, "method": method},
                headers=headers,
                timeout=15.0,
            )
        except requests.RequestException as exc:
            raise MCPError(f"SSE MCP notification {method} failed: {exc}") from exc

    def list_tools(self, timeout: float = 30.0) -> list[dict[str, Any]]:
        result = self._request("tools/list", {}, timeout)
        if isinstance(result, dict):
            return [t for t in result.get("tools", []) if isinstance(t, dict)]
        return []

    def call_tool(self, name: str, arguments: dict[str, Any], timeout: float = 600.0) -> str:
        result = self._request("tools/call", {"name": name, "arguments": arguments}, timeout)
        return extract_text_content(result)

    def close(self) -> None:
        self._closed = True
        if self._response is not None:
            try:
                self._response.close()
            except Exception:
                pass
            self._response = None


# ---------------------------------------------------------------------------
# Service registry + health check
# ---------------------------------------------------------------------------

@dataclass
class MCPServices:
    webresearch: StdioMCPClient
    scholartrace: SseMCPClient
    scholaranalysis: SseMCPClient

    def close_all(self) -> None:
        for client in (self.webresearch, self.scholartrace, self.scholaranalysis):
            try:
                client.close()
            except Exception:
                pass


_SERVICE_START_HINTS = {
    "scholartrace": "bash /home/g203/zhanghaonan/ScholarTrace/run_scholartrace_mcp_sse.sh  (SSE on :8001)",
    "scholaranalysis": "bash /home/g203/zhanghaonan/ScholarAnalysis/run.sh  (SSE on :8005)",
    "webresearch": "/home/g203/zhanghaonan/webresearch-mcp/.venv/bin/python -m webresearch_mcp.server  (stdio)",
}


def _call_timeout() -> float:
    raw = os.getenv("ARC_MCP_CALL_TIMEOUT_SECONDS", "600").strip()
    try:
        value = float(raw)
    except ValueError:
        return 600.0
    return value if value > 0 else 600.0


def _missing_env(name: str, url: str) -> str:
    return (
        f"{name} is not configured: set {url} and the matching token "
        "in .env (see .env.example)"
    )


def connect_services() -> MCPServices:
    """Connect to all three MCP services, failing fast with actionable errors."""
    failures: list[str] = []

    scholartrace_url = os.getenv("ARC_SCHOLARTRACE_URL", DEFAULT_SCHOLARTRACE_URL)
    scholartrace_token = os.getenv("ARC_SCHOLARTRACE_TOKEN", "")
    scholartrace = SseMCPClient(scholartrace_url, scholartrace_token)

    scholaranalysis_url = os.getenv("ARC_SCHOLARANALYSIS_URL", DEFAULT_SCHOLARANALYSIS_URL)
    scholaranalysis_token = os.getenv("ARC_SCHOLARANALYSIS_TOKEN", "")
    scholaranalysis = SseMCPClient(scholaranalysis_url, scholaranalysis_token)

    webresearch_cmd = os.getenv("ARC_MCP_WEBRESEARCH_CMD", DEFAULT_WEBRESEARCH_CMD)
    webresearch = StdioMCPClient(webresearch_cmd)

    if not scholartrace_token:
        failures.append(_missing_env("scholartrace", "ARC_SCHOLARTRACE_TOKEN"))
    if not scholaranalysis_token:
        failures.append(_missing_env("scholaranalysis", "ARC_SCHOLARANALYSIS_TOKEN"))

    if not failures:
        try:
            scholartrace.connect()
        except MCPError as exc:
            failures.append(f"scholartrace unreachable: {exc}\n  start: {_SERVICE_START_HINTS['scholartrace']}")
        try:
            scholaranalysis.connect()
        except MCPError as exc:
            failures.append(f"scholaranalysis unreachable: {exc}\n  start: {_SERVICE_START_HINTS['scholaranalysis']}")
        try:
            webresearch.start()
        except MCPError as exc:
            failures.append(f"webresearch failed to start: {exc}\n  start: {_SERVICE_START_HINTS['webresearch']}")

    if failures:
        scholartrace.close()
        scholaranalysis.close()
        webresearch.close()
        raise MCPError(
            "discover mode requires all three MCP services; fix the following and retry:\n- "
            + "\n- ".join(failures)
        )

    return MCPServices(webresearch=webresearch, scholartrace=scholartrace, scholaranalysis=scholaranalysis)
