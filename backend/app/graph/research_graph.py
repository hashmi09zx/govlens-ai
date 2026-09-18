from langgraph.graph import StateGraph, START, END
from app.graph.state import ResearchState
from app.graph.checkpointer import get_checkpointer
from app.agents.query_agent import query_agent_node
from app.agents.recruitment_id_agent import recruitment_id_agent_node
from app.agents.source_agent import source_agent_node
from app.agents.extraction_agent import extraction_agent_node
from app.agents.conflict_agent import conflict_agent_node
from app.agents.verification_agent import verification_agent_node
from app.agents.report_agent import report_agent_node
from app.agents.request_agent import request_agent_node


def check_recruitment_ambiguity(state: ResearchState) -> str:
    status = state.get("research_status", {})
    if status.get("recruitment_id") == "ambiguous":
        return "ambiguous"
    return "resolved"


def build_research_graph():
    builder = StateGraph(ResearchState)

    # Register nodes
    builder.add_node("query_agent", query_agent_node)
    builder.add_node("recruitment_id_agent", recruitment_id_agent_node)
    builder.add_node("source_agent", source_agent_node)
    builder.add_node("extraction_agent", extraction_agent_node)
    builder.add_node("conflict_agent", conflict_agent_node)
    builder.add_node("verification_agent", verification_agent_node)
    builder.add_node("report_agent", report_agent_node)
    builder.add_node("request_agent", request_agent_node)

    # Edges
    builder.add_edge(START, "query_agent")
    builder.add_edge("query_agent", "recruitment_id_agent")

    builder.add_conditional_edges(
        "recruitment_id_agent",
        check_recruitment_ambiguity,
        {
            "ambiguous": END,
            "resolved": "source_agent",
        },
    )

    builder.add_edge("source_agent", "extraction_agent")
    builder.add_edge("extraction_agent", "conflict_agent")
    builder.add_edge("conflict_agent", "verification_agent")
    builder.add_edge("verification_agent", "report_agent")
    builder.add_edge("report_agent", END)

    # HITL flow
    builder.add_edge("request_agent", "source_agent")

    checkpointer = get_checkpointer()
    return builder.compile(checkpointer=checkpointer)


# Instantiated graph
research_graph = build_research_graph()
