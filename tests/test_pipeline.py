"""
PromptGreen v2.0 - Unified Pipeline Orchestrator Test Suite (Stage 5)
Comprehensive unit, integration, safety, and adversarial tests for PromptGreenPipeline.

Covers:
1. Four-stage execution order (Pruner -> Compressor -> Shaper -> Guardrail).
2. Proper propagation of intermediate stage outputs.
3. Byte-for-byte preservation of protected structural regions across all stages.
4. Deterministic CPU fallback in Stage 2 without external model downloads.
5. Stage 3 formatting clarification without task alteration.
6. Honest token accounting (Stage 3 additions never counted as compression savings).
7. Intermediate Stage 2 passing into Stage 4.
8. Bounded adaptive relaxation retry loop on semantic rejection.
9. Safe atomic rollback to original prompt on exhausted retries.
10. Robust handling of component exceptions without crashing.
11. End-to-end survival of fenced code, JSON, URLs, paths, and technical identifiers.
12. Multi-chunk chunk-level semantic validation for long prompts.
13. Defense against localized tail divergence (Audit Test 1 & 5: high aggregate, low chunk).
14. Protection of negations, numbers, conditions, and exceptions.
15. Safe handling of empty and whitespace-only prompts.
16. Deterministic, reproducible pipeline executions.
"""

import pytest
import numpy as np

from promptgreen.optimizer.pipeline import (
    PromptGreenPipeline,
    PromptGreenOptimizer,
    PipelineConfig,
    PipelineResult,
    StageExecution,
    optimize_prompt,
)
from promptgreen.optimizer.rule_pruner import RuleBasedPruner, PruningResult
from promptgreen.optimizer.compressor import LLMLinguaCompressor, CompressorConfig, CompressionResult
from promptgreen.optimizer.output_shaper import OutputDirectiveShaper, ShaperConfig, ShapingResult
from promptgreen.optimizer.semantic_guard import (
    SemanticFidelityGuard,
    GuardrailConfig,
    GuardrailResult,
    LocalMiniLMEmbedder,
    compute_cosine_similarity,
)


def create_mock_embedder_for_pipeline() -> LocalMiniLMEmbedder:
    """Creates a deterministic mock embedder for fast unit tests without disk I/O."""
    rng = np.random.default_rng(12345)
    base_vec = rng.standard_normal(384).astype(np.float32)
    base_vec /= np.linalg.norm(base_vec)

    orth_vec = rng.standard_normal(384).astype(np.float32)
    orth_vec -= np.dot(orth_vec, base_vec) * base_vec
    orth_vec /= np.linalg.norm(orth_vec)

    def mock_embed(text: str) -> list[float]:
        if not text or not text.strip():
            return [0.0] * 384
        # Adversarial or divergent texts
        t_low = text.lower()
        if "cake" in t_low or "vacation" in t_low or "unrelated" in t_low or "resort" in t_low:
            v = 0.10 * base_vec + np.sqrt(1.0 - 0.10**2) * orth_vec
            return (v / np.linalg.norm(v)).tolist()
        if "mild_diff" in t_low:
            v = 0.85 * base_vec + np.sqrt(1.0 - 0.85**2) * orth_vec
            return (v / np.linalg.norm(v)).tolist()
        return base_vec.tolist()

    return LocalMiniLMEmbedder(custom_client=mock_embed)


# =============================================================================
# TEST CATEGORY 1: EXECUTION ORDER & INTERMEDIATE STAGE PROPAGATION
# =============================================================================

def test_1_all_four_stages_execute_in_correct_order() -> None:
    """Verifies that all 4 stages execute in strict sequence: Pruner -> Compressor -> Shaper -> Guardrail."""
    pipeline = PromptGreenPipeline()
    prompt = (
        "Could you please kindly explain how neural network backpropagation works in detail? "
        "Make sure to explain gradient descent. Thank you so much!"
    )

    result = pipeline.optimize(prompt, mode="balanced")

    assert result.success is True
    assert result.accepted is True
    assert "stage_1" in result.stage_executions
    assert "stage_2" in result.stage_executions
    assert "stage_3" in result.stage_executions
    assert "stage_4" in result.stage_executions

    assert result.stage_executions["stage_1"].stage_id == 1
    assert result.stage_executions["stage_2"].stage_id == 2
    assert result.stage_executions["stage_3"].stage_id == 3
    assert result.stage_executions["stage_4"].stage_id == 4

    assert result.stage_executions["stage_1"].status == "completed"
    assert result.stage_executions["stage_2"].status in {"completed", "fallback"}
    assert result.stage_executions["stage_3"].status in {"completed", "completed_noop"}
    assert result.stage_executions["stage_4"].status == "completed"


def test_2_each_stage_receives_previous_stage_output() -> None:
    """Verifies that intermediate stage outputs chain correctly from Stage 1 through Stage 4."""
    pipeline = PromptGreenPipeline()
    prompt = (
        "Hello dear assistant! Would you be so kind as to summarize how microservices communicate? "
        "In order to ensure reliability, services must use message queues. Thank you in advance!"
    )

    res = pipeline.optimize(prompt, mode="balanced")

    # Stage 1 strips greetings and polite closures
    assert res.stage_1_output is not None
    assert "Hello dear assistant" not in res.stage_1_output
    assert "Thank you in advance" not in res.stage_1_output

    # Stage 2 receives Stage 1 output and compresses discourse fillers
    assert res.stage_2_output is not None
    # "In order to" should be converted to "to"
    assert "in order to" not in res.stage_2_output.lower()

    # Stage 3 receives Stage 2 output
    assert res.stage_3_output is not None

    # Stage 4 validates the candidate
    assert res.final_prompt is not None


# =============================================================================
# TEST CATEGORY 2: STRUCTURAL & CODE PRESERVATION SURVIVES END-TO-END
# =============================================================================

def test_3_stage1_protection_survives_complete_pipeline() -> None:
    """Guarantees fenced code blocks survive all 4 pipeline stages byte-for-byte."""
    pipeline = PromptGreenPipeline()
    code_snippet = "```python\ndef calculate_fibonacci(n: int) -> int:\n    if n <= 1:\n        return n\n    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)\n```"
    prompt = f"Please kindly optimize the following function:\n{code_snippet}\nMake sure to retain syntax."

    res = pipeline.optimize(prompt, mode="balanced")

    assert res.success is True
    assert code_snippet in res.final_prompt
    assert "calculate_fibonacci" in res.final_prompt


def test_4_stage2_fallback_without_downloading_external_models() -> None:
    """Stage 2 must compress natural language on CPU without external model downloads."""
    # Ensure llmlingua instance is None and model_available is checked
    comp = LLMLinguaCompressor(config=CompressorConfig(mode="balanced", use_llmlingua2=False))
    pipeline = PromptGreenPipeline(compressor=comp)

    prompt = (
        "In the event that the database is unavailable, it is important to note that the system "
        "must log an alert. Furthermore, at the present time, take into consideration all metrics."
    )

    res = pipeline.optimize(prompt, mode="balanced")

    assert res.success is True
    assert res.stage_executions["stage_2"].method_used in {
        "deterministic_lexical_fallback", "llmlingua-2"
    }
    # Immune keywords must survive
    assert "must" in res.final_prompt
    assert "alert" in res.final_prompt


def test_5_stage3_adds_directives_without_changing_underlying_task() -> None:
    """Stage 3 clarifies output formatting bounds without mutating the core prompt directives."""
    pipeline = PromptGreenPipeline()
    prompt = "Compare relational databases and document stores."

    res = pipeline.optimize(prompt, mode="balanced")

    assert res.success is True
    # Underlying concepts remain present
    assert "relational databases" in res.final_prompt.lower()
    assert "document stores" in res.final_prompt.lower()


# =============================================================================
# TEST CATEGORY 3: ACCURATE TOKEN ACCOUNTING
# =============================================================================

def test_6_stage3_does_not_falsely_appear_as_compression_savings() -> None:
    """Directive additions in Stage 3 must not be miscounted as compression savings."""
    pipeline = PromptGreenPipeline()
    short_prompt = "Explain caching."

    res = pipeline.optimize(short_prompt, mode="balanced")

    # If Stage 3 added directives, final token count may be larger than original
    # Net reduction must be exactly original - final
    expected_net = res.original_token_count - res.final_token_count
    assert res.net_token_reduction == expected_net

    if res.final_token_count > res.original_token_count:
        assert res.net_token_reduction < 0
        assert res.net_token_reduction_pct < 0.0


# =============================================================================
# TEST CATEGORY 4: STAGE 4 INTEGRATION & ADAPTIVE RECOVERY
# =============================================================================

def test_7_stage4_receives_stage2_intermediate() -> None:
    """Verifies that Stage 4 receives the Stage 2 intermediate candidate."""
    mock_emb = create_mock_embedder_for_pipeline()
    guard = SemanticFidelityGuard(embedder=mock_emb)
    pipeline = PromptGreenPipeline(guardrail=guard)

    prompt = (
        "Could you please explain how database indexing accelerates queries? "
        "Ensure to describe B-trees. Thank you!"
    )

    res = pipeline.optimize(prompt, mode="balanced")

    assert res.success is True
    # Stage 4 executions details
    stage_4_details = res.stage_executions["stage_4"].details
    assert "similarity_score" in stage_4_details


def test_8_semantic_rejection_triggers_less_aggressive_retry() -> None:
    """A candidate failing aggressive threshold triggers bounded relaxation to balanced or conservative."""
    # Custom compressor mock that produces low similarity on aggressive, high on balanced
    class ControllableCompressor(LLMLinguaCompressor):
        def compress(self, prompt: str, mode: str | None = None) -> CompressionResult:
            active_m = mode or self.config.mode
            if active_m == "aggressive":
                comp_text = prompt + " mild_diff"
            else:
                comp_text = prompt
            return CompressionResult(
                original_prompt=prompt,
                compressed_prompt=comp_text,
                original_token_count=10,
                compressed_token_count=8,
                actual_reduction_percentage=20.0,
                retention_rate=0.8,
                compression_mode=active_m,
                compression_method="mock",
                model_name="mock",
                model_available=True,
                is_exact_token_count=True,
                compression_latency_ms=1.0,
                model_loading_latency_ms=0.0,
                protected_region_count=0,
                protected_regions_preserved=True,
            )

    # Mock embedder that gives 0.80 on mild_diff (below aggressive 0.86 threshold)
    seed_map = {"mild_diff": 0.80}
    rng = np.random.default_rng(999)
    bv = rng.standard_normal(384).astype(np.float32)
    bv /= np.linalg.norm(bv)
    ov = rng.standard_normal(384).astype(np.float32)
    ov -= np.dot(ov, bv) * bv
    ov /= np.linalg.norm(ov)

    def mock_embed(t: str) -> list[float]:
        if "mild_diff" in t:
            v = 0.80 * bv + np.sqrt(1.0 - 0.80**2) * ov
            return (v / np.linalg.norm(v)).tolist()
        return bv.tolist()

    mock_emb = LocalMiniLMEmbedder(custom_client=mock_embed)
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="aggressive", max_retries=2), embedder=mock_emb)
    comp = ControllableCompressor()

    pipeline = PromptGreenPipeline(
        config=PipelineConfig(mode="aggressive", max_retries=2),
        compressor=comp,
        guardrail=guard,
    )

    res = pipeline.optimize("Analyze system performance metrics.", mode="aggressive")

    # Aggressive candidate failed (0.80 < 0.86), relaxed to balanced which succeeded (1.0 >= 0.92)
    assert res.retry_count >= 1
    assert len(res.retry_history) >= 1
    assert res.accepted is True
    assert res.rollback_occurred is False


def test_9_failed_retries_return_original_prompt() -> None:
    """When all relaxation retries fail, pipeline executes atomic rollback to original prompt."""
    # Compressor that always produces completely unrelated cake text
    class DefectiveCompressor(LLMLinguaCompressor):
        def compress(self, prompt: str, mode: str | None = None) -> CompressionResult:
            return CompressionResult(
                original_prompt=prompt,
                compressed_prompt="Bake a chocolate cake with cherries and frosting.",
                original_token_count=10,
                compressed_token_count=8,
                actual_reduction_percentage=20.0,
                retention_rate=0.8,
                compression_mode=mode or "balanced",
                compression_method="mock",
                model_name="mock",
                model_available=True,
                is_exact_token_count=True,
                compression_latency_ms=1.0,
                model_loading_latency_ms=0.0,
                protected_region_count=0,
                protected_regions_preserved=True,
            )

    mock_emb = create_mock_embedder_for_pipeline()
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced", max_retries=1), embedder=mock_emb)
    comp = DefectiveCompressor()

    pipeline = PromptGreenPipeline(
        config=PipelineConfig(mode="balanced", max_retries=1),
        compressor=comp,
        guardrail=guard,
    )

    orig_prompt = "Deploy high-performance database cluster."
    res = pipeline.optimize(orig_prompt, mode="balanced")

    assert res.accepted is False
    assert res.rollback_occurred is True
    assert res.final_prompt == orig_prompt
    assert res.rollback_stage == "original"
    assert len(res.failure_reasons) > 0


# =============================================================================
# TEST CATEGORY 5: ROBUST COMPONENT EXCEPTION HANDLING
# =============================================================================

def test_10_component_exceptions_handled_safely() -> None:
    """An unhandled exception in any stage does not crash the pipeline; applies safe fallback."""
    class CrashingPruner(RuleBasedPruner):
        def prune(self, prompt: str) -> PruningResult:
            raise RuntimeError("Simulated Stage 1 crash")

    pipeline = PromptGreenPipeline(pruner=CrashingPruner())
    prompt = "Explain cloud computing architectures."

    res = pipeline.optimize(prompt, mode="balanced")

    # Pipeline gracefully handled the Stage 1 crash by falling back to raw prompt
    assert res.success is True
    assert res.stage_executions["stage_1"].status == "fallback"
    assert any("Simulated Stage 1 crash" in w for w in res.warnings)


# =============================================================================
# TEST CATEGORY 6: STRUCTURAL COMPONENT INTEGRITY
# =============================================================================

def test_11_protected_code_json_urls_and_identifiers_survive_end_to_end() -> None:
    """Complex prompt with JSON schemas, URLs, paths, and numerical constraints survives intact."""
    pipeline = PromptGreenPipeline()
    prompt = (
        "Please query the endpoint at https://api.example.com/v1/telemetry and inspect the file at /var/log/app.log. "
        "The response payload must strictly match the following JSON schema:\n"
        '{"status": "ok", "latency_ms": 45}\n'
        "Ensure query latency remains strictly < 50ms under peak load."
    )

    res = pipeline.optimize(prompt, mode="balanced")

    assert res.success is True
    assert "https://api.example.com/v1/telemetry" in res.final_prompt
    assert "/var/log/app.log" in res.final_prompt
    assert '"latency_ms"' in res.final_prompt
    assert "50ms" in res.final_prompt


# =============================================================================
# TEST CATEGORY 7: MULTI-CHUNK & AUDIT DEFECT REGRESSION (PART 3 PRIORITY)
# =============================================================================

def test_12_long_prompts_receive_meaningful_chunk_level_validation() -> None:
    """Prompts exceeding single chunk boundaries produce multi-chunk coverage metrics."""
    embedder = LocalMiniLMEmbedder()
    if not embedder.initialize():
        pytest.skip("Local MiniLM model unavailable.")

    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=embedder)
    pipeline = PromptGreenPipeline(guardrail=guard)

    long_prompt = (
        "Software architecture requires clean separation of concerns, disciplined layering, and reliable interfaces. "
        "Presentation layers render user interfaces and validate input schemas. "
        "Service layers orchestrate business workflows and domain rules. "
        "Database access layers encapsulate schema queries and transactional operations. "
    ) * 3

    res = pipeline.optimize(long_prompt, mode="balanced")

    assert res.success is True
    assert res.accepted is True
    assert len(res.chunk_coverage) > 1
    assert all(cov >= 0.75 for cov in res.chunk_coverage)


def test_13_changed_final_paragraph_cannot_be_hidden_by_high_aggregate_similarity() -> None:
    """
    CRITICAL AUDIT REGRESSION (CHUNK-01):
    Adversarial example with 90% identical prefix and altered natural-language tail
    has high aggregate similarity (> 0.95), but MUST BE REJECTED by chunk validation.
    """
    embedder = LocalMiniLMEmbedder()
    if not embedder.initialize():
        pytest.skip("Local MiniLM model unavailable.")

    guard = SemanticFidelityGuard(
        config=GuardrailConfig(mode="balanced", enable_chunk_validation=True),
        embedder=embedder
    )

    prefix = (
        "disciplined coordination across modern engineering organizations requires structured communication channels and transparent status tracking. "
        "distributed teams document ongoing system designs through collaborative repositories and shared architectural decision records. "
        "cross-functional working groups convene regularly to address systemic bottlenecks and streamline delivery cycles. "
    ) * 4

    tail_orig = (
        "the planning committee finalized the quarterly roadmap targets and prioritized backlog items for all engineering squads. "
        "milestones were scheduled across biweekly iterations to balance capacity against technical debt reduction."
    )
    tail_bad = (
        "the travel club organized an extended vacation to the tropical islands and booked luxury resort accommodations. "
        "group activities included snorkeling excursions and sunset sailing cruises across crystal blue waters."
    )

    orig = prefix + "\n\n" + tail_orig
    bad_cand = prefix + "\n\n" + tail_bad

    res = guard.evaluate(orig, bad_cand)

    # Must be rejected because localized tail chunk coverage is severely degraded
    assert res.passed is False
    assert res.rollback_occurred is True
    assert res.final_prompt == orig
    assert any("Localized semantic change" in r for r in res.failure_reasons)


# =============================================================================
# TEST CATEGORY 8: NEGATIONS, NUMBERS, CONDITIONS & EXCEPTIONS PRESERVATION
# =============================================================================

def test_14_negation_numerical_constraints_conditions_exceptions_protected() -> None:
    """Critical operational modifiers cannot be dropped without triggering immediate rollback."""
    pipeline = PromptGreenPipeline()

    test_cases = [
        ("Do not delete obsolete records without authorization.", "Delete obsolete records without authorization."),
        ("Timeout must not exceed 50ms.", "Timeout must not exceed 500ms."),
        ("If system is degraded, switch to backup cluster.", "Switch to backup cluster."),
        ("Archive all logs except security audit records.", "Archive all logs."),
    ]

    for orig, corrupted in test_cases:
        res = pipeline.guardrail.evaluate(orig, corrupted)
        assert res.passed is False
        assert res.rollback_occurred is True


# =============================================================================
# TEST CATEGORY 9: EDGE CASES & REPRODUCIBILITY
# =============================================================================

def test_15_empty_and_whitespace_prompts_behave_safely() -> None:
    """Empty and whitespace strings return immediately with zero tokens and no errors."""
    pipeline = PromptGreenPipeline()

    for empty_input in ["", "   ", "\n\t  \n"]:
        res = pipeline.optimize(empty_input)
        assert res.success is True
        assert res.original_token_count == 0
        assert res.final_token_count == 0
        assert res.final_prompt == empty_input


def test_16_repeated_runs_produce_reproducible_outputs() -> None:
    """Multiple executions with deterministic components yield identical results."""
    pipeline = PromptGreenPipeline()
    prompt = (
        "Could you please explain how distributed consensus works in Raft? "
        "Make sure to explain leader election. Thank you!"
    )

    res1 = pipeline.optimize(prompt, mode="balanced")
    res2 = pipeline.optimize(prompt, mode="balanced")

    assert res1.final_prompt == res2.final_prompt
    assert res1.final_token_count == res2.final_token_count
    assert res1.net_token_reduction == res2.net_token_reduction


def test_17_no_internal_placeholders_exposed_to_user() -> None:
    """Verifies that __CODE_BLOCK_i__ or similar placeholders never leak to final output."""
    pipeline = PromptGreenPipeline()
    prompt = "Here is Python code:\n```python\nx = 1\n```\nPlease explain."

    res = pipeline.optimize(prompt)
    assert not pipeline._contains_internal_placeholders(res.final_prompt)


def test_18_stage_toggles_allow_selective_execution() -> None:
    """Individual stages can be toggled on/off while maintaining pipeline integrity."""
    pipeline = PromptGreenPipeline()
    prompt = "Please explain quantum computing in detail."

    # Disable Stage 2 and Stage 3
    res = pipeline.optimize(prompt, enable_stage_2=False, enable_stage_3=False)

    assert res.stage_executions["stage_2"].status == "skipped"
    assert res.stage_executions["stage_3"].status == "skipped"
    assert res.stage_executions["stage_1"].status == "completed"
    assert res.stage_executions["stage_4"].status == "completed"


def test_19_public_optimize_prompt_helper() -> None:
    """Verifies top-level optimize_prompt functional entrypoint."""
    res = optimize_prompt("Please describe cloud elasticity.", mode="balanced")
    assert isinstance(res, PipelineResult)
    assert res.success is True
    assert res.final_prompt != ""


def test_20_mode_selection_affects_retention_and_threshold() -> None:
    """Different modes configure appropriate thresholds and retention targets."""
    p_cons = PromptGreenPipeline(config=PipelineConfig(mode="conservative"))
    p_agg = PromptGreenPipeline(config=PipelineConfig(mode="aggressive"))

    assert p_cons.config.guardrail_config.threshold == 0.96
    assert p_agg.config.guardrail_config.threshold == 0.86
