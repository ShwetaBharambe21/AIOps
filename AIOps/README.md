# AIOps CLI

AI-powered anomaly detection, root cause analysis, and incident response for **Docker containers** and **Kubernetes clusters** — backed by **Gemma 4** running locally via **Ollama**. No cloud API required.

---

## Features

| Feature | Docker | Kubernetes |
|---|:---:|:---:|
| Rule-based anomaly detection | ✅ | ✅ |
| AI root cause analysis (Gemma 4) | ✅ | ✅ |
| Per-resource fix generation | ✅ | ✅ |
| Triage — critical issues only | — | ✅ |
| Full incident report (Markdown) | — | ✅ |
| SOP / runbook generation | — | ✅ |
| Continuous watch mode | — | ✅ |
| Deep ReAct agent investigation | — | ✅ |
| Conversational plain-English chat | ✅ | ✅ |

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | `python --version` |
| [Ollama](https://ollama.com) | running locally |
| Gemma 4 model | `ollama pull gemma4` |
| Docker Desktop | for `docker-scan` / `docker-fix` |
| kubectl | configured and pointing at your cluster |
| minikube / Kind (optional) | for a local Kubernetes cluster |

---

## Installation

```bash
cd AIOps
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create a local cluster if needed:

```bash
# minikube
minikube start

# or Kind
kind create cluster --name aiops-demo
```

---

## Usage

```
python main.py [COMMAND] [OPTIONS]
```

---

## Kubernetes commands

### `scan` — Detect anomalies

Fast rule-based scan with no LLM latency. Covers pods, nodes, deployments, PVCs, and Jobs.

```bash
# Scan all namespaces
python main.py scan

# Limit to one namespace
python main.py scan --namespace production

# Follow scan with AI root cause analysis
python main.py scan --ai

# JSON output (pipe-friendly)
python main.py scan --output json
```

---

### `triage` — Critical issues only

Shows only CRITICAL anomalies. No LLM, instant output. Use this first during an incident.

```bash
python main.py triage
python main.py triage --namespace production
```

---

### `analyze` — AI root cause analysis

Collects cluster data and asks Gemma 4 to explain root causes, with evidence and fix commands.

```bash
# Fast path — pre-collects data, single LLM call
python main.py analyze

# Focus on one namespace
python main.py analyze kube-system

# Deep mode — ReAct agent calls live kubectl tools itself
python main.py analyze --deep
```

**Fast path** collects pods, events, and logs, then sends everything to Gemma 4 in one call.  
**Deep mode** spawns a ReAct agent with 7 live kubectl tools — it investigates the cluster autonomously.

---

### `fix` — Per-pod remediation

Fetches pod description + logs, then asks Gemma 4 for a targeted fix.

```bash
python main.py fix <pod-name> --namespace default
```

Output includes: Immediate fix · Root fix · Verification steps · Rollback procedure.

---

### `report` — Full incident report

Generates a complete Markdown incident report saved to `docs/`.

```bash
# Auto-named: docs/incident-report-<timestamp>.md
python main.py report

# Custom output file
python main.py report --out /tmp/my-report.md

# Custom docs directory
python main.py report --docs-dir ./reports
```

Report sections: Executive Summary · Health Score · Anomaly Inventory table · Per-issue RCA with evidence · P0 / P1 / P2 Remediation Plan · Risk Assessment.

---

### `sop` — Generate SOP runbooks

AI-generated Standard Operating Procedure documents saved as Markdown files.

```bash
# SOPs for all anomaly types currently detected in the cluster
python main.py sop --all

# SOP for a specific anomaly type
python main.py sop --type CrashLoopBackOff
python main.py sop --type ImagePullBackOff
python main.py sop --type OOMKilled
python main.py sop --type PVCUnbound

# Custom output directory
python main.py sop --all --docs-dir ./runbooks
```

Valid `--type` values: `CrashLoopBackOff` · `OOMKilled` · `ImagePullBackOff` · `PodPending` · `HighRestartCount` · `DeploymentDegraded` · `NodeNotReady` · `ContainerStuck` · `ResourcePressure` · `FailedScheduling` · `EvictedPod` · `PVCUnbound` · `PVCPending` · `JobFailed`

Each SOP contains: Overview · Symptoms · Detection commands · Root Cause · Step-by-Step Resolution · Rollback · Prevention · Escalation.

---

### `watch` — Continuous monitoring

Polls the cluster on an interval and alerts when new anomalies appear.

```bash
# Poll every 60 seconds (default)
python main.py watch

# Poll every 30 seconds with AI analysis on new anomalies
python main.py watch --interval 30 --ai

# Watch a specific namespace
python main.py watch --namespace production --interval 15
```

Press `Ctrl-C` to stop.

---

### `status` — Cluster health overview

Quick summary: all pods, nodes, and a health verdict (HEALTHY / DEGRADED / CRITICAL).

```bash
python main.py status
```

---

## Docker commands

### `docker-scan` — Detect container anomalies

Rule-based scan across all Docker containers. No LLM required.

```bash
# Scan running containers
python main.py docker-scan

# Include stopped / exited containers
python main.py docker-scan --all

# Show logs for anomalous containers
python main.py docker-scan --all --logs
```

Detected states:

| State | Severity | Description |
|---|---|---|
| Exited (non-zero code) | CRITICAL | Container crashed with an error |
| Restarting | CRITICAL | Container in a continuous restart loop |
| Dead | CRITICAL | Container in dead state, requires manual cleanup |
| Paused | WARNING | Container is paused and not serving traffic |

---

### `docker-fix` — AI remediation for a container

Fetches container logs, then asks Gemma 4 for a targeted fix.

```bash
python main.py docker-fix <container-name>
python main.py docker-fix my-api
python main.py docker-fix laravel-queue
```

Output includes: Immediate fix · Root fix · Verification steps · Rollback procedure.

---

## Conversational chat (covers both Docker and Kubernetes)

The easiest way to use AIOps. Type in plain English — Gemma 4 figures out the intent and runs the right command.

```bash
python main.py chat
```

Example session:

```
You> what's wrong with my cluster?
You> triage — show me only the critical issues
You> why is the frontend pod crashing?
You> fix broken-app-7589c9dfd4-w6wnb
You> scan docker containers
You> docker fix my-api-container
You> generate an incident report
You> show me a health overview
You> generate sop documents
You> deep analyze everything
You> watch the cluster
You> exit
```

Conversation history is maintained across turns so follow-up questions work naturally.

---

## Detected anomaly types

### Kubernetes

| Type | Severity | Trigger |
|---|---|---|
| `CrashLoopBackOff` | CRITICAL | Container in a restart loop |
| `OOMKilled` | CRITICAL | Container killed by out-of-memory |
| `ImagePullBackOff` | CRITICAL | Image cannot be pulled from registry |
| `NodeNotReady` | CRITICAL | Node not in Ready state |
| `DeploymentDegraded` | CRITICAL / WARNING | Available replicas < desired |
| `PVCUnbound` | CRITICAL | PersistentVolumeClaim not Bound |
| `JobFailed` | CRITICAL | Job exceeded its backoff limit |
| `PodPending` | WARNING | Pod stuck in Pending state |
| `HighRestartCount` | WARNING | Restart count > 5 |
| `ContainerStuck` | WARNING | Stuck in ContainerCreating |
| `ResourcePressure` | WARNING | Node memory / disk / PID pressure |
| `EvictedPod` | WARNING | Pod was evicted |
| `PVCPending` | WARNING | PVC stuck in Pending |

### Docker

| State | Severity | Trigger |
|---|---|---|
| Exited (non-zero) | CRITICAL | Container exited with a non-zero exit code |
| Restarting | CRITICAL | Container continuously restarting |
| Dead | CRITICAL | Container in dead state |
| Paused | WARNING | Container is paused |

---

## Architecture

```
main.py
aiops/
  cli.py               ← Typer CLI — all 11 commands
  chat.py              ← Plain-English conversational REPL (Docker + Kubernetes intents)
  collector.py         ← kubectl wrappers: pods, nodes, deployments, PVCs, Jobs, events, logs
  docker_collector.py  ← Docker wrappers: ps, logs, stats, inspect
  detector.py          ← Rule-based detection — Kubernetes + Docker anomalies (no LLM)
  agent.py             ← LangGraph ReAct agent + direct Gemma 4 calls (RCA, fix, report)
  sop.py               ← SOP Markdown generation + index README
  models.py            ← Pydantic models: Anomaly, Severity, AnomalyType, Solution, SOP
  prompts.py           ← LLM prompt templates: RCA, solution, SOP, incident report
docs/                  ← Generated SOPs + incident reports
```

### AI stack

| Component | Detail |
|---|---|
| Model | `gemma4` via Ollama — 100% local, no cloud API |
| Framework | LangChain + LangGraph `create_react_agent` |
| Kubernetes tools | 7 live `kubectl` tools (pods, logs, events, nodes, deployments, metrics, describe) |
| Docker tools | 4 live `docker` tools (ps, logs, stats, inspect) |
| Fast path | Direct `llm.invoke()` from pre-collected data — skips agent loop overhead |
| Deep path | Full ReAct loop — agent calls all 11 tools autonomously |

---

## Demo: simulate failures

### Kubernetes

```bash
# CrashLoopBackOff
kubectl create deployment crasher --image=busybox -- /bin/sh -c "exit 1"

# ImagePullBackOff
kubectl create deployment bad-image --image=thisimage-does-not-exist:nope

# Wait ~30 seconds for pods to enter failed states, then:
python main.py scan
python main.py triage
python main.py analyze
python main.py fix crasher-<hash> --namespace default
python main.py report
python main.py sop --type CrashLoopBackOff

# Clean up
kubectl delete deployment crasher bad-image
```

### Docker

```bash
# Container that exits with error
docker run --name test-crash busybox /bin/sh -c "exit 1"

# Then:
python main.py docker-scan --all --logs
python main.py docker-fix test-crash

# Clean up
docker rm test-crash
```

---

## Generated output files

```
docs/
  README.md                                             ← SOP index + quick reference table
  incident-report-2026-06-11-10-30.md                  ← Full incident report
  SOP-resolving-crashloopbackoff-in-kubernetes-pods.md
  SOP-fixing-imagepullbackoff-errors.md
  SOP-handling-oomkilled-out-of-memory-pods.md
  SOP-recovering-degraded-kubernetes-deployments.md
  SOP-resolving-pending-pods-in-kubernetes.md
  SOP-resolving-unbound-persistentvolumeclaims.md
  SOP-recovering-failed-kubernetes-jobs.md
  ...
```
