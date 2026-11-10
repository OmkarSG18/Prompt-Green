import sys
import os
import json
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from promptgreen.analysis.diff_parser import PromptDiffAnalyzer
from promptgreen.predictor.hybrid_predictor import HybridPredictor
from promptgreen.engine.carbon_engine import CarbonEngine
from promptgreen.gate.prompt_gate import PromptGate
from promptgreen.ledger.database import PromptLedger
from promptgreen.validation.benchmark import BenchmarkSuiteRunner

console = Console()


@click.group()
@click.version_option("1.0.0", prog_name="PromptGreen")
def main():
    """PromptGreen: Zero-Budget Carbon-Aware Prompt Review CLI."""
    pass


@main.command()
@click.option("--old", required=True, help="Baseline (old) prompt text or file path.")
@click.option("--new", required=True, help="Optimized (new) prompt text or file path.")
@click.option("--model", default="llama-3-8b", help="Model key (llama-3-8b, mistral-7b, phi-3-3.8b, llama-3-70b, gpt-4).")
@click.option("--region", default="US", help="Region code (US, EU, IN, GLOBAL).")
@click.option("--budget", default=0.5, type=float, help="Carbon budget threshold (gCO2 per 1K inferences).")
@click.option("--mode", default="warn", type=click.Choice(["warn", "block"]), help="Gate enforcement policy mode.")
@click.option("--monthly", default=10000, type=int, help="Assumed monthly inference volume.")
@click.option("--author", default="local-user", help="Author name for ledger.")
@click.option("--team", default="Engineering", help="Team name for ledger.")
def analyze(old, new, model, region, budget, mode, monthly, author, team):
    """Analyze old vs new prompt and evaluate carbon gate."""
    # Resolve file paths if provided
    if os.path.exists(old):
        with open(old, "r", encoding="utf-8") as f:
            old = f.read()
    if os.path.exists(new):
        with open(new, "r", encoding="utf-8") as f:
            new = f.read()

    gate = PromptGate(budget_threshold_gco2_1k=budget, mode=mode, model_key=model, region=region)
    res = gate.evaluate(old, new, monthly_inferences=monthly)

    # Print Panel Header
    status_style = "bold green" if res.status_code == "PASS" else ("bold yellow" if res.status_code == "WARN" else "bold red")
    console.print(Panel(f"PromptGreen Gate Evaluation Result: [{status_style}]{res.status_code}[/{status_style}]", title="[bold green]PromptGreen Carbon Review[/bold green]"))

    # Print Metrics Table
    table = Table(title="Carbon Impact Metrics Breakdown", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="dim")
    table.add_column("Baseline (Old)")
    table.add_column("Proposed (New)")
    table.add_column("Delta", style="bold")

    c = res.carbon_result
    table.add_row("Input Tokens", str(c.features.old_input_tokens), str(c.features.new_input_tokens), f"{c.features.input_token_delta:+d}")
    table.add_row("Predicted Output Tokens", f"{c.prediction.predicted_old_output_tokens:.1f}", f"{c.prediction.predicted_new_output_tokens:.1f}", f"{c.prediction.predicted_output_token_delta:+.1f} ({c.prediction.inflation_percentage:+.1f}%)")
    table.add_row("Energy per Inference (mJ)", f"{c.old_energy_per_inf_mj:.2f}", f"{c.new_energy_per_inf_mj:.2f}", f"{c.energy_delta_per_inf_mj:+.2f}")
    table.add_row("Carbon per 1K Inferences (gCO2)", f"{c.old_carbon_per_inf_gco2*1000:.4f}", f"{c.new_carbon_per_inf_gco2*1000:.4f}", f"{c.carbon_delta_per_1k_gco2:+.4f}")
    table.add_row(f"Est. Monthly Footprint ({monthly:,} inf)", "-", "-", f"[bold]{c.monthly_carbon_delta_gco2:+.2f} gCO2[/bold]")

    console.print(table)

    # Print Detected Semantic Changes
    console.print("\n[bold yellow]Semantic Prompt Changes Detected:[/bold yellow]")
    if c.features.detected_changes:
        for ch in c.features.detected_changes:
            console.print(f"  • {ch}")
    else:
        console.print("  • Minor textual edits")

    # Print Suggestions
    console.print("\n[bold cyan]Carbon Optimization Suggestions:[/bold cyan]")
    for sg in res.suggestions:
        console.print(f"  • {sg}")

    # Record to local SQLite ledger
    ledger = PromptLedger()
    ledger.record_prompt_review(
        commit_hash="local-cli",
        author=author,
        team=team,
        model_name=c.model_name,
        region=region,
        old_prompt=old[:100],
        new_prompt=new[:100],
        input_token_delta=c.features.input_token_delta,
        predicted_output_token_delta=c.prediction.predicted_output_token_delta,
        carbon_delta_gco2_1k=c.carbon_delta_per_1k_gco2,
        monthly_carbon_delta_gco2=c.monthly_carbon_delta_gco2,
        status=res.status_code
    )
    console.print("\n[dim][Success] Recorded review result into local Prompt Carbon Ledger (prompt_ledger.db)[/dim]")

    if not res.passed and mode == "block":
        sys.exit(1)


@main.command(name="git-diff")
@click.option("--commit", default="HEAD~1", help="Git commit / ref to compare against HEAD.")
@click.option("--model", default="llama-3-8b", help="Model key.")
@click.option("--budget", default=0.5, type=float, help="Carbon budget threshold (gCO2 / 1K inf).")
@click.option("--mode", default="warn", type=click.Choice(["warn", "block"]), help="Gate enforcement policy mode.")
def git_diff(commit, model, budget, mode):
    """Analyze Git repository prompt diffs."""
    import subprocess
    try:
        diff_out = subprocess.check_output(["git", "diff", commit, "HEAD"], text=True)
    except Exception as e:
        console.print(f"[bold red]Failed to execute git diff: {e}[/bold red]")
        sys.exit(1)

    if not diff_out.strip():
        console.print("[green]No git diff detected between commit and HEAD.[/green]")
        return

    analyzer = PromptDiffAnalyzer()
    feats = analyzer.analyze_git_diff(diff_out)
    console.print(Panel(f"Git Diff Token Delta: [bold]{feats.input_token_delta:+d}[/bold] tokens across prompt files.", title="PromptGreen Git Diff Analysis"))


@main.command()
@click.option("--data", default=None, help="Path to benchmark_suite.json.")
def benchmark(data):
    """Run validation benchmark suite across 50 prompt pairs."""
    runner = BenchmarkSuiteRunner(json_path=data)
    res = runner.run_evaluation()

    console.print(Panel("Validation Benchmark Results", title="[bold green]PromptGreen Benchmark Suite[/bold green]"))

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric")
    table.add_column("Result Target")
    table.add_column("Measured Value", style="bold green")

    table.add_row("Total Benchmark Pairs", "50 Pairs", f"{res['total_pairs']} Pairs")
    table.add_row("Directional Accuracy", "> 85.0%", f"{res['directional_accuracy_pct']:.1f}%")
    table.add_row("Mean Absolute Pct Error (MAPE)", "< 20.0%", f"{res['mape_pct']:.1f}%")
    table.add_row("R² Regression Score", "> 0.80", f"{res['r2_score']:.4f}")

    console.print(table)


@main.command()
@click.option("--limit", default=10, help="Number of records to show.")
def ledger(limit):
    """Inspect local Prompt Carbon Ledger records."""
    db = PromptLedger()
    db.seed_demo_data_if_empty()
    records = db.get_recent_records(limit=limit)

    table = Table(title="Prompt Carbon Ledger Records", show_header=True, header_style="bold blue")
    table.add_column("ID", style="dim")
    table.add_column("Commit")
    table.add_column("Author")
    table.add_column("Team")
    table.add_column("Model")
    table.add_column("Input Δ")
    table.add_column("Output Δ")
    table.add_column("Carbon Δ / 1K")
    table.add_column("Status")

    for r in records:
        status_style = "green" if r["status"] == "PASS" else ("yellow" if r["status"] == "WARN" else "red")
        table.add_row(
            str(r["id"]),
            r["commit_hash"][:7],
            r["author"],
            r["team"],
            r["model_name"],
            f"{r['input_token_delta']:+d}",
            f"{r['predicted_output_token_delta']:+.1f}",
            f"{r['carbon_delta_gco2_1k']:+.4f}g",
            f"[{status_style}]{r['status']}[/{status_style}]"
        )

    console.print(table)

    summary = db.get_cumulative_carbon_debt()
    console.print(f"\n[bold]Total Reviews:[/bold] {summary.get('total_reviews', 0)} | "
                  f"[bold green]Passed:[/bold green] {summary.get('passed_reviews', 0)} | "
                  f"[bold red]Failed/Warned:[/bold red] {summary.get('failed_reviews', 0) + summary.get('warned_reviews', 0)} | "
                  f"[bold cyan]Net 1K Carbon Δ:[/bold cyan] {summary.get('total_carbon_delta_1k', 0.0):+.4f} gCO2")


if __name__ == "__main__":
    main()
