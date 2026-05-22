from typing import List
from datetime import datetime
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from .collector import (
    get_pods, get_events, get_pod_logs, get_nodes,
    get_deployments, get_resource_metrics, describe_pod,
)
from .models import Anomaly
from .prompts import SYSTEM_PROMPT, RCA_PROMPT_TEMPLATE, SOLUTION_PROMPT_TEMPLATE


def _build_llm(temperature: float = 0.3) -> ChatOllama:
    return ChatOllama(model="gemma4", temperature=temperature)


# --------------------------------------------------------------------------
# LangChain tools exposed to the ReAct agent
# --------------------------------------------------------------------------

@tool
def kubernetes_get_all_pods() -> str:
    """Get all pods across all namespaces with their current status."""
    return get_pods()


@tool
def kubernetes_get_events() -> str:
    """Get recent warning events from the Kubernetes cluster."""
    return get_events()


@tool
def kubernetes_get_nodes() -> str:
    """Get status of all Kubernetes nodes."""
    return get_nodes()


@tool
def kubernetes_get_deployments() -> str:
    """Get status of all Kubernetes deployments across all namespaces."""
    return get_deployments()


@tool
def kubernetes_get_resource_metrics() -> str:
    """Get CPU and memory usage metrics for nodes and pods (requires metrics-server)."""
    return get_resource_metrics()


@tool
def kubernetes_get_pod_logs(pod_name: str, namespace: str) -> str:
    """Get recent logs from a specific Kubernetes pod.

    Args:
        pod_name: Name of the pod.
        namespace: Kubernetes namespace the pod lives in.
    """
    return get_pod_logs(pod_name, namespace)


@tool
def kubernetes_describe_pod(pod_name: str, namespace: str) -> str:
    """Get detailed description of a Kubernetes pod including events and conditions.

    Args:
        pod_name: Name of the pod.
        namespace: Kubernetes namespace the pod lives in.
    """
    return describe_pod(pod_name, namespace)


K8S_TOOLS = [
    kubernetes_get_all_pods,
    kubernetes_get_events,
    kubernetes_get_nodes,
    kubernetes_get_deployments,
    kubernetes_get_resource_metrics,
    kubernetes_get_pod_logs,
    kubernetes_describe_pod,
]


# --------------------------------------------------------------------------
# Public analysis functions
# --------------------------------------------------------------------------

def run_full_analysis(cluster_name: str) -> dict:
    """Run comprehensive cluster health analysis using a ReAct agent with k8s tools."""
    llm = _build_llm()
    agent = create_react_agent(llm, K8S_TOOLS, prompt=SYSTEM_PROMPT)

    user_message = f"""Perform a comprehensive health check of Kubernetes cluster '{cluster_name}'.

Use ALL available tools to:
1. Check all pod statuses and identify any issues
2. Check node health
3. Check deployment statuses
4. Look at recent warning events
5. Get logs from any problematic pods
6. Check resource metrics if available

Then provide your full analysis with these sections:

## Anomalies Detected
List all issues found with severity [CRITICAL/WARNING/INFO].

## Root Cause Analysis
For each issue, explain the likely root cause with evidence.

## Recommended Fixes
Specific kubectl commands to resolve each issue.

## Cluster Health Score
Rate cluster health 0-100 with brief justification.

## Priority Action Plan
What to fix immediately vs. what can wait.
"""

    response = agent.invoke({"messages": [{"role": "user", "content": user_message}]})
    return {
        "analysis": response["messages"][-1].content,
        "timestamp": datetime.now().isoformat(),
        "cluster": cluster_name,
    }


def generate_rca_from_data(
    cluster_name: str,
    anomalies: List[Anomaly],
    events_text: str,
    logs_by_pod: dict,
) -> str:
    """Generate root cause analysis from pre-collected data (no agent loop)."""
    llm = _build_llm()

    anomalies_text = "\n".join(
        f"[{a.severity.value}] {a.type.value} | {a.namespace}/{a.resource}\n  → {a.message}"
        + (f"\n  → Restart count: {a.restart_count}" if a.restart_count else "")
        for a in anomalies
    ) or "No anomalies pre-detected."

    logs_text = ""
    for pod_key, logs in logs_by_pod.items():
        logs_text += f"\n--- {pod_key} ---\n{logs[:2000]}\n"

    prompt = RCA_PROMPT_TEMPLATE.format(
        cluster_name=cluster_name,
        anomalies_text=anomalies_text,
        events_text=(events_text or "No warning events")[:3000],
        logs_text=(logs_text or "No logs available")[:4000],
    )

    response = llm.invoke([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ])
    return response.content


def generate_solution(anomaly: Anomaly, pod_description: str = "", logs: str = "") -> str:
    """Generate a specific remediation plan for a single anomaly."""
    llm = _build_llm()

    prompt = SOLUTION_PROMPT_TEMPLATE.format(
        anomaly_type=anomaly.type.value,
        namespace=anomaly.namespace,
        resource=anomaly.resource,
        severity=anomaly.severity.value,
        message=anomaly.message,
        pod_description=(pod_description or "Not available")[:2000],
        logs=(logs or "Not available")[:2000],
    )

    response = llm.invoke([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ])
    return response.content
