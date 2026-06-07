import uuid
from langgraph.types import Command
from graph.graph import graph

def test_phase4_human_in_loop():
    print("Testing Phase 4: Graph Interrupt and Resume...")
    
    # We generate a unique thread_id for this specific PR review run.
    # This is how the SqliteSaver knows which state to save/load.
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    # Initial state mimicking a tiny, real PR to make the test fast
    initial_state = {
        "repo_url": "https://github.com/octocat/Spoon-Knife.git",
        "pr_number": 1,
        "base_sha": "d0dd1f61b33d64e29d8bc1372a94ef6a2fee76a9", # main branch
        "head_sha": "f439fc5710cd87a4025247e8f75901cdadf5333d"  # change-the-title branch
    }
    
    print(f"--- Starting Graph Execution (Thread ID: {thread_id}) ---")
    
    # Run the graph. It should run through Diff Reader, Security/Logic Scanners,
    # Test Runner, and Review Writer, then PAUSE at the Human Approval node.
    for event in graph.stream(initial_state, config=config):
        for node_name, node_state in event.items():
            print(f"> Completed Node: {node_name}")
            
    # At this point, the graph should be paused.
    # We can inspect the state to confirm it's waiting on an interrupt.
    snapshot = graph.get_state(config)
    print("\n--- Graph Paused ---")
    print(f"Next node to execute: {snapshot.next}")
    
    if snapshot.tasks and snapshot.tasks[0].interrupts:
        interrupt_data = snapshot.tasks[0].interrupts[0].value
        print("\n--- Interrupt Payload (Sent to Dashboard) ---")
        print(f"PR Number: {interrupt_data.get('pr_number')}")
        print(f"Findings Count: {interrupt_data.get('findings_count')}")
        print("Draft Review Snippet:")
        print(interrupt_data.get('draft_review')[:200] + "...\n")
        
        print("\n--- Simulating Human Approval ---")
        # We send a Command to resume the graph, passing the human's decision.
        resume_command = Command(resume={"approved": True, "comment": "Great job, looks safe to merge."})
        
        # Resume the graph execution
        for event in graph.stream(resume_command, config=config):
            for node_name, node_state in event.items():
                print(f"> Completed Node: {node_name}")
                
        # Get the final state
        final_state = graph.get_state(config).values
        print("\n--- Final State ---")
        print(f"Action taken: {final_state.get('action')}")
        print(f"Human Comment: {final_state.get('human_comment')}")
        
    else:
        print("Error: Graph did not pause on an interrupt as expected.")

if __name__ == "__main__":
    test_phase4_human_in_loop()
