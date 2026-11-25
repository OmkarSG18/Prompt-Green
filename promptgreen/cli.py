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
from promptgreen.optimizer.pipeline import PromptGreenPipeline, PipelineConfig, PipelineResult
from promptgreen.optimizer.semantic_guard import LocalMiniLMEmbedder
from promptgreen.engine.model_profiles import DEFAULT_PROFILE_REGISTRY, STANDARD_MODEL_TIERS
from promptgreen.engine.thermodynamics import (
    calculate_thermodynamic_impact,
    calculate_multi_scenario_impact,
    AccountingScenario,
    MultiScenarioEnergyResult,
)
from promptgreen.engine.model_router import (
    GreenModelRouter,
    TaskCategory,
    TaskComplexity,
    TaskContext,
    ModelRoutingRecommendation,
)

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


@main.command(name="optimize")
@click.option("--prompt", "-p", required=True, help="Input prompt text or file path containing the prompt.")
@click.option("--mode", "-m", default="balanced", type=click.Choice(["conservative", "balanced", "aggressive"], case_sensitive=False), help="Optimization policy mode (conservative, balanced, aggressive).")
@click.option("--model-tier", "-t", default="mid_tier", type=click.Choice(["frontier_dense", "large_reasoning", "mid_tier", "compact_green"], case_sensitive=False), help="Target downstream LLM tier.")
@click.option("--grid", "-g", default="ILLUSTRATIVE_385", help="Grid scenario code (e.g. ILLUSTRATIVE_385, THESIS_367) or custom gCO2/kWh value.")
@click.option("--monthly", default=10000, type=int, help="Assumed monthly inference volume.")
@click.option("--record/--no-record", default=False, help="Whether to persist this optimization record in prompt_ledger.db.")
@click.option("--author", default="cli-user", help="Author name for ledger recording.")
@click.option("--team", default="Engineering", help="Team name for ledger recording.")
def optimize(prompt, mode, model_tier, grid, monthly, record, author, team):
    """Run the 4-stage active PromptGreen V2 optimization pipeline and thermodynamic telemetry."""
    import time

    # Read prompt from file if path exists
    prompt_text = prompt
    if os.path.exists(prompt):
        try:
            with open(prompt, "r", encoding="utf-8") as f:
                prompt_text = f.read()
        except Exception as f_err:
            console.print(f"[bold red]Failed to read prompt file: {f_err}[/bold red]")
            sys.exit(1)

    if not prompt_text.strip():
        console.print("[bold red]Error: Prompt text cannot be empty or whitespace only.[/bold red]")
        sys.exit(1)

    mode = mode.lower()
    model_tier = model_tier.lower()

    # Prewarm cached MiniLM model safely if not already loaded
    try:
        LocalMiniLMEmbedder.prewarm()
    except Exception as pw_err:
        console.print(f"[dim yellow]Model prewarming note: {pw_err}[/dim yellow]")

    # 1. Run 4-stage pipeline
    pipeline = PromptGreenPipeline(config=PipelineConfig(mode=mode))
    t0 = time.perf_counter()
    opt_res: PipelineResult = pipeline.optimize(prompt_text)
    latency_ms = (time.perf_counter() - t0) * 1000.0

    # 2. Hybrid output token prediction
    predictor = HybridPredictor()
    pred_res = predictor.predict(opt_res.original_prompt, opt_res.final_prompt)
    if opt_res.original_prompt.strip() == opt_res.final_prompt.strip():
        tout_orig = pred_res.predicted_old_output_tokens
        tout_opt = tout_orig
    else:
        tout_orig = pred_res.predicted_old_output_tokens
        tout_opt = pred_res.predicted_new_output_tokens

    # 3. Thermodynamic energy & carbon multi-scenario calculation
    grid_arg = grid
    try:
        grid_arg = float(grid)
    except ValueError:
        grid_arg = str(grid)

    is_identical = (opt_res.original_prompt.strip() == opt_res.final_prompt.strip())
    multi_res: MultiScenarioEnergyResult = calculate_multi_scenario_impact(
        tin_original=opt_res.original_token_count,
        tin_optimized=opt_res.final_token_count,
        optimizer_latency_ms=latency_ms,
        model_tier=model_tier,
        grid_scenario=grid_arg,
        predicted_tout_original=tout_orig,
        predicted_tout_optimized=tout_opt,
        p_cpu_w=35.0,
        pue=1.15,
        wue_ml_per_wh=1.8,
        is_prompt_identical=is_identical,
    )

    verif_res = multi_res.input_only
    pred_res_thermo = multi_res.input_plus_predicted_output
    thermo_res = pred_res_thermo

    # 4. Conservative Green Model Router
    router = GreenModelRouter(registry=DEFAULT_PROFILE_REGISTRY)
    cat = TaskCategory.UNKNOWN
    if "def " in prompt_text or "function" in prompt_text or "python" in prompt_text.lower():
        cat = TaskCategory.CODE_GENERATION
    elif "step-by-step" in prompt_text.lower() or "calculate" in prompt_text.lower() or "prove" in prompt_text.lower():
        cat = TaskCategory.COMPLEX_REASONING

    task_ctx = TaskContext(
        task_category=cat,
        task_complexity=TaskComplexity.MEDIUM,
        task_description=prompt_text[:150],
        requires_code_generation=(cat == TaskCategory.CODE_GENERATION),
        requires_deep_reasoning=(cat == TaskCategory.COMPLEX_REASONING),
    )

    routing_rec: ModelRoutingRecommendation = router.recommend(
        current_model_tier=model_tier,
        task_context=task_ctx,
        input_tokens=opt_res.final_token_count,
        expected_output_tokens=tout_opt,
        grid_scenario=grid_arg,
    )

    # 5. Format Output with Rich Panels & Tables
    status_color = "bold green" if opt_res.accepted and not verif_res.is_net_carbon_debt else ("bold yellow" if opt_res.accepted else "bold red")
    guard_badge = "ACCEPTED" if opt_res.accepted else f"ROLLED BACK ({opt_res.rollback_stage})"
    debt_badge = "CARBON DEBT" if verif_res.is_net_carbon_debt else "NET SAVINGS"
    console.print(Panel(
        f"Optimization Mode: [cyan]{mode.upper()}[/cyan] | Target Tier: [cyan]{model_tier}[/cyan] | Guardrail: [{status_color}]{guard_badge}[/{status_color}] | Verified Baseline: [{status_color}]{debt_badge}[/{status_color}]",
        title="[bold green]PromptGreen V2 Active Prompt Optimization[/bold green]",
        border_style="green"
    ))

    # Prompts comparison
    console.print(Panel(opt_res.original_prompt, title="[dim]Original Prompt[/dim]", border_style="dim"))
    console.print(Panel(opt_res.final_prompt, title="[bold cyan]Optimized Green Prompt[/bold cyan]", border_style="cyan"))

    # Table 1: Token & Quality Metrics
    t_tok = Table(title="Token Accounting & Quality Metrics", show_header=True, header_style="bold cyan")
    t_tok.add_column("Metric", style="dim")
    t_tok.add_column("Value")
    t_tok.add_column("Methodology / Epistemic Status", style="italic dim")

    t_tok.add_row("Input Tokens", f"{opt_res.original_token_count} -> {opt_res.final_token_count} (Saved: {opt_res.net_token_reduction}, {opt_res.net_token_reduction_pct:.1f}%)", "(exact measured tiktoken count)")
    t_tok.add_row("Output Tokens", f"{tout_orig:.1f} -> {tout_opt:.1f} (Saved: {tout_orig - tout_opt:.1f})", "(modeled hybrid regression prediction)")
    t_tok.add_row("Semantic Fidelity Score", f"{opt_res.semantic_similarity:.4f}" if opt_res.semantic_similarity is not None else "N/A", "(measured cosine similarity vs mode threshold)")
    t_tok.add_row("Pipeline Execution Latency", f"{latency_ms:.1f} ms", "(measured host wall-clock time)")
    t_tok.add_row("Rollback Occurred", f"{opt_res.rollback_occurred} (Stage: {opt_res.rollback_stage or 'none'})", "(automated safety guardrail)")
    console.print(t_tok)

    # Table 2: Conservative Verified Accounting (Scenario 1: INPUT_ONLY)
    t_env = Table(title="[bold green]Thermodynamic Energy & Carbon Accounting — Scenario 1: Verified Input-Only (Primary Baseline)[/bold green]", show_header=True, header_style="bold green")
    t_env.add_column("Metric", style="dim")
    t_env.add_column("Value")
    t_env.add_column("Methodology / Epistemic Status", style="italic dim")

    t_env.add_row("Original Input Energy", f"{verif_res.energy_orig_wh:.6f} Wh", "(measured input tokens: PUE=1.15)")
    t_env.add_row("Optimized Input Energy", f"{verif_res.energy_opt_wh:.6f} Wh", "(measured input tokens: PUE=1.15)")
    t_env.add_row("Gross Input Energy Saved", f"{verif_res.gross_energy_saved_wh:.6f} Wh", "(directly verifiable input delta; 0 output assumed)")
    t_env.add_row("Optimizer CPU Overhead", f"{verif_res.optimizer_overhead_wh:.6f} Wh", "(modeled local CPU: 35.0W unmeasured estimate)")
    v_net_style = "bold red" if verif_res.is_net_carbon_debt else "bold green"
    t_env.add_row("Net Energy Saved (ΔE_net)", f"[{v_net_style}]{verif_res.net_energy_saved_wh:+.6f} Wh[/{v_net_style}]", "(honest net accounting: Gross Input - Overhead)")
    t_env.add_row("Net Carbon Abated per 1K", f"{verif_res.net_carbon_abated_per_1k_gco2:+.4f} gCO2e", f"(grid intensity: {verif_res.grid_intensity_gco2_kwh} g/kWh)")
    t_env.add_row(f"Est. Monthly Carbon ({monthly:,} inf)", f"{verif_res.net_carbon_abated_gco2 * monthly:+.2f} gCO2e", "(projected cumulative impact)")
    t_env.add_row("Net Cooling Water Saved", f"{verif_res.net_water_saved_per_1k_ml:+.2f} mL / 1K inf", "(modeled evaporative cooling: 1.8 mL/Wh)")
    console.print(t_env)

    # Panel: Exploratory Modeled Downstream Estimate (Scenario 2: INPUT_PLUS_PREDICTED_OUTPUT)
    p_net_style = "bold red" if pred_res_thermo.is_net_carbon_debt else "bold green"
    console.print(Panel(
        f"[bold yellow]Scenario 2: Exploratory Modeled Downstream Estimate (Secondary)[/bold yellow]\n"
        f"• Predicted Output Delta: [bold]{tout_opt - tout_orig:+.1f} tokens[/bold] (Zero-diff guard enforced: {is_identical})\n"
        f"• Modeled Gross Energy Saved: [bold]{pred_res_thermo.gross_energy_saved_wh:.6f} Wh[/bold]\n"
        f"• Modeled Net Energy Saved: [{p_net_style}]{pred_res_thermo.net_energy_saved_wh:+.6f} Wh[/{p_net_style}]\n"
        f"• Modeled Net Carbon Abated / 1K: [bold]{pred_res_thermo.net_carbon_abated_per_1k_gco2:+.4f} gCO2e[/bold]\n\n"
        f"[dim italic]Epistemic Status: Exploratory modeled estimate combining measured input tokens with HybridPredictor downstream output estimates. Not physically measured.[/dim italic]",
        title="[bold yellow]Downstream Output Modeling (Exploratory)[/bold yellow]",
        border_style="yellow"
    ))

    # Table 3: Green Model Router Recommendation
    r_style = "bold green" if routing_rec.outcome.name == "RECOMMEND_LOWER_ENERGY_TIER" else "bold yellow"
    console.print(Panel(
        f"Routing Decision: [{r_style}]{routing_rec.outcome.name}[/{r_style}]\n"
        f"Recommended Tier: [bold cyan]{routing_rec.recommended_model_tier or 'N/A'}[/bold cyan] (Confidence: {routing_rec.confidence_level.name})\n"
        f"Reasoning: {routing_rec.explanation}\n\n"
        f"[dim italic]Advisory Governance: {routing_rec.disclaimer}[/dim italic]",
        title="[bold blue]Conservative Green Model Router (Advisory Recommendation)[/bold blue]",
        border_style="blue"
    ))

    # Optional recording to SQLite ledger
    if record:
        db = PromptLedger()
        st_code = "PASS" if (not thermo_res.is_net_carbon_debt and opt_res.guardrail_passed) else ("WARN" if not thermo_res.is_net_carbon_debt else "FAIL")
        rid = db.record_v2_run(
            commit_hash="cli-v2",
            author=author,
            team=team,
            model_name=model_tier,
            region=str(grid_arg),
            old_prompt=opt_res.original_prompt[:100],
            new_prompt=opt_res.final_prompt[:100],
            input_token_delta=opt_res.final_token_count - opt_res.original_token_count,
            predicted_output_token_delta=tout_opt - tout_orig,
            carbon_delta_gco2_1k=-(thermo_res.net_carbon_abated_per_1k_gco2),
            monthly_carbon_delta_gco2=-(thermo_res.net_carbon_abated_gco2 * monthly),
            status=st_code,
            opt_mode=mode,
            semantic_score=opt_res.semantic_similarity or 0.0,
            net_energy_wh=thermo_res.net_energy_saved_wh,
            net_carbon_g=thermo_res.net_carbon_abated_gco2,
            water_saved_ml=thermo_res.net_water_saved_ml,
            routing_outcome=routing_rec.outcome.name,
            recommended_tier=routing_rec.recommended_model_tier or "NONE",
            latency_ms=latency_ms
        )
        console.print(f"\n[dim][Success] Recorded V2 optimization run into prompt_ledger.db (Record #{rid})[/dim]")


# Command aliases for seamless developer experience
main.add_command(analyze, name="review")
main.add_command(git_diff, name="diff")


if __name__ == "__main__":
    main()
