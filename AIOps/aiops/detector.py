import uuid
from typing import List
from .models import Anomaly, Severity, AnomalyType
from .collector import get_pods_json, get_nodes_json, get_deployments_json


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

    severity_order = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}
    all_anomalies.sort(key=lambda a: severity_order[a.severity])

    return all_anomalies
