from __future__ import annotations

import json

import pytest

from arc.providers.mcp_bridge import (
    MCPError,
    SseMCPClient,
    StdioMCPClient,
    build_request,
    extract_text_content,
    parse_sse_block,
    split_command,
)


def test_build_request_shape() -> None:
    raw = build_request(7, "tools/call", {"name": "query", "arguments": {"a": 1}})
    msg = json.loads(raw)
    assert msg["jsonrpc"] == "2.0"
    assert msg["id"] == 7
    assert msg["method"] == "tools/call"
    assert msg["params"] == {"name": "query", "arguments": {"a": 1}}


def test_extract_text_content_joins_text_parts() -> None:
    result = {
        "content": [
            {"type": "text", "text": "part one"},
            {"type": "text", "text": "part two"},
            {"type": "other"},
        ],
        "isError": False,
    }
    assert extract_text_content(result) == "part one\npart two"
    assert extract_text_content("garbage") == ""
    assert extract_text_content({}) == ""


def test_extract_text_content_raises_on_tool_error() -> None:
    with pytest.raises(MCPError):
        extract_text_content({"isError": True, "content": [{"type": "text", "text": "boom"}]})


def test_parse_sse_block_variants() -> None:
    assert parse_sse_block(["event: endpoint", "data: /messages/?session_id=abc"]) == (
        "endpoint",
        "/messages/?session_id=abc",
    )
    assert parse_sse_block(["data: {\"jsonrpc\": \"2.0\"}"]) == ("", '{"jsonrpc": "2.0"}')
    # Comments/keepalives are ignored.
    assert parse_sse_block([": ping"]) is None
    assert parse_sse_block([]) is None


def test_split_command_preserves_quotes() -> None:
    argv = split_command('"/path with space/py" -m module.name --flag "a b"')
    assert argv == ["/path with space/py", "-m", "module.name", "--flag", "a b"]


def test_sse_client_unreachable_endpoint_fails_fast() -> None:
    client = SseMCPClient("http://127.0.0.1:9/sse", "token", connect_timeout=3.0)
    with pytest.raises(MCPError, match="cannot connect"):
        client.connect()


def test_stdio_client_bad_command_fails_fast() -> None:
    client = StdioMCPClient("/nonexistent/binary/for/arc/tests", startup_timeout=5.0)
    with pytest.raises(MCPError, match="failed to spawn"):
        client.start()


def test_stdio_client_requires_start_before_use() -> None:
    client = StdioMCPClient("/bin/sleep 60")
    with pytest.raises(MCPError, match="not running"):
        client.list_tools()


def test_connect_services_fails_hard_when_tokens_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from arc.providers import mcp_bridge

    monkeypatch.delenv("ARC_SCHOLARTRACE_TOKEN", raising=False)
    monkeypatch.delenv("ARC_SCHOLARANALYSIS_TOKEN", raising=False)
    with pytest.raises(MCPError, match="requires all three MCP services"):
        mcp_bridge.connect_services()
