import os
import hmac
import hashlib
import uuid
import json
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langgraph.types import Command

from graph.graph import graph

app = FastAPI(title="CodeReview Agent API")

# Add CORS middleware to allow requests from the future Next.js dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for pending reviews to feed the dashboard.
# In a true production app, this would be a database table.
pending_reviews: Dict[str, Any] = {}

class ApprovalRequest(BaseModel):
    comment: str = ""

def verify_github_signature(payload_body: bytes, signature_header: str) -> bool:
    """
    Verifies that the webhook request actually came from GitHub by hashing the body
    with our shared secret and comparing it to the signature header.
    """
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
    if not secret:
        # For local testing if secret isn't set, we bypass. In prod, this is unsafe.
        print("[WARNING] GITHUB_WEBHOOK_SECRET not set, bypassing signature validation.")
        return True
        
    if not signature_header:
        return False
        
    hash_object = hmac.new(secret.encode('utf-8'), msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()
    
    # hmac.compare_digest prevents timing attacks
    return hmac.compare_digest(expected_signature, signature_header)

def run_review_graph(thread_id: str, state: dict):
    """
    This function runs in the background. It executes the LangGraph workflow
    until it hits the human_approval interrupt.
    """
    print(f"[Background] Starting graph execution for thread {thread_id}")
    config = {"configurable": {"thread_id": thread_id}}
    
    # Stream the graph execution
    for event in graph.stream(state, config=config):
        pass # We just let it run
        
    # Once it pauses at the interrupt, we grab the state snapshot
    snapshot = graph.get_state(config)
    
    # If it paused properly on the human_approval node, extract the interrupt data
    if snapshot.tasks and snapshot.tasks[0].interrupts:
        interrupt_data = snapshot.tasks[0].interrupts[0].value
        # Store it in memory so the Next.js dashboard can fetch it via GET /reviews/pending
        pending_reviews[thread_id] = interrupt_data
        print(f"[Background] Review {thread_id} paused and added to pending list.")
    else:
        print(f"[Background] Error: Graph for {thread_id} finished without pausing.")

@app.post("/webhook/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receives Pull Request events from GitHub.
    """
    # 1. Verify Signature
    signature = request.headers.get("X-Hub-Signature-256")
    body = await request.body()
    if not verify_github_signature(body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # 2. Only process PR opened or synchronized (updated) events
    # We ignore labeled, assigned, closed, etc.
    event_type = request.headers.get("X-GitHub-Event")
    if event_type != "pull_request":
        return {"status": "ignored", "reason": "Not a pull request event"}
        
    action = payload.get("action")
    if action not in ["opened", "synchronize"]:
        return {"status": "ignored", "reason": f"Action '{action}' ignored"}

    pr_data = payload.get("pull_request", {})
    repo_data = payload.get("repository", {})
    
    # 3. Extract necessary data for the graph state
    repo_url = repo_data.get("clone_url") # e.g. https://github.com/owner/repo.git
    pr_number = pr_data.get("number")
    base_sha = pr_data.get("base", {}).get("sha")
    head_sha = pr_data.get("head", {}).get("sha")

    if not all([repo_url, pr_number, base_sha, head_sha]):
         raise HTTPException(status_code=400, detail="Missing required PR data in payload")

    # 4. Generate unique thread ID for LangGraph checkpointer
    thread_id = str(uuid.uuid4())
    
    initial_state = {
        "repo_url": repo_url,
        "pr_number": pr_number,
        "base_sha": base_sha,
        "head_sha": head_sha
    }

    # 5. Kick off the background task
    # We MUST use background tasks because GitHub requires a 2xx response within 10 seconds.
    # Our graph takes much longer due to LLM calls and Docker testing.
    background_tasks.add_task(run_review_graph, thread_id, initial_state)

    return {"status": "review started", "thread_id": thread_id}

@app.get("/reviews/pending")
def get_pending_reviews():
    """
    Called by the Next.js dashboard to list all reviews waiting for human approval.
    """
    # Convert dict to a list for easier frontend rendering
    return [
        {"thread_id": tid, "data": data} 
        for tid, data in pending_reviews.items()
    ]

@app.post("/reviews/{thread_id}/approve")
def approve_review(thread_id: str, request: ApprovalRequest, background_tasks: BackgroundTasks):
    """
    Called by the dashboard when the human clicks 'Approve'.
    """
    if thread_id not in pending_reviews:
        raise HTTPException(status_code=404, detail="Review not found or already processed")
        
    # Remove from pending list immediately so it disappears from dashboard
    del pending_reviews[thread_id]
    
    config = {"configurable": {"thread_id": thread_id}}
    
    # Define a quick wrapper to run the resume in the background
    def resume_graph():
        print(f"[API] Resuming graph {thread_id} with APPROVE command.")
        resume_cmd = Command(resume={"approved": True, "comment": request.comment})
        for event in graph.stream(resume_cmd, config=config):
            pass
            
    background_tasks.add_task(resume_graph)
    return {"status": "approved, resuming workflow"}

@app.post("/reviews/{thread_id}/reject")
def reject_review(thread_id: str, background_tasks: BackgroundTasks):
    """
    Called by the dashboard when the human clicks 'Reject'.
    """
    if thread_id not in pending_reviews:
        raise HTTPException(status_code=404, detail="Review not found or already processed")
        
    del pending_reviews[thread_id]
    
    config = {"configurable": {"thread_id": thread_id}}
    
    def resume_graph():
        print(f"[API] Resuming graph {thread_id} with REJECT command.")
        resume_cmd = Command(resume={"approved": False})
        for event in graph.stream(resume_cmd, config=config):
            pass
            
    background_tasks.add_task(resume_graph)
    return {"status": "rejected, resuming workflow"}
