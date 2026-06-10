# AIOps CLI

> AI-powered anomaly detection, root cause analysis, and incident response for **Docker** and **Kubernetes** — backed by **Gemma 4** running 100% locally via **Ollama**.

```
python main.py chat
You> what's wrong with my cluster?
You> scan docker containers
You> generate an incident report
```

---

## What it does

| Capability | Docker | Kubernetes |
|---|:---:|:---:|
| Anomaly detection (rule-based, no LLM) | ✅ | ✅ |
| AI root cause analysis (Gemma 4) | ✅ | ✅ |
| Per-resource fix generation | ✅ | ✅ |
| Triage — critical issues only | — | ✅ |
| Full incident report (Markdown) | — | ✅ |
| SOP / runbook generation | — | ✅ |
| Continuous watch mode | — | ✅ |
| Deep ReAct agent investigation | — | ✅ |
| Conversational plain-English interface | ✅ | ✅ |

---

## Prerequisites

| Requirement | Install |
|---|---|
| Python 3.11+ | `python --version` |
| [Ollama](https://ollama.com) | running locally |
| Gemma 4 model | `ollama pull gemma4` |
| Docker Desktop | for Docker container monitoring |
| kubectl + cluster | minikube / Kind / any cluster for Kubernetes monitoring |

---

## Setup

```bash
git clone https://github.com/ShwetaBharambe21/AIOps.git
cd AIOps/AIOps

python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Start a local Kubernetes cluster if you don't have one:

```bash
# minikube
minikube start

# or Kind
kind create cluster --name aiops-demo
```

---

## Quick start

### Kubernetes

```bash
# Detect anomalies (fast, no LLM)
python main.py scan

# AI root cause analysis
python main.py analyze

# Triage — critical issues only
python main.py triage

# Fix a specific pod
python main.py fix <pod-name> --namespace default

# Full incident report saved to docs/
python main.py report

# Generate SOP runbooks
python main.py sop --all

# Continuous monitoring (Ctrl-C to stop)
python main.py watch --interval 30 --ai
```

### Docker

```bash
# Detect anomalies across all containers
python main.py docker-scan

# Include stopped containers
python main.py docker-scan --all

# Show logs for unhealthy containers
python main.py docker-scan --logs

# AI fix for a specific container
python main.py docker-fix <container-name>
```

### Conversational chat (covers both)

```bash
python main.py chat
```

```
You> what's wrong with my cluster?
You> triage — show only critical
You> scan docker containers
You> why is the frontend pod crashing?
You> fix broken-app-7589c9dfd4-w6wnb
You> docker fix my-api-container
You> generate an incident report
You> generate sop documents
You> deep analyze everything
You> exit
```

---

## All commands

```
python main.py [COMMAND] [OPTIONS]
```

| Command | Target | Description |
|---|---|---|
| `scan` | Kubernetes | Rule-based anomaly scan across pods, nodes, deployments, PVCs, Jobs |
| `triage` | Kubernetes | CRITICAL issues only — instant, no LLM |
| `analyze` | Kubernetes | AI root cause analysis (fast path or deep ReAct agent) |
| `fix <pod>` | Kubernetes | AI remediation plan for a specific pod |
| `report` | Kubernetes | Full Markdown incident report with RCA + remediation plan |
| `sop` | Kubernetes | Generate SOP / runbook Markdown files |
| `watch` | Kubernetes | Continuous monitoring with optional AI alerts |
| `status` | Kubernetes | Quick cluster health overview |
| `docker-scan` | Docker | Rule-based anomaly scan across all containers |
| `docker-fix <name>` | Docker | AI remediation plan for a specific container |
| `chat` | Both | Plain-English conversational interface |

---

## Detected anomaly types

### Kubernetes

| Type | Severity | Trigger |
|---|---|---|
| `CrashLoopBackOff` | CRITICAL | Container restart loop |
| `OOMKilled` | CRITICAL | Container killed by out-of-memory |
| `ImagePullBackOff` | CRITICAL | Image cannot be pulled from registry |
| `NodeNotReady` | CRITICAL | Node not in Ready state |
| `DeploymentDegraded` | CRITICAL / WARNING | Available replicas < desired |
| `PVCUnbound` | CRITICAL | PersistentVolumeClaim not Bound |
| `JobFailed` | CRITICAL | Job exceeded backoff limit |
| `PodPending` | WARNING | Pod stuck in Pending state |
| `HighRestartCount` | WARNING | Restart count > 5 |
| `ContainerStuck` | WARNING | Stuck in ContainerCreating |
| `ResourcePressure` | WARNING | Node memory / disk / PID pressure |
| `EvictedPod` | WARNING | Pod was evicted |

### Docker

| State | Severity | Trigger |
|---|---|---|
| Exited (non-zero) | CRITICAL | Container exited with error code |
| Restarting | CRITICAL | Container in continuous restart loop |
| Dead | CRITICAL | Container in dead state |
| Paused | WARNING | Container is paused |

---

## Architecture

```
main.py
aiops/
  cli.py               ← Typer CLI — all commands
  chat.py              ← Plain-English conversational REPL
  collector.py         ← kubectl wrappers (pods, nodes, deployments, PVCs, Jobs, events, logs)
  docker_collector.py  ← Docker wrappers (ps, logs, stats, inspect)
  detector.py          ← Rule-based detection — Kubernetes + Docker (no LLM)
  agent.py             ← LangGraph ReAct agent + direct Gemma 4 calls
  sop.py               ← SOP Markdown generation + file writing
  models.py            ← Pydantic data models
  prompts.py           ← LLM prompt templates
docs/                  ← Generated SOPs + incident reports
```

### AI stack

- **Model** — `gemma4` via Ollama — 100% local, zero cloud API calls
- **Framework** — LangChain + LangGraph `create_react_agent`
- **Agent tools** — 11 live tools: 7 Kubernetes (`kubectl` calls) + 4 Docker (`docker` calls)
- **Fast path** — direct `llm.invoke()` from pre-collected data (no agent loop overhead)

---

## Demo: simulate failures

### Kubernetes

```bash
# CrashLoopBackOff
kubectl create deployment crasher --image=busybox -- /bin/sh -c "exit 1"

# ImagePullBackOff
kubectl create deployment bad-image --image=thisimage-does-not-exist:nope

# Wait ~30 seconds, then:
python main.py scan
python main.py triage
python main.py analyze
python main.py report
```

### Docker

```bash
# Exited with error
docker run --name test-crash busybox /bin/sh -c "exit 1"

# Then:
python main.py docker-scan --all
python main.py docker-fix test-crash
```

---

## Generated output

```
docs/
  README.md                                          ← SOP index
  incident-report-2026-06-11-10-30.md               ← Full incident report
  SOP-resolving-crashloopbackoff-in-kubernetes-pods.md
  SOP-fixing-imagepullbackoff-errors.md
  SOP-handling-oomkilled-out-of-memory-pods.md
  SOP-recovering-degraded-kubernetes-deployments.md
  SOP-resolving-pending-pods-in-kubernetes.md
  ...
```

Each SOP contains: Overview · Symptoms · Detection · Root Cause · Step-by-Step Resolution · Rollback · Prevention · Escalation.

Each incident report contains: Executive Summary · Health Score · Anomaly Inventory · Per-issue RCA with evidence · P0/P1/P2 Remediation Plan · Risk Assessment.
