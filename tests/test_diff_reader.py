from agents.diff_reader import diff_reader_node
import json

def test_diff_reader():
    # Test state with a real public repo and real commit SHAs
    state = {
        "repo_url": "https://github.com/psf/requests.git",
        "pr_number": 1,
        "base_sha": "e50e5945294f79ee9ab4ec69de24d14f9b26a7ae",
        "head_sha": "1190afd14fca74292946d62c4c8169880a47ff67"
    }
    
    print("Testing diff_reader_node...")
    result = diff_reader_node(state)
    
    print("\nResult Keys:", result.keys())
    print("Repo Path:", result.get("repo_path"))
    print("Number of file diffs:", len(result.get("file_diffs", [])))
    
    # Print the first file diff as a sample
    if result.get("file_diffs"):
        first_file = result["file_diffs"][0]
        print(f"\nFirst file: {first_file['filename']}")
        print(f"Diff length: {len(first_file['diff'])} chars")
        # print("Diff Snippet:", first_file['diff'][:200] + "...")

if __name__ == "__main__":
    test_diff_reader()
