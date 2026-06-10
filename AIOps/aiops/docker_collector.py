import subprocess
import json


def _run_docker(args: list[str]) -> tuple[str, str, int]:
    result = subprocess.run(["docker"] + args, capture_output=True, text=True)
    return result.stdout, result.stderr, result.returncode


def get_running_containers() -> str:
    """List all running Docker containers."""
    stdout, stderr, rc = _run_docker(["ps", "--format",
        "table {{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"])
    return stdout if rc == 0 else f"ERROR: {stderr}"


def get_all_containers() -> str:
    """List all Docker containers including stopped ones."""
    stdout, stderr, rc = _run_docker(["ps", "-a", "--format",
        "table {{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"])
    return stdout if rc == 0 else f"ERROR: {stderr}"


def get_all_containers_json() -> list[dict]:
    """Return all containers as structured list for anomaly detection."""
    stdout, _, rc = _run_docker(["ps", "-a", "--format", "{{json .}}"])
    if rc != 0:
        return []
    containers = []
    for line in stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            containers.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return containers


def get_container_logs(container_name: str, lines: int = 50) -> str:
    """Get recent logs from a Docker container, falling back to nothing if missing."""
    stdout, stderr, rc = _run_docker([
        "logs", "--tail", str(lines), "--timestamps", container_name
    ])
    if rc != 0:
        return f"ERROR: {stderr}"
    return stdout or stderr  # docker logs go to stderr by default


def get_container_inspect(container_name: str) -> str:
    """Get detailed inspect output for a container."""
    stdout, stderr, rc = _run_docker(["inspect", container_name])
    return stdout if rc == 0 else f"ERROR: {stderr}"


def get_docker_stats() -> str:
    """Get current CPU/memory stats for all running containers (snapshot)."""
    stdout, stderr, rc = _run_docker([
        "stats", "--no-stream", "--format",
        "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}"
    ])
    return stdout if rc == 0 else f"ERROR: {stderr}"


def is_docker_available() -> bool:
    """Return True if Docker daemon is reachable."""
    _, _, rc = _run_docker(["info"])
    return rc == 0
