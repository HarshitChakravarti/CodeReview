import tempfile
import git
import os
from typing import List
import numpy

def parse_diff_by_file(raw_diff: str) -> List[dict]:
    # We split the raw diff string by 'diff --git' to isolate changes for each file.
    # The first element in the split is usually empty if the diff starts with 'diff --git',
    # so we filter out any empty strings.
    chunks = raw_diff.split("diff --git")
    file_chunks = []
    
    for chunk in chunks:
        if not chunk.strip():
            continue
            
        # Re-add 'diff --git' because split() removes it. 
        # We need it to identify the file name and for potential downstream parsing.
        full_chunk = "diff --git" + chunk
        
        # Simple extraction of filename: look for 'b/' in the first line
        # A typical line: 'diff --git a/file.txt b/file.txt'
        lines = full_chunk.splitlines()
        filename = "unknown"
        if lines:
            header = lines[0]
            if " b/" in header:
                filename = header.split(" b/")[-1].strip()
        
        file_chunks.append({
            "filename": filename,
            "diff": full_chunk
        })
        
    return file_chunks

def diff_reader_node(state: dict) -> dict:
    # 1. Create a temporary directory for cloning the repository.
    # This ensures we don't pollute the local filesystem and cleanup is easier.
    tmp_dir = tempfile.mkdtemp()
    
    print(f"Cloning {state['repo_url']} into {tmp_dir}...")
    
    # 2. Clone the repository at the specified URL.
    # git.Repo.clone_from is a high-level function from GitPython.
    repo = git.Repo.clone_from(state["repo_url"], tmp_dir)
    
    # 3. Extract the raw diff between base_sha and head_sha.
    # repo.git.diff allows us to run standard git diff commands via Python.
    raw_diff = repo.git.diff(state["base_sha"], state["head_sha"])
    
    # 4. Parse the raw diff into chunks separated by file.
    file_chunks = parse_diff_by_file(raw_diff)
    
    # 5. Return the updated state.
    # Note: repo_path will be used by the test_runner node later.
    return {
        "repo_path": tmp_dir,
        "raw_diff": raw_diff,
        "file_diffs": file_chunks
    }
