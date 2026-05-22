import json
import re
import time
from typing import Dict, List, Optional

from langchain_ollama import ChatOllama
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table

from .agent import generate_rca_from_data, generate_solution, run_full_analysis
from .collector import (
    describe_pod,
    get_current_context,
    get_events,
    get_nodes,
    get_pod_logs,
    get_pods,
    get_pods_json,
)
from .detector import detect_pod_anomalies, run_detection
from .models import Anomaly, AnomalyType, Severity
from .sop import generate_index_readme, generate_sop_content, save_sop

console = Console()

_SEVERITY_COLOR = {"CRITICAL": "bold red", "WARNING": "bold yellow", "INFO": "bold blue"}
_SEVERITY_ICON  = {"CRITICAL": "🔴", "WARNING": "🟡", "INFO": "🔵"}

_INTENT_SYSTEM_PROMPT = """\
You are an AIOps assistant for Shweta who manages Kubernetes clusters.
Parse the user's message and return ONLY a JSON object — no prose, no markdown fences.

Available intents:
  scan          – detect anomalies ("scan", "check", "what's wrong", "any issues", "detect")
  analyze       – AI root cause analysis ("analyze", "why", "root cause", "explain")
  analyze_deep  – deep ReAct agent analysis ("deep", "thorough", "full investigation")
  fix           – remediation for a pod ("fix", "repair", "remediate", "how to fix")
  status        – quick cluster overview ("status", "health", "overview", "how is the cluster")
  sop           – generate SOP documents ("sop", "runbook", "document", "procedure")
  watch         – continuous monitoring ("watch", "monitor continuously", "keep checking")
  help          – show capabilities ("help", "what can you do")
  unknown       – cannot determine

JSON schema (all fields required):
{
  "intent": "<one of the intents above>",
  "pod_name": "<pod name if mentioned, else null>",
  "namespace": "<namespace if mentioned, else 'default'>",
  "message": "<1-2 sentence friendly response addressing the user as Shweta>"
}"""

_WELCOME = """\
[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]
[bold white]  AIOps Assistant[/bold white] [dim]— AI-powered Kubernetes copilot[/dim]
[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]

Hi Shweta! I'm your AIOps assistant. Just tell me what you need in plain English.

  [cyan]scan / check[/cyan]          detect cluster anomalies
  [cyan]analyze[/cyan]               AI root cause analysis
  [cyan]deep analyze[/cyan]          thorough ReAct agent investigation
  [cyan]fix <pod>[/cyan]             generate remediation steps for a pod
  [cyan]status / health[/cyan]       quick cluster overview
  [cyan]sop[/cyan]                   generate SOP runbooks
  [cyan]watch[/cyan]                 continuous monitoring (Ctrl-C to stop)
  [cyan]help[/cyan]                  show this list
  [cyan]exit / quit[/cyan]           goodbye
"""


# ---------------------------------------------------------------------------
# Intent parsing
# ---------------------------------------------------------------------------

def _parse_intent(user_input: str, history: List[Dict]) -> Dict:
    llm = ChatOllama(model="gemma4", temperature=0.1)

    messages = [{"role": "system", "content": _INTENT_SYSTEM_PROMPT}]
    for msg in history[-4:]:
        messages.append(msg)
    messages.append({"role": "user", "content": user_input})

    try:
        raw = llm.invoke(messages).content.strip()
        # Strip code fences
        if "```" in raw:
            m = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
            if m:
                raw = m.group(1).strip()
        # Extract the first JSON object
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            raw = m.group(0)
        return json.loads(raw)
    except Exception:
        return _keyword_fallback(user_input)


def _keyword_fallback(text: str) -> Dict:
    lo = text.lower()

    def _resp(intent: str, msg: str) -> Dict:
        return {"intent": intent, "pod_name": None, "namespace": "default", "message": msg}

    if any(w in lo for w in ["deep", "thorough", "full invest"]):
        return _resp("analyze_deep", "Sure Shweta, starting a deep investigation now!")
    if any(w in lo for w in ["analyz", "rca", "root cause", "why"]):
        return _resp("analyze", "On it, Shweta — running root cause analysis!")
    if any(w in lo for w in ["scan", "detect", "check", "wrong", "issue", "problem", "anomal"]):
        return _resp("scan", "Scanning your cluster now, Shweta!")
    if any(w in lo for w in ["fix", "repair", "remediat", "resolv"]):
        return _resp("fix", "Let me generate a fix for that, Shweta!")
    if any(w in lo for w in ["status", "health", "overview", "how's", "hows"]):
        return _resp("status", "Pulling up your cluster status, Shweta!")
    if any(w in lo for w in ["sop", "runbook", "document", "procedure"]):
        return _resp("sop", "Generating SOP documents for you, Shweta!")
    if any(w in lo for w in ["watch", "monitor", "continu"]):
        return _resp("watch", "Starting continuous monitoring, Shweta!")
    if any(w in lo for w in ["help", "what can", "capabilit"]):
        return _resp("help", "Here's everything I can do for you, Shweta!")
    return _resp("unknown", "Hmm, I'm not sure what you mean, Shweta. Try 'help' to see what I can do!")


# ---------------------------------------------------------------------------
# Action helpers
# ---------------------------------------------------------------------------

def _anomaly_table(anomalies: list) -> None:
    if not anomalies:
        console.print("[bold green]✅ No anomalies — cluster looks healthy![/bold green]")
        return

    table = Table(title="Detected Anomalies", show_lines=True, expand=False)
    table.add_column("Severity",  min_width=10, max_width=12, no_wrap=True)
    table.add_column("Type",      min_width=12, max_width=20)
    table.add_column("Namespace", min_width=7,  max_width=14)
    table.add_column("Resource",  min_width=12, max_width=24)
    table.add_column("Details",   min_width=10, max_width=44)

    for a in anomalies:
        icon  = _SEVERITY_ICON.get(a.severity.value, "")
        color = _SEVERITY_COLOR.get(a.severity.value, "white")
        msg   = a.message if len(a.message) <= 80 else a.message[:77] + "..."
        table.add_row(
            f"[{color}]{icon} {a.severity.value}[/{color}]",
            a.type.value, a.namespace, a.resource, msg,
        )

    console.print(table)
    critical = sum(1 for a in anomalies if a.severity == Severity.CRITICAL)
    warnings = sum(1 for a in anomalies if a.severity == Severity.WARNING)
    console.print(
        f"\n[bold]Total: {len(anomalies)} issues[/bold]  |  "
        f"[bold red]Critical: {critical}[/bold red]  |  "
        f"[bold yellow]Warnings: {warnings}[/bold yellow]"
    )


def _do_scan(cluster: str) -> str:
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
        t = p.add_task("Scanning cluster for anomalies…", total=None)
        anomalies = run_detection()
        p.remove_task(t)
    _anomaly_table(anomalies)
    if anomalies:
        c = sum(1 for a in anomalies if a.severity == Severity.CRITICAL)
        return f"Found {len(anomalies)} anomalies ({c} critical)"
    return "No anomalies detected"


def _do_analyze(cluster: str) -> str:
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
        t = p.add_task("Detecting anomalies…", total=None)
        anomalies = run_detection()
        p.update(t, description="Fetching warning events…")
        events = get_events()
        logs_by_pod: dict = {}
        for a in anomalies[:5]:
            if a.namespace != "cluster":
                p.update(t, description=f"Fetching logs: {a.namespace}/{a.resource}…")
                logs = get_pod_logs(a.resource, a.namespace)
                if not logs.startswith("ERROR"):
                    logs_by_pod[f"{a.namespace}/{a.resource}"] = logs
        p.update(t, description="Running AI root cause analysis…")
        analysis = generate_rca_from_data(cluster, anomalies, events, logs_by_pod)
        p.remove_task(t)
    _anomaly_table(anomalies)
    console.print()
    console.print(Panel(Markdown(analysis), title="[bold]Root Cause Analysis[/bold]", border_style="cyan"))
    return "Analysis complete"


def _do_analyze_deep(cluster: str) -> str:
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
        t = p.add_task("Running deep ReAct agent analysis…", total=None)
        result = run_full_analysis(cluster)
        p.remove_task(t)
    console.print(Panel(
        Markdown(result["analysis"]),
        title="[bold]Deep AI Analysis (ReAct Agent)[/bold]",
        border_style="cyan",
    ))
    return "Deep analysis complete"


def _do_fix(cluster: str, pod_name: Optional[str], namespace: str) -> str:
    if not pod_name:
        console.print(
            "[yellow]Which pod should I fix, Shweta? "
            "Mention the pod name, e.g. [bold]fix my-pod-abc123[/bold][/yellow]"
        )
        return "Needs pod name"

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
        t = p.add_task(f"Gathering info for {namespace}/{pod_name}…", total=None)
        pod_desc   = describe_pod(pod_name, namespace)
        logs       = get_pod_logs(pod_name, namespace)
        pods_data  = get_pods_json(namespace)
        pod_issues = [a for a in detect_pod_anomalies(pods_data) if a.resource == pod_name]
        anomaly    = pod_issues[0] if pod_issues else Anomaly(
            id="manual", severity=Severity.WARNING, type=AnomalyType.UNKNOWN,
            resource=pod_name, namespace=namespace,
            message="Manual investigation requested",
        )
        p.update(t, description="Generating fix with Gemma 4…")
        solution = generate_solution(anomaly, pod_desc, logs)
        p.remove_task(t)

    console.print(Panel(
        Markdown(solution),
        title=f"[bold]Fix Recommendations: {namespace}/{pod_name}[/bold]",
        border_style="green",
    ))
    return f"Fix generated for {namespace}/{pod_name}"


def _do_status(cluster: str) -> str:
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
        t = p.add_task("Collecting cluster status…", total=None)
        pods_text = get_pods()
        nodes_text = get_nodes()
        anomalies = run_detection()
        p.remove_task(t)

    console.print(Panel(pods_text  or "No pods found",  title="[bold]Pods[/bold]",  border_style="blue"))
    console.print(Panel(nodes_text or "No nodes found", title="[bold]Nodes[/bold]", border_style="blue"))

    critical = sum(1 for a in anomalies if a.severity == Severity.CRITICAL)
    warnings = sum(1 for a in anomalies if a.severity == Severity.WARNING)
    if critical > 0:
        health = f"[bold red]CRITICAL — {critical} critical issue(s)[/bold red]"
    elif warnings > 0:
        health = f"[bold yellow]DEGRADED — {warnings} warning(s)[/bold yellow]"
    else:
        health = "[bold green]HEALTHY[/bold green]"
    console.print(Panel(f"Health: {health}", title="[bold]Summary[/bold]"))
    return "Status displayed"


def _do_sop(cluster: str) -> str:
    docs_dir = "docs"
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
        t = p.add_task("Scanning cluster…", total=None)
        anomalies = run_detection()
        events = get_events()
        logs_by_pod: dict = {}
        for a in anomalies[:3]:
            if a.namespace != "cluster":
                logs = get_pod_logs(a.resource, a.namespace)
                if not logs.startswith("ERROR"):
                    logs_by_pod[f"{a.namespace}/{a.resource}"] = logs
        p.update(t, description="Running RCA…")
        rca = generate_rca_from_data(cluster, anomalies, events, logs_by_pod)

        seen: set = set()
        sop_anomalies = []
        for a in anomalies:
            if a.type not in seen:
                seen.add(a.type)
                sop_anomalies.append(a)
        if not sop_anomalies:
            from .sop import SOP_TITLES
            for atype in list(SOP_TITLES.keys())[:3]:
                sop_anomalies.append(Anomaly(
                    id=f"ref-{atype.value}", severity=Severity.WARNING, type=atype,
                    resource="example-pod", namespace="default",
                    message=f"Reference SOP for {atype.value}",
                ))

        sop_files: list = []
        for a in sop_anomalies:
            p.update(t, description=f"Writing SOP: {a.type.value}…")
            content  = generate_sop_content(a, root_cause=rca[:1500], solution=f"Fix for {a.type.value}")
            filepath = save_sop(content, a.type, docs_dir)
            sop_files.append(filepath)
            console.print(f"  [green]✓[/green] {filepath}")

        p.update(t, description="Writing index README…")
        generate_index_readme(sop_files, anomalies, docs_dir)
        p.remove_task(t)

    console.print(f"\n[bold green]✅ {len(sop_files)} SOP(s) written to {docs_dir}/[/bold green]")
    return f"Generated {len(sop_files)} SOPs"


def _do_watch(cluster: str, interval: int = 30) -> None:
    console.print(Panel(
        f"[bold cyan]Watching:[/bold cyan] [white]{cluster}[/white]\n"
        "[dim]Press Ctrl-C to stop and return to chat[/dim]",
        border_style="cyan",
    ))
    previous_ids: set = set()
    try:
        while True:
            console.rule(f"[dim]Scan @ {time.strftime('%H:%M:%S')}[/dim]")
            anomalies = run_detection()
            current_ids = {f"{a.type.value}:{a.namespace}:{a.resource}" for a in anomalies}
            new_anomalies = [
                a for a in anomalies
                if f"{a.type.value}:{a.namespace}:{a.resource}" not in previous_ids
            ]
            if not anomalies:
                console.print("[green]✅ Cluster healthy[/green]")
            else:
                _anomaly_table(anomalies)
            if new_anomalies:
                console.print(f"\n[bold red]⚠  {len(new_anomalies)} NEW anomalie(s) detected![/bold red]")
            previous_ids = current_ids
            console.print(f"\n[dim]Next scan in {interval}s… (Ctrl-C to return to chat)[/dim]")
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[bold]Watch stopped. Back to chat, Shweta![/bold]")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_chat() -> None:
    """Start the interactive conversational AIOps CLI."""
    cluster = get_current_context()
    console.print(_WELCOME)
    console.print(f"[dim]Cluster: {cluster}[/dim]\n")

    history: List[Dict] = []

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold]Goodbye, Shweta! Take care. 👋[/bold]")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "bye", "goodbye", "q"):
            console.print("\n[bold]Goodbye, Shweta! Take care. 👋[/bold]")
            break

        # Determine intent — show a brief spinner so the terminal isn't silent
        with Progress(SpinnerColumn(), TextColumn("[dim]Thinking…[/dim]"),
                      console=console, transient=True) as p:
            p.add_task("", total=None)
            parsed = _parse_intent(user_input, history)

        intent     = parsed.get("intent", "unknown")
        pod_name   = parsed.get("pod_name")
        namespace  = parsed.get("namespace") or "default"
        agent_msg  = parsed.get("message", "On it, Shweta!")

        console.print(f"\n[bold green]AIOps[/bold green]  {agent_msg}")
        console.rule(style="dim")

        result = ""
        try:
            if intent == "scan":
                result = _do_scan(cluster)
            elif intent == "analyze":
                result = _do_analyze(cluster)
            elif intent == "analyze_deep":
                result = _do_analyze_deep(cluster)
            elif intent == "fix":
                result = _do_fix(cluster, pod_name, namespace)
            elif intent == "status":
                result = _do_status(cluster)
            elif intent == "sop":
                result = _do_sop(cluster)
            elif intent == "watch":
                _do_watch(cluster)
                result = "Watch mode ended"
            elif intent == "help":
                console.print(_WELCOME)
                result = "Showed help"
            else:
                console.print(
                    "[yellow]I didn't quite catch that, Shweta. "
                    "Try: scan, analyze, deep analyze, fix <pod>, status, sop, watch, or help.[/yellow]"
                )
                result = "Unknown intent"
        except Exception as exc:
            console.print(f"[red]Something went wrong: {exc}[/red]")
            result = f"Error: {exc}"

        # Keep a rolling history for LLM context
        history.append({"role": "user",      "content": user_input})
        history.append({"role": "assistant", "content": f"{agent_msg} [{result}]"})
        if len(history) > 20:
            history = history[-20:]
