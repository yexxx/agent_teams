from agent_teams.acp.session_client import SessionHandle
from agent_teams.acp.session_pool import AcpSessionPool, SessionBinding


def test_acp_session_pool_set_get_pop() -> None:
    pool = AcpSessionPool()
    handle = SessionHandle(session_id="s1", instance_id="i1")
    binding = SessionBinding(client_id="acp:default", handle=handle)

    assert pool.get("i1") is None
    pool.set("i1", binding)
    assert pool.get("i1") == binding
    assert pool.pop("i1") == binding
    assert pool.get("i1") is None
