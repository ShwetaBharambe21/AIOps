import uuid
from typing import List
from .models import Anomaly, Severity, AnomalyType
from .collector import get_pods_json, get_nodes_json, get_deployments_json, get_pvcs_json, get_jobs_json
from .docker_collector import get_all_containers_json, is_docker_available


def detect_pod_anomalies(pods_data: dict) -> List[Anomaly]:
    """Detect anomalies from pod JSON data."""
    anomalies = []

    for pod in pods_data.get("items", []):
        namespace = pod.get("metadata", {}).get("namespace", "unknown")
        name = pod.get("metadata", {}).get("name", "unknown")
        phase = pod.get("status", {}).get("phase", "")

        all_statuses = (
            pod.get("status", {}).get("containerStatuses", [])
            + pod.get("status", {}).get("initContainerStatuses", [])
        )

        for cs in all_statuses:
            restart_count = cs.get("restartCount", 0)
            waiting = cs.get("state", {}).get("waiting", {})
            terminated = cs.get("state", {}).get("terminated", {})
            waiting_reason = waiting.get("reason", "")
            terminated_reason = terminated.get("reason", "")
            container_name = cs.get("name", "")

            if waiting_reason == "CrashLoopBackOff":
                anomalies.append(Anomaly(
                    id=str(uuid.uuid4()),
                    severity=Severity.CRITICAL,
                    type=AnomalyType.CRASH_LOOP_BACK_OFF,
                    resource=name,
                    namespace=namespace,
                    message=f"Container '{container_name}' is in CrashLoopBackOff with {restart_count} restarts. {waiting.get('message', '')}",
                    raw_status=waiting_reason,
                    restart_count=restart_count,
                ))

            elif waiting_reason in ("ImagePullBackOff", "ErrImagePull"):
                anomalies.append(Anomaly(
                    id=str(uuid.uuid4()),
                    severity=Severity.CRITICAL,
                    type=AnomalyType.IMAGE_PULL_BACK_OFF,
                    resource=name,
                    namespace=namespace,
                    message=f"Container '{container_name}' cannot pull image. {waiting.get('message', '')}",
                    raw_status=waiting_reason,
                ))

            elif terminated_reason == "OOMKilled":
                anomalies.append(Anomaly(
                    id=str(uuid.uuid4()),
                    severity=Severity.CRITICAL,
                    type=AnomalyType.OOM_KILLED,
                    resource=name,
                    namespace=namespace,
                    message=f"Container '{container_name}' was OOMKilled (Out of Memory). Restart count: {restart_count}",
                    raw_status=terminated_reason,
                    restart_count=restart_count,
                ))

            elif waiting_reason in ("ContainerCreating", "PodInitializing"):
                anomalies.append(Anomaly(
                    id=str(uuid.uuid4()),
                    severity=Severity.WARNING,
                    type=AnomalyType.CONTAINER_STUCK,
                    resource=name,
                    namespace=namespace,
                    message=f"Container '{container_name}' stuck in {waiting_reason}",
                    raw_status=waiting_reason,
                ))

            elif restart_count > 5 and not waiting_reason:
                anomalies.append(Anomaly(
                    id=str(uuid.uuid4()),
                    severity=Severity.WARNING,
                    type=AnomalyType.HIGH_RESTART_COUNT,
                    resource=name,
                    namespace=namespace,
                    message=f"Container '{container_name}' has high restart count: {restart_count}",
                    raw_status="Running",
                    restart_count=restart_count,
                ))

        # Evicted pods
        if pod.get("status", {}).get("reason") == "Evicted":
            anomalies.append(Anomaly(
                id=str(uuid.uuid4()),
                severity=Severity.WARNING,
                type=AnomalyType.EVICTED_POD,
                resource=name,
                namespace=namespace,
                message=f"Pod was evicted. {pod.get('status', {}).get('message', '')}",
                raw_status="Evicted",
            ))

        # Pending pods
        elif phase == "Pending":
            already_flagged = any(a.resource == name and a.namespace == namespace for a in anomalies)
            if not already_flagged:
                reason = ""
                for cond in pod.get("status", {}).get("conditions", []):
                    if cond.get("type") == "PodScheduled" and cond.get("status") == "False":
                        reason = cond.get("message", "Unknown scheduling failure")
                anomalies.append(Anomaly(
                    id=str(uuid.uuid4()),
                    severity=Severity.WARNING,
                    type=AnomalyType.POD_PENDING,
                    resource=name,
                    namespace=namespace,
                    message=f"Pod stuck in Pending state. {reason}",
                    raw_status="Pending",
                ))

        elif phase == "Failed":
            anomalies.append(Anomaly(
                id=str(uuid.uuid4()),
                severity=Severity.CRITICAL,
                type=AnomalyType.UNKNOWN,
                resource=name,
                namespace=namespace,
                message=f"Pod in Failed phase. {pod.get('status', {}).get('message', '')}",
                raw_status="Failed",
            ))

    return anomalies


def detect_node_anomalies(nodes_data: dict) -> List[Anomaly]:
    """Detect anomalies from node JSON data."""
    anomalies = []

    for node in nodes_data.get("items", []):
        name = node.get("metadata", {}).get("name", "unknown")

        for cond in node.get("status", {}).get("conditions", []):
            cond_type = cond.get("type", "")
            cond_status = cond.get("status", "")

            if cond_type == "Ready" and cond_status != "True":
                anomalies.append(Anomaly(
                    id=str(uuid.uuid4()),
                    severity=Severity.CRITICAL,
                    type=AnomalyType.NODE_NOT_READY,
                    resource=name,
                    namespace="cluster",
                    message=f"Node is NotReady. Reason: {cond.get('reason', 'N/A')}. {cond.get('message', '')}",
                    raw_status="NotReady",
                ))

            elif cond_type in ("MemoryPressure", "DiskPressure", "PIDPressure") and cond_status == "True":
                anomalies.append(Anomaly(
                    id=str(uuid.uuid4()),
                    severity=Severity.WARNING,
                    type=AnomalyType.RESOURCE_PRESSURE,
                    resource=name,
                    namespace="cluster",
                    message=f"Node has {cond_type}. Reason: {cond.get('reason', 'N/A')}",
                    raw_status=cond_type,
                ))

    return anomalies


def detect_deployment_anomalies(deployments_data: dict) -> List[Anomaly]:
    """Detect anomalies from deployment JSON data."""
    anomalies = []

    for dep in deployments_data.get("items", []):
        namespace = dep.get("metadata", {}).get("namespace", "unknown")
        name = dep.get("metadata", {}).get("name", "unknown")

        desired = dep.get("spec", {}).get("replicas", 0)
        available = dep.get("status", {}).get("availableReplicas") or 0
        ready = dep.get("status", {}).get("readyReplicas") or 0

        if desired is None or desired == 0:
            continue

        if available == 0:
            anomalies.append(Anomaly(
                id=str(uuid.uuid4()),
                severity=Severity.CRITICAL,
                type=AnomalyType.DEPLOYMENT_DEGRADED,
                resource=name,
                namespace=namespace,
                message=f"Deployment fully unavailable: 0/{desired} replicas available",
                raw_status="Unavailable",
            ))
        elif available < desired:
            anomalies.append(Anomaly(
                id=str(uuid.uuid4()),
                severity=Severity.WARNING,
                type=AnomalyType.DEPLOYMENT_DEGRADED,
                resource=name,
                namespace=namespace,
                message=f"Deployment degraded: {available}/{desired} available, {ready}/{desired} ready",
                raw_status="Degraded",
            ))

    return anomalies


def detect_pvc_anomalies(pvcs_data: dict) -> List[Anomaly]:
    """Detect anomalies from PersistentVolumeClaim JSON data."""
    anomalies = []

    for pvc in pvcs_data.get("items", []):
        namespace = pvc.get("metadata", {}).get("namespace", "unknown")
        name = pvc.get("metadata", {}).get("name", "unknown")
        phase = pvc.get("status", {}).get("phase", "")

        if phase == "Pending":
            storage = pvc.get("spec", {}).get("resources", {}).get("requests", {}).get("storage", "unknown")
            storage_class = pvc.get("spec", {}).get("storageClassName", "default")
            anomalies.append(Anomaly(
                id=str(uuid.uuid4()),
                severity=Severity.WARNING,
                type=AnomalyType.PVC_PENDING,
                resource=name,
                namespace=namespace,
                message=f"PVC stuck in Pending state. Requested: {storage}, StorageClass: {storage_class}",
                raw_status="Pending",
            ))
        elif phase not in ("Bound", ""):
            anomalies.append(Anomaly(
                id=str(uuid.uuid4()),
                severity=Severity.CRITICAL,
                type=AnomalyType.PVC_UNBOUND,
                resource=name,
                namespace=namespace,
                message=f"PVC is not Bound (phase: {phase}). Pods using this PVC may fail to start.",
                raw_status=phase,
            ))

    return anomalies


def detect_job_anomalies(jobs_data: dict) -> List[Anomaly]:
    """Detect anomalies from Job JSON data."""
    anomalies = []

    for job in jobs_data.get("items", []):
        namespace = job.get("metadata", {}).get("namespace", "unknown")
        name = job.get("metadata", {}).get("name", "unknown")

        failed = job.get("status", {}).get("failed", 0) or 0
        conditions = job.get("status", {}).get("conditions", [])
        backoff_limit = job.get("spec", {}).get("backoffLimit", 6)

        for cond in conditions:
            if cond.get("type") == "Failed" and cond.get("status") == "True":
                reason = cond.get("reason", "BackoffLimitExceeded")
                anomalies.append(Anomaly(
                    id=str(uuid.uuid4()),
                    severity=Severity.CRITICAL,
                    type=AnomalyType.JOB_FAILED,
                    resource=name,
                    namespace=namespace,
                    message=f"Job failed after {failed} attempt(s). Reason: {reason}. BackoffLimit: {backoff_limit}",
                    raw_status="Failed",
                ))
                break

    return anomalies


def run_detection() -> List[Anomaly]:
    """Run full anomaly detection across the cluster. Returns anomalies sorted by severity."""
    all_anomalies: List[Anomaly] = []

    pods_data = get_pods_json()
    if pods_data:
        all_anomalies.extend(detect_pod_anomalies(pods_data))

    nodes_data = get_nodes_json()
    if nodes_data:
        all_anomalies.extend(detect_node_anomalies(nodes_data))

    deployments_data = get_deployments_json()
    if deployments_data:
        all_anomalies.extend(detect_deployment_anomalies(deployments_data))

    pvcs_data = get_pvcs_json()
    if pvcs_data:
        all_anomalies.extend(detect_pvc_anomalies(pvcs_data))

    jobs_data = get_jobs_json()
    if jobs_data:
        all_anomalies.extend(detect_job_anomalies(jobs_data))

    severity_order = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}
    all_anomalies.sort(key=lambda a: severity_order[a.severity])

    return all_anomalies


# ---------------------------------------------------------------------------
# Docker anomaly detection (independent of Kubernetes)
# ---------------------------------------------------------------------------

def detect_docker_anomalies(containers: list[dict]) -> List[Anomaly]:
    """Detect anomalies from Docker container data returned by docker ps -a --format json."""
    anomalies = []

    for c in containers:
        name = c.get("Names", "unknown")
        image = c.get("Image", "unknown")
        status = c.get("Status", "")
        state = c.get("State", "").lower()

        if state == "exited":
            exit_code = ""
            if "Exited" in status:
                try:
                    exit_code = status.split("(")[1].split(")")[0]
                except (IndexError, ValueError):
                    exit_code = "unknown"
            severity = Severity.CRITICAL if exit_code not in ("0", "") else Severity.INFO
            if exit_code != "0":
                anomalies.append(Anomaly(
                    id=str(uuid.uuid4()),
                    severity=severity,
                    type=AnomalyType.UNKNOWN,
                    resource=name,
                    namespace="docker",
                    message=f"Container exited with code {exit_code}. Image: {image}. Status: {status}",
                    raw_status=status,
                ))

        elif state == "restarting":
            anomalies.append(Anomaly(
                id=str(uuid.uuid4()),
                severity=Severity.CRITICAL,
                type=AnomalyType.CRASH_LOOP_BACK_OFF,
                resource=name,
                namespace="docker",
                message=f"Container is restarting continuously. Image: {image}. Status: {status}",
                raw_status=status,
            ))

        elif state == "dead":
            anomalies.append(Anomaly(
                id=str(uuid.uuid4()),
                severity=Severity.CRITICAL,
                type=AnomalyType.UNKNOWN,
                resource=name,
                namespace="docker",
                message=f"Container is in dead state. Image: {image}. Manual removal required.",
                raw_status="dead",
            ))

        elif state == "paused":
            anomalies.append(Anomaly(
                id=str(uuid.uuid4()),
                severity=Severity.WARNING,
                type=AnomalyType.CONTAINER_STUCK,
                resource=name,
                namespace="docker",
                message=f"Container is paused. Image: {image}.",
                raw_status="paused",
            ))

    return anomalies


def run_docker_detection() -> List[Anomaly]:
    """Run Docker anomaly detection. Returns empty list if Docker is unavailable."""
    if not is_docker_available():
        return []
    containers = get_all_containers_json()
    anomalies = detect_docker_anomalies(containers)
    severity_order = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}
    anomalies.sort(key=lambda a: severity_order[a.severity])
    return anomalies
