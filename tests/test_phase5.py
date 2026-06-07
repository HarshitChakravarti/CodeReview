from fastapi.testclient import TestClient
from api.main import app
import time

client = TestClient(app)

def test_phase5_api():
    print("Testing Phase 5 FastAPI Webhook Server...")
    
    # 1. Simulate an incoming GitHub webhook
    mock_github_payload = {
        "action": "opened",
        "pull_request": {
            "number": 1,
            "base": {"sha": "d0dd1f61b33d64e29d8bc1372a94ef6a2fee76a9"},
            "head": {"sha": "f439fc5710cd87a4025247e8f75901cdadf5333d"}
        },
        "repository": {
            "clone_url": "https://github.com/octocat/Spoon-Knife.git"
        }
    }
    
    print("\n--- Sending mock webhook ---")
    response = client.post(
        "/webhook/github", 
        json=mock_github_payload,
        headers={"X-GitHub-Event": "pull_request"}
    )
    
    print(f"Webhook Status Code: {response.status_code}")
    print(f"Webhook Response: {response.json()}")
    
    thread_id = response.json().get("thread_id")
    
    # 2. Wait for background task to reach the interrupt
    print(f"\n--- Waiting for graph to pause (Thread: {thread_id}) ---")
    print("This will take a few seconds as the graph clones, runs LLMs, etc...")
    
    max_retries = 30
    pending_data = None
    for i in range(max_retries):
        time.sleep(1)
        res = client.get("/reviews/pending")
        pending_reviews = res.json()
        
        if pending_reviews and pending_reviews[0]["thread_id"] == thread_id:
            pending_data = pending_reviews[0]["data"]
            print(f"Graph paused! Found in pending reviews.")
            break
        print(".", end="", flush=True)
        
    if not pending_data:
        print("\nError: Background task did not add review to pending list in time.")
        return
        
    print(f"\nPending Data Draft Snippet:\n{pending_data.get('draft_review')[:100]}...\n")
    
    # 3. Simulate dashboard approval
    print("\n--- Sending Approval from Dashboard ---")
    approve_res = client.post(
        f"/reviews/{thread_id}/approve",
        json={"comment": "Looks good from the API test!"}
    )
    print(f"Approve Status: {approve_res.status_code}")
    print(f"Approve Response: {approve_res.json()}")
    
    # 4. Verify it was removed from pending
    final_pending = client.get("/reviews/pending").json()
    print(f"\nFinal Pending Count: {len(final_pending)}")

if __name__ == "__main__":
    test_phase5_api()
