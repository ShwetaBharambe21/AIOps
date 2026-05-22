import subprocess
import json
import shutil
from typing import Optional


def _find_kubectl() -> str:
    """Resolve the kubectl binary — prefers 'kubectl', falls back to 'kubectl.docker'."""
    for candidate in ("kubectl", "kubectl.docker"):
        path = shutil.which(candidate)
        if path:
            probe = subprocess.run([path, "version", "--client"], capture_output=True)
            if probe.returncode == 0:
                return path
    return "kubectl"  # last-resort, will surface a clear error


_KUBECTL = _find_kubectl()


def run_kubectl(args: list[str]) -> tuple[str, str, int]:
    """Run a kubectl command and return (stdout, stderr, returncode)."""
    cmd = [_KUBECTL] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout, result.stderr, result.returncode


def get_pods(namespace: str = "--all-namespaces") -> str:
    """Get all pods with status."""
    if namespace == "--all-namespaces":
        stdout, stderr, rc = run_kubectl([
            "get", "pods", "-A", "-o", "wide", "--no-headers",
            "--sort-by=.metadata.namespace"
        ])
    else:
        stdout, stderr, rc = run_kubectl([
            "get", "pods", "-n", namespace, "-o", "wide", "--no-headers"
        ])
    return stdout if rc == 0 else f"ERROR: {stderr}"


def get_pods_json(namespace: str = "--all-namespaces") -> dict:
    """Get pods as JSON for structured parsing."""
    args = ["get", "pods", "-o", "json"]
    if namespace == "--all-namespaces":
        args.insert(2, "-A")
    else:
        args.extend(["-n", namespace])
    stdout, _, rc = run_kubectl(args)
    if rc != 0:
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {}


def get_events(namespace: str = "--all-namespaces", event_type: str = "Warning") -> str:
    """Get recent warning events from the cluster."""
    if namespace == "--all-namespaces":
        stdout, stderr, rc = run_kubectl([
            "get", "events", "-A",
            "--field-selector", f"type={event_type}",
            "--sort-by=.lastTimestamp",
            "-o", "custom-columns=NAMESPACE:.metadata.namespace,NAME:.involvedObject.name,KIND:.involvedObject.kind,REASON:.reason,MESSAGE:.message,TIME:.lastTimestamp",
        ])
    else:
        stdout, stderr, rc = run_kubectl([
            "get", "events", "-n", namespace,
            "--field-selector", f"type={event_type}",
            "--sort-by=.lastTimestamp",
        ])
    return stdout if rc == 0 else f"ERROR: {stderr}"


def get_pod_logs(pod_name: str, namespace: str, container: Optional[str] = None, lines: int = 50) -> str:
    """Get recent logs from a pod, falling back to previous container if crashing."""
    args = ["logs", pod_name, "-n", namespace, "--tail", str(lines), "--timestamps"]
    if container:
        args.extend(["-c", container])

    stdout, stderr, rc = run_kubectl(args)
    if rc != 0:
        stdout_prev, _, rc_prev = run_kubectl(args + ["--previous"])
        if rc_prev == 0:
            return f"[Previous container logs]\n{stdout_prev}"
        return f"ERROR: {stderr}"
    return stdout


def get_nodes() -> str:
    """Get node status."""
    stdout, stderr, rc = run_kubectl(["get", "nodes", "-o", "wide", "--no-headers"])
    return stdout if rc == 0 else f"ERROR: {stderr}"


def get_nodes_json() -> dict:
    """Get nodes as JSON."""
    stdout, _, rc = run_kubectl(["get", "nodes", "-o", "json"])
    if rc != 0:
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {}


def get_deployments(namespace: str = "--all-namespaces") -> str:
    """Get deployments status."""
    args = ["get", "deployments", "-o", "wide", "--no-headers"]
    if namespace == "--all-namespaces":
        args.insert(2, "-A")
    else:
        args.extend(["-n", namespace])
    stdout, stderr, rc = run_kubectl(args)
    return stdout if rc == 0 else f"ERROR: {stderr}"


def get_deployments_json(namespace: str = "--all-namespaces") -> dict:
    """Get deployments as JSON."""
    args = ["get", "deployments", "-o", "json"]
    if namespace == "--all-namespaces":
        args.insert(2, "-A")
    else:
        args.extend(["-n", namespace])
    stdout, _, rc = run_kubectl(args)
    if rc != 0:
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {}


def get_resource_metrics() -> str:
    """Get CPU/memory usage via kubectl top (requires metrics-server)."""
    stdout_nodes, _, rc_nodes = run_kubectl(["top", "nodes", "--no-headers"])
    stdout_pods, _, rc_pods = run_kubectl(["top", "pods", "-A", "--no-headers"])

    parts = []
    parts.append("=== Node Resource Usage ===")
    parts.append(stdout_nodes if rc_nodes == 0 else "Metrics server not available")
    parts.append("\n=== Pod Resource Usage ===")
    parts.append(stdout_pods if rc_pods == 0 else "Metrics server not available")
    return "\n".join(parts)


def get_cluster_info() -> str:
    """Get basic cluster information."""
    stdout, stderr, rc = run_kubectl(["cluster-info"])
    return stdout if rc == 0 else f"ERROR: {stderr}"


def describe_pod(pod_name: str, namespace: str) -> str:
    """Get detailed description of a pod."""
    stdout, stderr, rc = run_kubectl(["describe", "pod", pod_name, "-n", namespace])
    return stdout if rc == 0 else f"ERROR: {stderr}"


def get_current_context() -> str:
    """Get current kubectl context name."""
    stdout, stderr, rc = run_kubectl(["config", "current-context"])
    return stdout.strip() if rc == 0 else "unknown-cluster"
