import os
from github import Github
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send, interrupt, Command
from langgraph.checkpoint.sqlite import SqliteSaver

from graph.state import ReviewState
from agents.diff_reader import diff_reader_node
from agents.security_scanner import security_scanner_node
from agents.logic_reviewer import logic_reviewer_node
from agents.test_runner import test_runner_node
from agents.review_writer import review_writer_node

def route_to_reviewers(state: ReviewState):
    return [
        Send("security_scanner", state),
        Send("logic_reviewer", state)
    ]

def human_approval_node(state: ReviewState):
    """
    Pauses graph execution to wait for a human to review the draft.
    Uses LangGraph's interrupt() feature.
    """
    print("\n[Node] Pausing for Human Approval...")
    
    # The dictionary passed to interrupt() is what the API/Dashboard will receive.
    # Execution halts here until the user provides a Command(resume=...)
    decision = interrupt({
        "draft_review": state.get("draft_review"),
        "pr_number": state.get("pr_number"),
        "findings_count": len(state.get("findings", []))
    })
    
    # When resumed, 'decision' contains the dictionary passed via `Command(resume={...})`
    print("\n[Node] Resuming from Human Approval...")
    return {
        "action": "approve" if decision.get("approved") else "reject",
        "human_comment": decision.get("comment", "")
    }

def post_to_github_node(state: ReviewState):
    """
    Posts the final approved review back to the GitHub PR.
    """
    if state.get("action") != "approve":
        print("[Node] Review rejected by human. Skipping GitHub post.")
        return {}
        
    print("[Node] Posting approved review to GitHub...")
    token = os.environ.get("GITHUB_TOKEN")
    if not token or token == "your_github_personal_access_token":
        print("[WARNING] Valid GITHUB_TOKEN not found in environment. Skipping actual post.")
        return {}
        
    try:
        g = Github(token)
        url = state.get("repo_url", "")
        # Basic parsing: https://github.com/owner/repo.git -> owner/repo
        repo_name = url.replace("https://github.com/", "").replace(".git", "")
        
        repo = g.get_repo(repo_name)
        pr = repo.get_pull(state.get("pr_number"))
        
        comment_body = state.get("draft_review", "")
        if state.get("human_comment"):
             comment_body += f"\n\n**Human Reviewer Comment:**\n{state['human_comment']}"
             
        # Create a review comment on the PR
        pr.create_review(body=comment_body, event="COMMENT")
        print(f"[Node] Review posted successfully to PR #{state.get('pr_number')}")
    except Exception as e:
        print(f"[ERROR] Failed to post to GitHub: {e}")
        
    return {}

workflow = StateGraph(ReviewState)

workflow.add_node("diff_reader", diff_reader_node)
workflow.add_node("security_scanner", security_scanner_node)
workflow.add_node("logic_reviewer", logic_reviewer_node)
workflow.add_node("test_runner", test_runner_node)
workflow.add_node("review_writer", review_writer_node)
workflow.add_node("human_approval", human_approval_node)
workflow.add_node("post_to_github", post_to_github_node)

# Execution Flow
workflow.add_edge(START, "diff_reader")

workflow.add_conditional_edges(
    "diff_reader", 
    route_to_reviewers, 
    ["security_scanner", "logic_reviewer"]
)

# Fan-in: Both parallel agents route to test_runner.
# LangGraph waits for all nodes in this superstep to finish before running test_runner.
workflow.add_edge("security_scanner", "test_runner")
workflow.add_edge("logic_reviewer", "test_runner")

workflow.add_edge("test_runner", "review_writer")
workflow.add_edge("review_writer", "human_approval")
workflow.add_edge("human_approval", "post_to_github")
workflow.add_edge("post_to_github", END)

# Set up SQLite checkpointer for state persistence.
# This writes the graph state to disk (reviews.db) so it can safely pause at `interrupt()`
# and be re-hydrated later when the human submits their approval.
import sqlite3
# check_same_thread=False allows FastAPI to use the same connection across requests later
conn = sqlite3.connect("reviews.db", check_same_thread=False)
checkpointer = SqliteSaver(conn)
graph = workflow.compile(checkpointer=checkpointer)
