# AIOps — AI-Powered Kubernetes Incident Response

Detect anomalies in a Kubernetes cluster, explain root causes with AI, generate remediation commands, and produce SOP runbooks — all from a single CLI backed by **Gemma 4 running locally via Ollama**.

```
python main.py scan --ai
```

---

## How it works

```
main.py                 ← entry point
AIOps/aiops/
  cli.py                ← Typer CLI (scan, analyze, fix, sop, watch, status)
  collector.py          ← kubectl wrappers
  detector.py           ← rule-based anomaly detection (no LLM)
  agent.py              ← LangGraph ReAct agent + Gemma 4 calls
  sop.py                ← SOP Markdown generation
  models.py             ← Pydantic data models
  prompts.py            ← LLM prompt templates
AIOps/docs/             ← generated SOP runbooks land here
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | `python --version` |
| kubectl | configured and pointing at your cluster |
| [Ollama](https://ollama.com) | running locally |
| gemma4 model | `ollama pull gemma4` |
| Kind (optional) | for the demo cluster below |

---

## Step-by-step setup

### 1. Clone the repo

```bash
git clone https://github.com/ShwetaBharambe21/AIOps.git
cd AIOps
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r AIOps/requirements.txt
```

### 4. Start Ollama and pull the model

```bash
# Make sure Ollama is running (it starts automatically on macOS after install)
ollama pull gemma4
```

### 5. Point kubectl at a cluster

If you don't have a cluster, spin up a local one with Kind:

```bash
kind create cluster --name aiops-demo
```

Verify it is reachable:

```bash
kubectl get nodes
```

### 6. (Optional) Deploy broken workloads for the demo

```bash
# ImagePullBackOff
kubectl create deployment bad-img --image=thisimage-does-not-exist:latest

# CrashLoopBackOff
kubectl create deployment broken-app --image=busybox -- /bin/sh -c "exit 1"
```

Wait ~30 seconds for the pods to enter their failed states.

---

## Running the CLI

All commands are run from the repo root:

```bash
cd AIOps   # subfolder that contains main.py
```

### Cluster health overview

```bash
python main.py status
```

### Scan for anomalies (fast, no LLM)

```bash
python main.py scan

# Limit to one namespace
python main.py scan --namespace default

# JSON output
python main.py scan --output json
```

### Scan + AI root-cause analysis

```bash
python main.py scan --ai
```

### Full AI root-cause analysis

```bash
# Fast path — pre-collects data, then queries Gemma 4
python main.py analyze

# Deep mode — ReAct agent calls kubectl tools live
python main.py analyze --deep
```

### Generate a fix for a specific pod

```bash
python main.py fix <pod-name> --namespace default
```

### Generate SOP runbooks

```bash
# SOPs for every anomaly type currently detected
python main.py sop

# SOP for a specific type
python main.py sop --type CrashLoopBackOff

# Custom output directory
python main.py sop --type ImagePullBackOff --docs-dir ./runbooks
```

Valid `--type` values: `CrashLoopBackOff`, `OOMKilled`, `ImagePullBackOff`, `PodPending`,
`HighRestartCount`, `DeploymentDegraded`, `NodeNotReady`, `ContainerStuck`,
`ResourcePressure`, `FailedScheduling`, `EvictedPod`, `Unknown`

### Continuous monitoring

```bash
# Poll every 60 s (default)
python main.py watch

# Poll every 30 s with AI analysis on new anomalies
python main.py watch --interval 30 --ai
```

---

## Detected anomaly types

| Type | Severity |
|---|---|
| `CrashLoopBackOff` | CRITICAL |
| `OOMKilled` | CRITICAL |
| `ImagePullBackOff` | CRITICAL |
| `NodeNotReady` | CRITICAL |
| `DeploymentDegraded` | CRITICAL / WARNING |
| `PodPending` | WARNING |
| `HighRestartCount` | WARNING |
| `ContainerStuck` | WARNING |
| `ResourcePressure` | WARNING |
| `EvictedPod` | WARNING |

---

## Generated SOPs

Runbooks are saved to `AIOps/docs/` as individual Markdown files with an index `README.md`:

```
AIOps/docs/
  README.md
  SOP-resolving-crashloopbackoff-in-kubernetes-pods.md
  SOP-fixing-imagepullbackoff-errors.md
  SOP-handling-oomkilled-out-of-memory-pods.md
  ...
```

Each SOP includes: Overview · Symptoms · Detection · Root Cause · Step-by-Step Resolution · Rollback · Prevention · Escalation.

---

## AI stack

- **Model**: `gemma4` via Ollama — 100% local, no cloud API
- **Framework**: LangChain + LangGraph `create_react_agent`
- **Agent tools**: live `kubectl` calls (pods, logs, events, describe, metrics)
- **Fast path**: direct LLM invoke from pre-collected data (skips agent loop)
