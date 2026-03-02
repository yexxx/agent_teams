from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from textwrap import dedent

from agent_teams.acp.stdio_client import StdioAcpSessionClient
from agent_teams.acp.session_client import SessionInitSpec, TurnInput
from agent_teams.core.acp_config import AcpProviderConfig, AcpTimeoutsConfig


def test_acp_auto_protocol_falls_back_to_legacy(tmp_path: Path) -> None:
    script = tmp_path / "fake_legacy_acp.py"
    script.write_text(
        dedent(
            """
            import json
            import sys

            for line in sys.stdin:
                msg = json.loads(line)
                rid = msg.get("id")
                method = msg.get("method")
                params = msg.get("params", {})
                if method == "session.init":
                    out = {"id": rid, "result": {"session_id": "fake-session"}}
                elif method == "session.run_turn":
                    text = params.get("input", "")
                    out = {"id": rid, "result": {"text": f"LEGACY:{text}"}}
                elif method == "session.close":
                    out = {"id": rid, "result": {"closed": True}}
                    print(json.dumps(out), flush=True)
                    break
                else:
                    out = {"id": rid, "error": {"message": "unknown method"}}
                print(json.dumps(out), flush=True)
            """
        ),
        encoding="utf-8",
    )

    async def _run() -> None:
        client = StdioAcpSessionClient(
            provider=AcpProviderConfig(
                transport="stdio",
                command=sys.executable,
                args=("-u", str(script)),
                env={},
            ),
            timeouts=AcpTimeoutsConfig(session_init_ms=2_000, turn_ms=2_000),
        )
        handle = await client.open(
            SessionInitSpec(
                run_id="r1",
                trace_id="r1",
                task_id="t1",
                session_id="sess1",
                instance_id="inst1",
                role_id="time",
                system_prompt="You are time role.",
            )
        )
        assert handle.metadata.get("protocol") == "legacy_session_v1"
        result = await client.run_turn(handle, TurnInput(user_prompt="what time is it"))
        assert result.text == "LEGACY:what time is it"
        await client.close(handle)

    asyncio.run(_run())


def test_acp_auto_protocol_uses_opencode_when_available(tmp_path: Path) -> None:
    script = tmp_path / "fake_opencode_acp.py"
    script.write_text(
        dedent(
            """
            import json
            import sys

            for line in sys.stdin:
                msg = json.loads(line)
                rid = msg.get("id")
                method = msg.get("method")
                params = msg.get("params", {})

                if method == "initialize":
                    out = {"jsonrpc":"2.0","id": rid, "result": {"protocolVersion": 1}}
                    print(json.dumps(out), flush=True)
                    continue

                if method == "session/new":
                    out = {"jsonrpc":"2.0","id": rid, "result": {"sessionId": "sess-opencode"}}
                    print(json.dumps(out), flush=True)
                    continue

                if method == "session/prompt":
                    note = {
                        "jsonrpc":"2.0",
                        "method":"session/update",
                        "params":{
                            "sessionId":"sess-opencode",
                            "update":{
                                "sessionUpdate":"agent_message_chunk",
                                "content":{"type":"text","text":"Current time is 10:00."}
                            }
                        }
                    }
                    print(json.dumps(note), flush=True)
                    out = {"jsonrpc":"2.0","id": rid, "result": {"stopReason":"end_turn"}}
                    print(json.dumps(out), flush=True)
                    continue

                if method == "session.close":
                    out = {"jsonrpc":"2.0","id": rid, "result": {"closed": True}}
                    print(json.dumps(out), flush=True)
                    break

                out = {"jsonrpc":"2.0","id": rid, "error": {"message": "unknown method"}}
                print(json.dumps(out), flush=True)
            """
        ),
        encoding="utf-8",
    )

    async def _run() -> None:
        client = StdioAcpSessionClient(
            provider=AcpProviderConfig(
                transport="stdio",
                protocol="auto",
                command=sys.executable,
                args=("-u", str(script)),
                env={},
                cwd=str(tmp_path),
            ),
            timeouts=AcpTimeoutsConfig(session_init_ms=2_000, turn_ms=2_000),
        )
        handle = await client.open(
            SessionInitSpec(
                run_id="r1",
                trace_id="r1",
                task_id="t1",
                session_id="sess1",
                instance_id="inst1",
                role_id="time",
                system_prompt="You are time role.",
            )
        )
        assert handle.metadata.get("protocol") == "opencode_v1"
        result = await client.run_turn(handle, TurnInput(user_prompt="what time is it"))
        assert "10:00" in result.text
        await client.close(handle)

    asyncio.run(_run())


def test_opencode_open_passes_mcp_and_skill_details(tmp_path: Path) -> None:
    script = tmp_path / "fake_opencode_capture.py"
    capture = tmp_path / "capture.json"
    script.write_text(
        dedent(
            f"""
            import json
            import sys
            from pathlib import Path

            capture_path = Path(r"{capture}")

            for line in sys.stdin:
                msg = json.loads(line)
                rid = msg.get("id")
                method = msg.get("method")
                params = msg.get("params", {{}})

                if method == "initialize":
                    out = {{"jsonrpc":"2.0","id": rid, "result": {{"protocolVersion": 1}}}}
                    print(json.dumps(out), flush=True)
                    continue

                if method == "session/new":
                    capture_path.write_text(json.dumps(params), encoding="utf-8")
                    out = {{"jsonrpc":"2.0","id": rid, "result": {{"sessionId": "sess-opencode"}}}}
                    print(json.dumps(out), flush=True)
                    continue

                if method == "session/prompt":
                    out = {{"jsonrpc":"2.0","id": rid, "result": {{"stopReason":"end_turn"}}}}
                    print(json.dumps(out), flush=True)
                    continue
            """
        ),
        encoding="utf-8",
    )

    async def _run() -> None:
        client = StdioAcpSessionClient(
            provider=AcpProviderConfig(
                transport="stdio",
                protocol="opencode_v1",
                command=sys.executable,
                args=("-u", str(script)),
                env={},
                cwd=str(tmp_path),
            ),
            timeouts=AcpTimeoutsConfig(session_init_ms=2_000, turn_ms=2_000),
        )
        handle = await client.open(
            SessionInitSpec(
                run_id="r1",
                trace_id="r1",
                task_id="t1",
                session_id="sess1",
                instance_id="inst1",
                role_id="time",
                system_prompt="You are time role.",
                skills=(
                    {
                        "name": "time",
                        "description": "time skill",
                        "instructions": "Run get_current_time script.",
                        "scripts": ["get_current_time"],
                        "resources": [],
                    },
                ),
                mcp_servers=(
                    {
                        "name": "time-mcp",
                        "config": {
                            "mcpServers": {
                                "time-mcp": {
                                    "command": "npx",
                                    "args": ["-y", "time-mcp"],
                                    "env": {"TZ": "UTC"},
                                }
                            }
                        },
                    },
                ),
            )
        )
        await client.close(handle)

    asyncio.run(_run())

    params = json.loads(capture.read_text(encoding="utf-8"))
    assert isinstance(params["mcpServers"], list)
    assert {
        "name": "time-mcp",
        "command": "npx",
        "args": ["-y", "time-mcp"],
        "env": [{"name": "TZ", "value": "UTC"}],
    } in params["mcpServers"]
    skills_mcp = next(
        (item for item in params["mcpServers"] if item.get("name") == "skills-mcp"),
        None,
    )
    assert isinstance(skills_mcp, dict)
    assert skills_mcp.get("command") == sys.executable
    args = skills_mcp.get("args")
    assert isinstance(args, list)
    assert "-m" in args
    assert "agent_teams" in args
    assert "skills-mcp" in args
    assert "--allowed-skill" in args
    assert "time" in args
    instructions = str(params["instructions"])
    assert "Enabled skills (catalog):" in instructions
    assert "Load skills progressively:" in instructions


def test_opencode_turn_reinjects_role_context(tmp_path: Path) -> None:
    script = tmp_path / "fake_opencode_capture_turn.py"
    capture = tmp_path / "turn_capture.json"
    script.write_text(
        dedent(
            f"""
            import json
            import sys
            from pathlib import Path

            capture_path = Path(r"{capture}")

            for line in sys.stdin:
                msg = json.loads(line)
                rid = msg.get("id")
                method = msg.get("method")
                params = msg.get("params", {{}})

                if method == "initialize":
                    out = {{"jsonrpc":"2.0","id": rid, "result": {{"protocolVersion": 1}}}}
                    print(json.dumps(out), flush=True)
                    continue

                if method == "session/new":
                    out = {{"jsonrpc":"2.0","id": rid, "result": {{"sessionId": "sess-opencode"}}}}
                    print(json.dumps(out), flush=True)
                    continue

                if method == "session/prompt":
                    capture_path.write_text(json.dumps(params), encoding="utf-8")
                    note = {{
                        "jsonrpc":"2.0",
                        "method":"session/update",
                        "params":{{
                            "sessionId":"sess-opencode",
                            "update":{{
                                "sessionUpdate":"agent_message_chunk",
                                "content":{{"type":"text","text":"ok"}}
                            }}
                        }}
                    }}
                    print(json.dumps(note), flush=True)
                    out = {{"jsonrpc":"2.0","id": rid, "result": {{"stopReason":"end_turn"}}}}
                    print(json.dumps(out), flush=True)
                    continue
            """
        ),
        encoding="utf-8",
    )

    async def _run() -> None:
        client = StdioAcpSessionClient(
            provider=AcpProviderConfig(
                transport="stdio",
                protocol="opencode_v1",
                command=sys.executable,
                args=("-u", str(script)),
                env={},
                cwd=str(tmp_path),
            ),
            timeouts=AcpTimeoutsConfig(session_init_ms=2_000, turn_ms=2_000),
        )
        handle = await client.open(
            SessionInitSpec(
                run_id="r1",
                trace_id="r1",
                task_id="t1",
                session_id="sess1",
                instance_id="inst1",
                role_id="time",
                system_prompt="You are time role.",
            )
        )
        await client.run_turn(handle, TurnInput(user_prompt="what time is it"))
        await client.close(handle)

    asyncio.run(_run())

    params = json.loads(capture.read_text(encoding="utf-8"))
    prompt = params.get("prompt")
    assert isinstance(prompt, list)
    assert len(prompt) >= 2
    first = prompt[0]
    second = prompt[1]
    assert isinstance(first, dict)
    assert isinstance(second, dict)
    assert "Role Context:" in str(first.get("text"))
    assert second.get("text") == "what time is it"


