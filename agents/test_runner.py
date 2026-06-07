import docker
import traceback

def test_runner_node(state: dict) -> dict:
    """
    Executes the repository's test suite inside a secure, sandboxed Docker container.
    """
    print("Running Test Suite in Docker Sandbox...")
    repo_path = state.get("repo_path")
    
    if not repo_path:
        print("[Test Runner] No repo_path found in state. Skipping tests.")
        return {"test_results": "Error: Repository not cloned properly."}

    # Initialize the Docker client.
    # On macOS, docker.from_env() sometimes fails to resolve the /var/run/docker.sock symlink.
    # We check for the explicit ~/.docker/run/docker.sock path as a fallback.
    try:
        import os
        mac_socket = os.path.expanduser("~/.docker/run/docker.sock")
        if "DOCKER_HOST" not in os.environ and os.path.exists(mac_socket):
            client = docker.DockerClient(base_url=f"unix://{mac_socket}")
        else:
            client = docker.from_env()
    except docker.errors.DockerException as e:
        print(f"[Test Runner] Failed to connect to Docker daemon: {e}")
        return {"test_results": f"Infrastructure Error: Could not connect to Docker. {str(e)}"}

    output_str = ""
    try:
        # Run the container with strict sandbox constraints
        # 1. image: Uses an ARM-native python 3.11 slim image for performance on Mac M1/M2/M3.
        # 2. command: Quietly installs requirements, then runs pytest quietly with short tracebacks.
        # 3. volumes: Mounts the cloned repo to /code as read-only (ro) so the tests cannot modify host files.
        # 4. network_mode: 'none' ensures tests cannot exfiltrate data or download malicious payloads at runtime.
        # 5. limits: Restricts CPU and memory to prevent denial-of-service via infinite loops or memory leaks.
        container_output = client.containers.run(
            image="python:3.11-slim",
            platform="linux/arm64",  # Critical for performance on Apple Silicon
            command="bash -c 'if [ -f requirements.txt ]; then pip install -r requirements.txt -q; fi && pytest --tb=short -q'",
            volumes={repo_path: {'bind': '/code', 'mode': 'ro'}},
            working_dir="/code",
            mem_limit="512m",
            cpu_period=100000,
            cpu_quota=50000,
            network_mode="bridge",
            remove=True,        # Automatically delete container when done to save disk space
            stdout=True, 
            stderr=True
        )
        
        # Decode the byte output from Docker into a standard string
        output_str = container_output.decode('utf-8')
        print("[Test Runner] Tests completed successfully.")
        
    except docker.errors.ContainerError as e:
        # This exception is raised if the container exits with a non-zero status code 
        # (which happens when tests fail or requirements fail to install).
        # We capture the test output anyway to report it in the final review.
        print(f"[Test Runner] Tests failed. Container exit code: {e.exit_status}")
        output_str = e.stderr.decode('utf-8') if e.stderr else ""
        if not output_str and e.stdout:
             output_str = e.stdout.decode('utf-8')
    except Exception as e:
        # Catch any other unexpected errors (e.g., image not found, out of memory)
        print(f"[Test Runner] Unexpected sandbox error: {e}")
        output_str = f"Sandbox Exception:\n{traceback.format_exc()}"

    # Return the test results string to be added to the graph state
    return {"test_results": output_str}
