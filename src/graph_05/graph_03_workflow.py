"""Graph flow 03: construct the stateless LangGraph workflow."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from src.domain_01.domain_03_models import QueryResult
from src.graph_05.graph_01_state import GraphState
from src.graph_05.graph_02_nodes import GraphNodes


def compile_graph(nodes: GraphNodes) -> Any:
    """Compile the linear graph without a checkpointer or persistent store."""

    builder = StateGraph(GraphState)
    builder.add_node("check_input", nodes.check_input)
    builder.add_node("route", nodes.route)
    builder.add_node("retrieve", nodes.retrieve)
    builder.add_node("generate", nodes.generate)
    builder.add_node("check_output", nodes.check_output)
    builder.add_edge(START, "check_input")
    builder.add_edge("check_input", "route")
    builder.add_edge("route", "retrieve")
    builder.add_edge("retrieve", "generate")
    builder.add_edge("generate", "check_output")
    builder.add_edge("check_output", END)
    return builder.compile()


class QueryService:
    """Run one question through the compiled graph."""

    def __init__(self, graph: Any, *, request_timeout_seconds: float) -> None:
        self._graph = graph
        self.request_timeout_seconds = request_timeout_seconds

    async def ask(self, question: str) -> QueryResult:
        """Return the final result from one graph invocation."""

        final_state = await self._graph.ainvoke({"question": question})
        return final_state["result"]
