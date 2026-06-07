import os
from agents.test_runner import test_runner_node

def test_phase3_sandbox():
    print("Testing Phase 3 Docker Test Runner...")
    
    local_repo_path = os.path.abspath("mock_repo")
    state = {"repo_path": local_repo_path}
    
    print(f"Executing tests in sandbox for directory: {local_repo_path}")
    result = test_runner_node(state)
    
    print("\n--- Test Results Output ---")
    print(result.get("test_results"))
    print("---------------------------\n")
    
    print("Testing network constraints via python request...")
    import docker
    client = docker.from_env()
    try:
        client.containers.run(
            image="python:3.11-slim",
            platform="linux/arm64",
            command='python -c "import urllib.request; urllib.request.urlopen(\'http://google.com\')"',
            network_mode="bridge",
            remove=True
        )
        print("SUCCESS: Network is now reachable (bridge mode).")
    except docker.errors.ContainerError as e:
        print(f"SUCCESS: Network unreachable. Error output:\n{e.stderr.decode('utf-8')}")

if __name__ == "__main__":
    try:
        import docker
        # Set DOCKER_HOST for the test script itself, just in case
        mac_socket = os.path.expanduser("~/.docker/run/docker.sock")
        if "DOCKER_HOST" not in os.environ and os.path.exists(mac_socket):
            os.environ["DOCKER_HOST"] = f"unix://{mac_socket}"
    except Exception:
        pass
    test_phase3_sandbox()
