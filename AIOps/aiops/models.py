from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class AnomalyType(str, Enum):
    CRASH_LOOP_BACK_OFF = "CrashLoopBackOff"
    OOM_KILLED = "OOMKilled"
    IMAGE_PULL_BACK_OFF = "ImagePullBackOff"
    POD_PENDING = "PodPending"
    HIGH_RESTART_COUNT = "HighRestartCount"
    DEPLOYMENT_DEGRADED = "DeploymentDegraded"
    NODE_NOT_READY = "NodeNotReady"
    CONTAINER_STUCK = "ContainerStuck"
    RESOURCE_PRESSURE = "ResourcePressure"
    FAILED_SCHEDULING = "FailedScheduling"
    EVICTED_POD = "EvictedPod"
    UNKNOWN = "Unknown"


class Anomaly(BaseModel):
    id: str
    severity: Severity
    type: AnomalyType
    resource: str
    namespace: str
    message: str
    raw_status: Optional[str] = None
    restart_count: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.now)

    def display_title(self) -> str:
        return f"[{self.severity.value}] {self.type.value} in {self.namespace}/{self.resource}"


class RootCause(BaseModel):
    anomaly_id: str
    summary: str
    details: str
    confidence: str  # HIGH, MEDIUM, LOW


class Solution(BaseModel):
    anomaly_id: str
    description: str
    commands: List[str]
    config_changes: Optional[str] = None
    priority: int = 1  # 1 = highest


class ClusterAnalysis(BaseModel):
    cluster_name: str
    timestamp: datetime = Field(default_factory=datetime.now)
    anomalies: List[Anomaly] = []
    root_causes: List[RootCause] = []
    solutions: List[Solution] = []
    raw_llm_analysis: Optional[str] = None

    def has_critical_issues(self) -> bool:
        return any(a.severity == Severity.CRITICAL for a in self.anomalies)


class SOPDocument(BaseModel):
    title: str
    anomaly_type: str
    content: str
    generated_at: datetime = Field(default_factory=datetime.now)
    file_path: Optional[str] = None
