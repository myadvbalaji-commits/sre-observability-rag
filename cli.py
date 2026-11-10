import json

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.config import settings
from src.engine.incident_analyzer import IncidentAnalyzer
from src.rag.document_loader import DocumentLoader
from src.rag.vector_store import SREVectorStore

console = Console()

@click.group()
def cli():
    """SRE Incident RAG & Observability CLI."""

@cli.command()
@click.argument("alert_path", type=click.Path(exists=True))
def diagnose(alert_path: str):
    """Diagnose an active incident from an alert JSON file."""
    with open(alert_path, "r", encoding="utf-8") as f:
        alert_data = json.load(f)

    console.print("[bold cyan]🔍 Loading SRE Vector Index...[/bold cyan]")
    vs = SREVectorStore()
    docs = DocumentLoader.load_all_sample_data(settings.sample_data_dir)
    vs.add_documents(docs)

    analyzer = IncidentAnalyzer(vector_store=vs)
    console.print(f"[bold yellow]⚡ Running RAG Analysis for Incident {alert_data.get('incident_id')}...[/bold yellow]")
    
    result = analyzer.analyze_incident(alert_data)

    console.print(Panel(
        f"[bold green]Root Cause Summary:[/bold green]\n{result.get('root_cause_summary')}\n\n"
        f"[bold cyan]Confidence Score:[/bold cyan] {int(result.get('confidence_score', 0.9)*100)}%\n\n"
        f"[bold white]Technical Analysis:[/bold white]\n{result.get('root_cause_analysis')}",
        title=f"🚨 RCA Report: {result.get('incident_id')}",
        expand=False
    ))

    table = Table(title="Recommended Immediate Mitigations")
    table.add_column("Step", style="cyan")
    table.add_column("Command / Action", style="magenta")

    for i, step in enumerate(result.get("immediate_mitigation_steps", []), 1):
        cmd = result.get("mitigation_commands", ["N/A"])[0] if i == 2 and result.get("mitigation_commands") else "See runbook"
        table.add_row(step, cmd)

    console.print(table)

@cli.command()
@click.argument("query")
@click.option("--top-k", default=3, help="Number of results to retrieve")
def search(query: str, top_k: int):
    """Search postmortems and runbooks in the vector store."""
    vs = SREVectorStore()
    docs = DocumentLoader.load_all_sample_data(settings.sample_data_dir)
    vs.add_documents(docs)
    
    results = vs.search(query, top_k=top_k)
    for r in results:
        console.print(Panel(
            r["content"][:400] + "...",
            title=f"📄 {r['doc_id']} (Score: {r['similarity_score']})",
            subtitle=f"Type: {r['metadata'].get('doc_type')}"
        ))

if __name__ == "__main__":
    cli()
