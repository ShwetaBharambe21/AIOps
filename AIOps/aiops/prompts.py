SYSTEM_PROMPT = """You are a senior Kubernetes SRE (Site Reliability Engineer) and DevOps expert.
You specialize in root cause analysis, incident response, and operational excellence.

Your analysis style:
- Be precise and factual — only reference what is in the data provided
- Prioritize by business impact and severity
- Provide actionable kubectl commands and YAML fixes
- Be concise but thorough
- Never hallucinate or invent problems not supported by the data
"""


RCA_PROMPT_TEMPLATE = """Analyze the following Kubernetes cluster data and provide a comprehensive root cause analysis.

## Cluster: {cluster_name}

## Detected Anomalies:
{anomalies_text}

## Recent Warning Events:
{events_text}

## Pod Logs (for affected pods):
{logs_text}

---

Please provide your analysis in the following structured format:

## Root Cause Analysis

For each anomaly, provide:
### [SEVERITY] Anomaly: <name>
- **Root Cause**: What is actually causing this issue
- **Evidence**: Specific data points that support this diagnosis
- **Fix Commands**: Ready-to-run kubectl commands to resolve

## Summary
Brief prioritized action plan — what to fix first and why.

## Risk Assessment
What could happen if these issues are left unresolved.
"""


SOLUTION_PROMPT_TEMPLATE = """You are providing specific remediation steps for a Kubernetes issue.

## Issue Details
- **Type**: {anomaly_type}
- **Resource**: {namespace}/{resource}
- **Severity**: {severity}
- **Problem**: {message}

## Pod Description:
{pod_description}

## Recent Logs:
{logs}

---

Provide a focused remediation plan:

### 1. Immediate Fix
What kubectl commands to run RIGHT NOW to restore service.

### 2. Root Fix
What configuration or code change prevents recurrence.

### 3. Verification
How to confirm the fix worked.

### 4. Rollback
How to undo the fix if it makes things worse.

Format all kubectl commands as fenced code blocks.
"""


SOP_PROMPT_TEMPLATE = """Create a comprehensive Standard Operating Procedure (SOP) document for the following Kubernetes issue.

## Incident Summary
- **Anomaly Type**: {anomaly_type}
- **Severity**: {severity}
- **Root Cause**: {root_cause}
- **Resolution**: {solution}

---

Generate a production-ready SOP in Markdown format using this exact structure:

# SOP: {sop_title}

## Overview
Brief description of the issue and when this SOP applies.

## Symptoms
Bullet list of observable symptoms that indicate this issue.

## Detection
How to detect this issue:
- Automated alerts to configure
- kubectl commands to check
- Log patterns to look for

## Root Cause Analysis
Typical root causes for this issue type.

## Prerequisites
What access and tools are needed before attempting the fix.

## Step-by-Step Resolution

### Step 1: Triage
...

### Step 2: Identify Root Cause
...

### Step 3: Apply Fix
...

### Step 4: Verify Resolution
...

## Rollback Procedure
Steps to safely undo changes if the fix causes problems.

## Prevention
- Configuration best practices
- Resource limits and requests guidance
- Monitoring and alerting recommendations

## Escalation
When to escalate and to whom.

## References
- Related Kubernetes documentation links
- Related SOPs
"""


FULL_CLUSTER_ANALYSIS_PROMPT = """You are analyzing a Kubernetes cluster for operational issues.

## Cluster Context
- **Name**: {cluster_name}
- **Scan Time**: {timestamp}

## All Pods Status:
```
{pods_text}
```

## Node Status:
```
{nodes_text}
```

## Deployments:
```
{deployments_text}
```

## Recent Warning Events:
```
{events_text}
```

## Resource Metrics:
```
{metrics_text}
```

---

Provide a complete AIOps analysis:

## Anomalies Detected
List ALL detected issues with severity [CRITICAL/WARNING/INFO].

## Root Cause Analysis
For each critical/warning anomaly, explain the root cause.

## Recommended Fixes
Specific, runnable kubectl commands and YAML changes.

## Cluster Health Score
Rate cluster health 0-100 with brief justification.

## Action Plan
Prioritized list — what to fix immediately vs. what can wait.
"""
