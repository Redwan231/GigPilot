"""P2-10: LangGraph agents — state structure and graph compilation."""

from app.agents.graph import graph
from app.agents.state import GigPilotState


def test_graph_compiles() -> None:
    assert graph is not None


def test_state_shape() -> None:
    state: GigPilotState = {
        "user_id": "uid",
        "job_id": "jid",
        "profile_summary": "skills: python",
        "job_summary": "build stuff",
        "score": 80,
        "voice_chunks": [],
        "draft": None,
        "voice_matched": False,
        "error": None,
    }
    assert state["user_id"] == "uid"
    assert state["voice_matched"] is False


def test_graph_has_nodes() -> None:
    node_names = set(graph.nodes.keys())
    assert "retrieve_voice" in node_names
    assert "generate_draft" in node_names
