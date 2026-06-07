from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    message: str
    response: str


def fill_response(state: State) -> State:
    state["response"] = f"Received: {state['message']}"
    return state


graph_builder = StateGraph(State)
graph_builder.add_node("fill_response", fill_response)
graph_builder.add_edge(START, "fill_response")
graph_builder.add_edge("fill_response", END)

graph = graph_builder.compile()
result = graph.invoke({"message": "hello langgraph", "response": ""})

print(result)
