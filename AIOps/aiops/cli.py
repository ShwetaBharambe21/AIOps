import time
from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

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
from .agent import generate_rca_from_data, generate_solution, run_full_analysis
from .sop import generate_index_readme, generate_sop_content, save_sop

app = typer.Typer(
    name="aiops",
    help="AIOps CLI — AI-powered Kubernetes anomaly detection and incident response (Gemma 4 via Ollama)",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()

_SEVERITY_COLOR = {"CRITICAL": "bold red", "WARNING": "bold yellow", "INFO": "bold blue"}
_SEVERITY_ICON = {"CRITICAL": "🔴", "WARNING": "🟡", "INFO": "🔵"}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _cluster_name() -> str:
    return get_current_context()


def _print_anomaly_table(anomalies: list[Anomaly]) -> None:
    if not anomalies:
        console.print("[bold green]✅ No anomalies detected — cluster looks healthy.[/bold green]")
        return

    table = Table(title="Detected Anomalies", show_lines=True, expand=False)
    table.add_column("Severity", width=12)
    table.add_column("Type", width=24)
    table.add_column("Namespace", width=18)
    table.add_column("Resource", width=30)
    table.add_column("Details", width=52)

    for a in anomalies:
        icon = _SEVERITY_ICON.get(a.severity.value, "")
        color = _SEVERITY_COLOR.get(a.severity.value, "white")
        msg = a.message if len(a.message) <= 80 else a.message[:77] + "..."
        table.add_row(
            f"[{color}]{icon} {a.severity.value}[/{color}]",
            a.type.value,
            a.namespace,
            a.resource,
            msg,
        )

    console.print(table)
    critical = sum(1 for a in anomalies if a.severity == Severity.CRITICAL)
    warnings = sum(1 for a in anomalies if a.severity == Severity.WARNING)
    console.print(
        f"\n[bold]Total: {len(anomalies)} issues[/bold]  |  "
        f"[bold red]Critical: {critical}[/bold red]  |  "
        f"[bold yellow]Warnings: {warnings}[/bold yellow]"
    )


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

@app.command()
def scan(
    namespace: Optional[str] = typer.Option(None, "--namespace", "-n", help="Limit scan to one namespace"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table | json"),
    ai: bool = typer.Option(False, "--ai", help="Follow scan with AI root-cause analysis"),
):
    """[bold cyan]Scan[/bold cyan] the cluster and detect anomalies."""
    cluster = _cluster_name()
    console.print(Panel(
        f"[bold cyan]Scanning cluster:[/bold cyan] [white]{cluster}[/white]",
        subtitle="AIOps · Anomaly Detection",
    ))

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
        t = p.add_task("Collecting cluster data …", total=None)
        anomalies = run_detection()
        p.remove_task(t)

    if output == "json":
        import json
        console.print(json.dumps([a.model_dump(mode='json') for a in anomalies], indent=2))
        return

    _print_anomaly_table(anomalies)

    if ai and anomalies:
        console.print("\n[bold cyan]Running AI root-cause analysis …[/bold cyan]")
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
            t = p.add_task("Querying Gemma 4 via Ollama …", total=None)
            events = get_events()
            logs_by_pod: dict = {}
            for a in anomalies[:3]:
                if a.namespace != "cluster":
                    logs = get_pod_logs(a.resource, a.namespace)
                    if not logs.startswith("ERROR"):
                        logs_by_pod[f"{a.namespace}/{a.resource}"] = logs
            analysis = generate_rca_from_data(cluster, anomalies, events, logs_by_pod)
            p.remove_task(t)
        console.print(Panel(Markdown(analysis), title="[bold]AI Root Cause Analysis[/bold]", border_style="cyan"))


@app.command()
def analyze(
    namespace: Optional[str] = typer.Argument(None, help="Namespace to focus on (default: all)"),
    deep: bool = typer.Option(False, "--deep", "-d", help="Use ReAct agent with live k8s tool access"),
):
    """[bold cyan]Analyze[/bold cyan] the cluster with AI-powered root cause analysis."""
    cluster = _cluster_name()
    console.print(Panel(
        f"[bold cyan]Analyzing cluster:[/bold cyan] [white]{cluster}[/white]  "
        f"[dim]namespace: {namespace or 'all'}[/dim]",
        subtitle="AIOps · Root Cause Analysis",
    ))

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
        if deep:
            t = p.add_task("Running deep ReAct agent analysis …", total=None)
            result = run_full_analysis(cluster)
            p.remove_task(t)
            console.print(Panel(
                Markdown(result["analysis"]),
                title="[bold]Deep AI Analysis (ReAct Agent)[/bold]",
                border_style="cyan",
            ))
        else:
            t = p.add_task("Detecting anomalies …", total=None)
            anomalies = run_detection()
            p.update(t, description="Fetching warning events …")
            events = get_events()

            logs_by_pod: dict = {}
            for a in anomalies[:5]:
                if a.namespace != "cluster":
                    p.update(t, description=f"Fetching logs: {a.namespace}/{a.resource} …")
                    logs = get_pod_logs(a.resource, a.namespace)
                    if not logs.startswith("ERROR"):
                        logs_by_pod[f"{a.namespace}/{a.resource}"] = logs

            p.update(t, description="Querying Gemma 4 …")
            analysis = generate_rca_from_data(cluster, anomalies, events, logs_by_pod)
            p.remove_task(t)

            _print_anomaly_table(anomalies)
            console.print()
            console.print(Panel(Markdown(analysis), title="[bold]Root Cause Analysis[/bold]", border_style="cyan"))


@app.command()
def fix(
    pod: str = typer.Argument(..., help="Pod name to generate fix for"),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Kubernetes namespace"),
):
    """[bold cyan]Fix[/bold cyan] — generate AI remediation steps for a specific pod."""
    cluster = _cluster_name()
    console.print(Panel(
        f"[bold cyan]Generating fix for:[/bold cyan] [white]{namespace}/{pod}[/white]",
        subtitle="AIOps · Fix Generator",
    ))

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
        t = p.add_task("Gathering pod information …", total=None)
        pod_desc = describe_pod(pod, namespace)
        logs = get_pod_logs(pod, namespace)

        pods_data = get_pods_json(namespace)
        pod_anomalies = [a for a in detect_pod_anomalies(pods_data) if a.resource == pod]
        anomaly = pod_anomalies[0] if pod_anomalies else Anomaly(
            id="manual",
            severity=Severity.WARNING,
            type=AnomalyType.UNKNOWN,
            resource=pod,
            namespace=namespace,
            message="Manual investigation requested",
        )

        p.update(t, description="Querying Gemma 4 for fix …")
        solution = generate_solution(anomaly, pod_desc, logs)
        p.remove_task(t)

    console.print(Panel(
        Markdown(solution),
        title=f"[bold]Fix Recommendations: {namespace}/{pod}[/bold]",
        border_style="green",
    ))


@app.command()
def sop(
    generate_all: bool = typer.Option(False, "--all", help="Generate SOPs for all detected anomaly types"),
    anomaly_type: Optional[str] = typer.Option(None, "--type", "-t", help="Specific anomaly type to generate SOP for"),
    docs_dir: str = typer.Option("docs", "--docs-dir", help="Directory to write SOP markdown files"),
):
    """[bold cyan]SOP[/bold cyan] — generate Standard Operating Procedure documents."""
    target: Optional[AnomalyType] = None
    if anomaly_type:
        try:
            target = AnomalyType(anomaly_type)
        except ValueError:
            console.print(f"[red]Unknown anomaly type: {anomaly_type}[/red]")
            console.print(f"Valid types: {', '.join(a.value for a in AnomalyType)}")
            raise typer.Exit(1)

    cluster = _cluster_name()
    console.print(Panel(
        f"[bold cyan]Generating SOPs for cluster:[/bold cyan] [white]{cluster}[/white]\n"
        f"[dim]Output: {docs_dir}/[/dim]",
        subtitle="AIOps · SOP Generator",
    ))

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
        t = p.add_task("Scanning cluster …", total=None)
        anomalies = run_detection()
        events = get_events()

        logs_by_pod: dict = {}
        for a in anomalies[:3]:
            if a.namespace != "cluster":
                logs = get_pod_logs(a.resource, a.namespace)
                if not logs.startswith("ERROR"):
                    logs_by_pod[f"{a.namespace}/{a.resource}"] = logs

        p.update(t, description="Performing RCA …")
        rca = generate_rca_from_data(cluster, anomalies, events, logs_by_pod)

        if target is not None:
            sop_anomalies = [a for a in anomalies if a.type == target][:1]
            if not sop_anomalies:
                sop_anomalies = [Anomaly(
                    id="ref", severity=Severity.WARNING, type=target,
                    resource="example-pod", namespace="default",
                    message=f"Reference SOP for {target.value}",
                )]
        else:
            seen: set = set()
            sop_anomalies = []
            for a in anomalies:
                if a.type not in seen:
                    seen.add(a.type)
                    sop_anomalies.append(a)
            if not sop_anomalies:
                from .sop import SOP_TITLES
                for atype in list(SOP_TITLES.keys())[:4]:
                    sop_anomalies.append(Anomaly(
                        id=f"ref-{atype.value}", severity=Severity.WARNING, type=atype,
                        resource="example-pod", namespace="default",
                        message=f"Reference SOP for {atype.value}",
                    ))

        sop_files: list[str] = []
        for a in sop_anomalies:
            p.update(t, description=f"Writing SOP: {a.type.value} …")
            content = generate_sop_content(a, root_cause=rca[:1500], solution=f"Fix for {a.type.value}")
            filepath = save_sop(content, a.type, docs_dir)
            sop_files.append(filepath)
            console.print(f"  [green]✓[/green] {filepath}")

        p.update(t, description="Writing index README …")
        readme = generate_index_readme(sop_files, anomalies, docs_dir)
        p.remove_task(t)

    console.print(f"\n[bold green]✅ {len(sop_files)} SOP(s) + index README written to {docs_dir}/[/bold green]")
    console.print(f"[dim]Index: {readme}[/dim]")


@app.command()
def watch(
    interval: int = typer.Option(60, "--interval", "-i", help="Scan interval in seconds"),
    namespace: Optional[str] = typer.Option(None, "--namespace", "-n", help="Namespace to watch"),
    ai: bool = typer.Option(False, "--ai", help="Run AI analysis when new anomalies are found"),
):
    """[bold cyan]Watch[/bold cyan] — continuously monitor the cluster for anomalies."""
    cluster = _cluster_name()
    console.print(Panel(
        f"[bold cyan]Watching:[/bold cyan] [white]{cluster}[/white]  "
        f"[dim]interval={interval}s  namespace={namespace or 'all'}[/dim]\n"
        "[dim]Press Ctrl+C to stop[/dim]",
        subtitle="AIOps · Continuous Monitoring",
    ))

    previous_ids: set = set()
    try:
        while True:
            console.rule(f"[dim]Scan @ {datetime.now().strftime('%H:%M:%S')}[/dim]")
            anomalies = run_detection()
            current_ids = {f"{a.type.value}:{a.namespace}:{a.resource}" for a in anomalies}
            new_anomalies = [a for a in anomalies if f"{a.type.value}:{a.namespace}:{a.resource}" not in previous_ids]

            if not anomalies:
                console.print("[green]✅ Cluster healthy[/green]")
            else:
                _print_anomaly_table(anomalies)

            if new_anomalies:
                console.print(f"\n[bold red]⚠  {len(new_anomalies)} NEW anomalie(s) detected![/bold red]")
                for a in new_anomalies:
                    console.print(f"  {_SEVERITY_ICON.get(a.severity.value, '')} [bold]{a.type.value}[/bold]: {a.namespace}/{a.resource}")

                if ai:
                    console.print("\n[cyan]Running AI analysis on new anomalies …[/cyan]")
                    events = get_events()
                    logs_by_pod: dict = {}
                    for a in new_anomalies[:2]:
                        if a.namespace != "cluster":
                            logs = get_pod_logs(a.resource, a.namespace)
                            if not logs.startswith("ERROR"):
                                logs_by_pod[f"{a.namespace}/{a.resource}"] = logs
                    analysis = generate_rca_from_data(cluster, new_anomalies, events, logs_by_pod)
                    console.print(Panel(Markdown(analysis), border_style="red"))

            previous_ids = current_ids
            console.print(f"\n[dim]Next scan in {interval}s …[/dim]")
            time.sleep(interval)

    except KeyboardInterrupt:
        console.print("\n[bold]Monitoring stopped.[/bold]")


@app.command()
def status():
    """[bold cyan]Status[/bold cyan] — show a quick cluster health overview."""
    cluster = _cluster_name()
    console.print(Panel(
        f"[bold cyan]Cluster:[/bold cyan] [white]{cluster}[/white]",
        subtitle="AIOps · Status",
    ))

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
        t = p.add_task("Collecting status …", total=None)
        pods_text = get_pods()
        nodes_text = get_nodes()
        anomalies = run_detection()
        p.remove_task(t)

    console.print(Panel(pods_text or "No pods found", title="[bold]Pods[/bold]", border_style="blue"))
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

if __name__ == "__main__":
    app()