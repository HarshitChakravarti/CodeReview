from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from graph.state import ReviewState
from agents.diff_reader import diff_reader_node
from agents.security_scanner import security_scanner_node
from agents.logic_reviewer import logic_reviewer_node

def route_to_reviewers(state: ReviewState):
    # This is the routing function that enables parallel execution.
    # Instead of picking just one path, we use the `Send` API to fan-out to 
    # multiple nodes simultaneously. Each node receives the current state.
    
    # We send the state to both the security scanner and the logic reviewer.
    return [
        Send("security_scanner", state),
        Send("logic_reviewer", state)
    ]

# 1. Initialize the graph with our defined state schema
workflow = StateGraph(ReviewState)

# 2. Add all our agent nodes to the graph
workflow.add_node("diff_reader", diff_reader_node)
workflow.add_node("security_scanner", security_scanner_node)
workflow.add_node("logic_reviewer", logic_reviewer_node)

# 3. Define the flow edges
# The graph always starts at the diff_reader to clone the repo and get the diffs.
workflow.add_edge(START, "diff_reader")

# After the diff_reader completes, we hit a conditional edge.
# The `route_to_reviewers` function will fan-out execution to both reviewers.
# By passing the node names as a list in the third argument, we declare the possible destinations.
workflow.add_conditional_edges(
    "diff_reader", 
    route_to_reviewers, 
    ["security_scanner", "logic_reviewer"]
)

# Temporarily, for Phase 2 testing, we wire both parallel agents directly to END.
# In Phase 3, these will route to the test runner instead.
workflow.add_edge("security_scanner", END)
workflow.add_edge("logic_reviewer", END)

# 4. Compile the graph into an executable application
# We are omitting the checkpointer for now; it will be added in Phase 4.
graph = workflow.compile()
