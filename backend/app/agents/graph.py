"""LangGraph graph definition for GigPilot proposal drafting (04_TRD §2)."""

from langgraph.graph import END, StateGraph

from app.agents.nodes import draft_node, retrieve_voice_node  # nodes/ package
from app.agents.state import GigPilotState


def build_graph():
    g = StateGraph(GigPilotState)

    g.add_node("retrieve_voice", retrieve_voice_node)
    g.add_node("generate_draft", draft_node)

    g.set_entry_point("retrieve_voice")
    g.add_edge("retrieve_voice", "generate_draft")
    g.add_edge("generate_draft", END)

    return g.compile()


graph = build_graph()
