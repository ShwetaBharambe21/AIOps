# AIOps CLI

AI-powered Kubernetes anomaly detection and incident response CLI, backed by **Gemma 4** running locally via **Ollama**.

## Features

| Feature | Description |
|---------|-------------|
| **Conversational Chat** | Plain-English REPL — just describe what you need, Gemma 4 figures out the rest |
| **Anomaly Detection** | Rule-based scan across pods, nodes, deployments, PVCs, and Jobs — no LLM latency |
| **Triage Mode** | Instantly surface only CRITICAL issues for immediate action |
| **Root Cause Analysis** | Gemma 4 analyzes logs + events to explain *why* something broke |
| **Fix Generation** | Actionable `kubectl` commands tailored to each detected issue |
| **Incident Reports** | Full Markdown incident report with RCA, health score, and remediation plan |
| **SOP Documents** | AI-generated Markdown runbooks (with real per-issue solutions) saved to `docs/` |
| **Continuous Monitoring** | `watch` mode polls the cluster and alerts on new anomalies |
| **Deep Agent Mode** | ReAct agent uses live k8s tools to self-investigate the cluster |

## Prerequisites

- Python 3.11+
- [`kubectl`](https://kubernetes.io/docs/tasks/tools/) configured and pointing at your Kind cluster
- [Ollama](https://ollama.com) running locally with the `gemma4` model pulled

```bash
ollama pull gemma4
```

- A local Kind cluster (or any `kubectl`-reachable cluster)

```bash
kind create cluster --name aiops-demo
```

## Installation

```bash
cd demo/AIOps
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

```
python main.py [COMMAND] [OPTIONS]
```

### Commands

#### `chat` — Conversational assistant ⭐

The easiest way to use AIOps. Just type in plain English — no flags to remember.

```bash
python main.py chat
```

Then talk to it naturally:

```
You> what's wrong with my cluster?
You> triage — show me only the critical issues
You> why is the frontend pod crashing?
You> fix broken-app-7589c9dfd4-w6wnb
You> generate an incident report
You> show me a health overview
You> generate sop documents
You> deep analyze everything
You> exit
```

Gemma 4 parses your intent, picks the right action (scan / analyze / fix / status / sop / watch), and runs it. Conversation history is maintained across turns so follow-up questions work naturally.

---

#### `scan` — Detect anomalies

```bash
# Quick scan, table output
python main.py scan

# Scan a single namespace
python main.py scan --namespace kube-system

# Scan + AI root-cause analysis
python main.py scan --ai

# JSON output (pipe-friendly)
python main.py scan --output json
```

#### `analyze` — Deep root cause analysis

```bash
# RCA with pre-collected data (fast)
python main.py analyze

# Focus on one namespace
python main.py analyze kube-system

# Deep ReAct agent — agent calls live k8s tools itself
python main.py analyze --deep
```

#### `fix` — Per-pod remediation plan

```bash
python main.py fix my-broken-pod --namespace default
```

#### `sop` — Generate SOP documents

```bash
# Generate SOPs for all currently detected anomaly types
python main.py sop --all

# Generate SOP for a specific type
python main.py sop --type CrashLoopBackOff

# Custom output directory
python main.py sop --all --docs-dir ./runbooks
```

Generated files land in `docs/` (or `--docs-dir`). A `README.md` index is always created.

#### `triage` — Critical issues only

```bash
python main.py triage
python main.py triage --namespace production
```

Shows only CRITICAL anomalies — no warnings, no LLM latency. Use this as your first check during an incident.

#### `report` — Full incident report

```bash
# Generate report to docs/incident-report-<timestamp>.md
python main.py report

# Custom output file
python main.py report --out /tmp/my-report.md

# Custom docs directory
python main.py report --docs-dir ./reports
```

Generates a complete Markdown incident report containing: Executive Summary · Health Score · Anomaly Inventory · Per-issue RCA with evidence · Prioritised Remediation Plan (P0/P1/P2) · Risk Assessment. Powered by Gemma 4.

#### `watch` — Continuous monitoring

```bash
# Poll every 60 seconds (default)
python main.py watch

# Poll every 30 seconds with AI analysis on new anomalies
python main.py watch --interval 30 --ai
```

#### `status` — Quick cluster overview

```bash
python main.py status
```

## Detected Anomaly Types

| Type | Severity | Trigger |
|------|----------|---------|
| `CrashLoopBackOff` | CRITICAL | Container restart loop |
| `OOMKilled` | CRITICAL | Container killed by OOM |
| `ImagePullBackOff` | CRITICAL | Image cannot be pulled |
| `NodeNotReady` | CRITICAL | Node not in Ready state |
| `DeploymentDegraded` | CRITICAL/WARNING | Available replicas < desired |
| `PodPending` | WARNING | Pod stuck in Pending |
| `HighRestartCount` | WARNING | Restart count > 5 |
| `ContainerStuck` | WARNING | Stuck in ContainerCreating |
| `ResourcePressure` | WARNING | Node memory/disk/PID pressure |
| `EvictedPod` | WARNING | Pod was evicted |
| `PVCUnbound` | CRITICAL | PersistentVolumeClaim not Bound |
| `PVCPending` | WARNING | PersistentVolumeClaim stuck in Pending |
| `JobFailed` | CRITICAL | Kubernetes Job failed (backoff limit exceeded) |

## Architecture

```
main.py                 ← entry point
aiops/
  cli.py                ← Typer CLI commands (scan, triage, analyze, fix, report, sop, watch, chat, status)
  chat.py               ← conversational REPL (plain-English interface)
  collector.py          ← kubectl wrappers (pods, nodes, deployments, PVCs, Jobs, events, logs)
  detector.py           ← rule-based anomaly detection (no LLM) — pods, nodes, deployments, PVCs, Jobs
  agent.py              ← LangGraph ReAct agent + direct LLM calls (Gemma 4) — RCA, fix, report generation
  sop.py                ← SOP markdown generation + file writing
  models.py             ← Pydantic data models (Anomaly, Severity, AnomalyType, etc.)
  prompts.py            ← LLM prompt templates (RCA, solution, SOP, full incident report)
docs/                   ← generated SOP + incident report Markdown files land here
```

### AI Stack

- **Model**: `gemma4` via Ollama (100% local, no cloud API)
- **Framework**: LangChain + LangGraph `create_react_agent`
- **Agent tools**: live `kubectl` calls (pods, logs, events, describe, metrics)
- **Fast path**: direct LLM invoke from pre-collected data (no agent loop overhead)

## Example: Simulating a CrashLoopBackOff

```bash
# Deploy a broken workload
kubectl create deployment crasher \
  --image=busybox -- /bin/sh -c "exit 1"

# Wait ~30 seconds, then scan
python main.py scan --ai

# Generate the SOP
python main.py sop --type CrashLoopBackOff

# Get specific fix commands
python main.py fix crasher-<pod-hash> --namespace default
```

## Generated SOPs

SOPs are saved to `docs/` as individual Markdown files:

```
docs/
  README.md                                       ← index + quick reference
  SOP-resolving-crashloopbackoff-in-kubernetes-pods.md
  SOP-handling-oomkilled-out-of-memory-pods.md
  SOP-fixing-imagepullbackoff-errors.md
  ...
```

Each SOP contains: Overview · Symptoms · Detection · RCA · Step-by-Step Resolution · Rollback · Prevention · Escalation.
