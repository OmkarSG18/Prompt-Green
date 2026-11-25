"""
PromptGreen v2.0 - Unified 4-Stage Active Pipeline Orchestrator (Stage 5)
End-to-End Prompt Optimization, Directive Shaping, and Semantic Fidelity Enforcement.

This module orchestrates the complete four-stage active prompt optimization pipeline:
    User Prompt
        │
        ▼
    Stage 1: Structural & Rule-Based Pruner (rule_pruner.py)
        │ - AST-based protection of code, JSON, YAML, XML, URLs, paths, constraints
        │ - Conservative removal of conversational greetings and closures
        ▼
    Stage 2: Extractive Token Compressor (compressor.py)
        │ - Microsoft LLMLingua-2 BERT classifier with deterministic CPU fallback
        │ - Natural-language token compression with immutable region preservation
        ▼
    Stage 3: Abstractive Output Directive Shaper (output_shaper.py)
        │ - Output format clarification (tables, JSON schemas, numbered lists)
        │ - Local SLM (Ollama) or deterministic rule-bounded templates
        ▼
    Stage 4: Semantic Fidelity Guardrail (semantic_guard.py)
        │ - Sentence-aware chunked all-MiniLM-L6-v2 cosine similarity validation
        │ - Strict instruction, negation, condition, number, and format preservation
        │ - Multi-chunk localized safety gating (prevents tail dilution)
        │ - Adaptive relaxation retry loop (aggressive -> balanced -> conservative -> rollback)
        ▼
    Optimized Prompt / Safe Rollback
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from promptgreen.optimizer.compressor import (
    CompressionResult,
    CompressorConfig,
    LLMLinguaCompressor,
    RETENTION_MODES,
)
from promptgreen.optimizer.output_shaper import (
    OutputDirectiveShaper,
    ShaperConfig,
    ShapingResult,
)
from promptgreen.optimizer.rule_pruner import (
    PruningResult,
    RuleBasedPruner,
)
from promptgreen.optimizer.semantic_guard import (
    GuardrailConfig,
    GuardrailResult,
    SemanticFidelityGuard,
)

logger = logging.getLogger("promptgreen.optimizer.pipeline")


@dataclass
class PipelineConfig:
    """
    Configuration options for the PromptGreen unified 4-stage active optimization pipeline.
    """
    mode: str = "balanced"  # "conservative", "balanced", "aggressive"
    enable_stage_1: bool = True  # Structural & Rule-Based Pruning
    enable_stage_2: bool = True  # Extractive Token Compression
    enable_stage_3: bool = True  # Output Directive Shaping
    enable_stage_4: bool = True  # Semantic Fidelity Guardrail & Recovery

    # Stage-specific sub-configurations (initialized with mode defaults if None)
    pruner_tokenizer_name: str = "cl100k_base"
    compressor_config: Optional[CompressorConfig] = None
    shaper_config: Optional[ShaperConfig] = None
    guardrail_config: Optional[GuardrailConfig] = None

    # Pipeline-level controls
    max_retries: int = 2
    pass_intermediate_stages: bool = True
    enforce_placeholder_cleanup: bool = True

    def __post_init__(self) -> None:
        valid_modes = {"conservative", "balanced", "aggressive"}
        if self.mode.lower() not in valid_modes:
            raise ValueError(
                f"Invalid pipeline mode '{self.mode}'. Must be one of: {sorted(list(valid_modes))}"
            )
        self.mode = self.mode.lower()

        # Instantiate sub-configurations if not explicitly provided
        if self.compressor_config is None:
            self.compressor_config = CompressorConfig(mode=self.mode)
        if self.shaper_config is None:
            self.shaper_config = ShaperConfig()
        if self.guardrail_config is None:
            self.guardrail_config = GuardrailConfig(mode=self.mode, max_retries=self.max_retries)


@dataclass
class StageExecution:
    """Detailed telemetry and execution record for an individual pipeline stage."""
    stage_id: int
    stage_name: str
    status: str  # "completed", "skipped", "fallback", "failed", "rolled_back"
    input_tokens: int
    output_tokens: int
    token_delta: int  # output_tokens - input_tokens
    latency_ms: float
    method_used: str
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """
    Comprehensive result object returned by the PromptGreen active optimization pipeline.
    Preserves intermediate outputs, stage telemetries, token counts, and safety metrics.
    """
    original_prompt: str
    final_prompt: str

    # Intermediate stage outputs
    stage_1_output: Optional[str] = None
    stage_2_output: Optional[str] = None
    stage_3_output: Optional[str] = None

    # Overall pipeline status
    success: bool = True
    accepted: bool = True
    rollback_occurred: bool = False
    rollback_stage: Optional[str] = None  # "none", "original", "stage_1", "stage_2"
    rollback_reason: Optional[str] = None

    # Optimization modes
    initial_mode: str = "balanced"
    final_mode: str = "balanced"

    # Token accounting (using single consistent tokenizer)
    original_token_count: int = 0
    final_token_count: int = 0
    net_token_reduction: int = 0  # original_token_count - final_token_count
    net_token_reduction_pct: float = 0.0
    is_exact_token_count: bool = True
    tokenizer_name: str = "cl100k_base"

    # Per-stage token counts
    stage_1_token_count: Optional[int] = None
    stage_2_token_count: Optional[int] = None
    stage_3_token_count: Optional[int] = None

    # Latencies
    stage_latencies_ms: Dict[str, float] = field(default_factory=dict)
    total_latency_ms: float = 0.0

    # Semantic validation metrics
    semantic_similarity: Optional[float] = None
    chunk_similarities: List[float] = field(default_factory=list)
    chunk_coverage: List[float] = field(default_factory=list)
    guardrail_passed: bool = True
    preservation_violations: List[str] = field(default_factory=list)

    # Adaptive retry telemetry
    retry_count: int = 0
    retry_history: List[Dict[str, Any]] = field(default_factory=list)

    # Detailed stage executions
    stage_executions: Dict[str, StageExecution] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    failure_reasons: List[str] = field(default_factory=list)

    # Academic semantic compliance & fallback tracking (Chapter 6, Section 6.3.2)
    fallback_type: str = "none"  # "none", "stage_2_compressed", "stage_1", "original"
    active_retention_rate: Optional[float] = None  # Compressor target retention rate (e.g. 0.40, 0.60, 0.80)
    compressor_retention_rate: Optional[float] = None  # Explicit compressor retention rate
    final_token_retention_ratio: Optional[float] = None  # Final prompt tokens / original tokens
    accepted_compressor_retention_rate: Optional[float] = None  # Rate of accepted compressor candidate (None if fallback/rollback/bypassed)
    last_compressor_attempt_retention_rate: Optional[float] = None  # Target rate of last compressor attempt (e.g. 0.40, 0.60, 0.80)
    core_similarity: Optional[float] = None

    @property
    def actual_retention_rate(self) -> Optional[float]:
        """Backward-compatible alias for final_token_retention_ratio."""
        return self.final_token_retention_ratio


# Alias for backward compatibility with v2 architecture plan
OptimizationResult = PipelineResult


class PromptGreenPipeline:
    """
    Unified PromptGreen v2.0 Four-Stage Active Optimization Pipeline.

    Orchestrates:
    1. Structural Pruning (`RuleBasedPruner`)
    2. Extractive Token Compression (`LLMLinguaCompressor`)
    3. Output Directive Shaping (`OutputDirectiveShaper`)
    4. Semantic Fidelity Guardrail (`SemanticFidelityGuard`)
    """

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        pruner: Optional[RuleBasedPruner] = None,
        compressor: Optional[LLMLinguaCompressor] = None,
        shaper: Optional[OutputDirectiveShaper] = None,
        guardrail: Optional[SemanticFidelityGuard] = None,
    ) -> None:
        self.config = config or PipelineConfig()

        # Stage 1: Structural Pruner
        self.pruner = pruner or RuleBasedPruner(tokenizer_name=self.config.pruner_tokenizer_name)

        # Stage 2: Extractive Token Compressor
        self.compressor = compressor or LLMLinguaCompressor(
            config=self.config.compressor_config,
            pruner=self.pruner,
        )

        # Stage 3: Output Directive Shaper
        self.shaper = shaper or OutputDirectiveShaper(
            config=self.config.shaper_config,
            pruner=self.pruner,
        )

        # Stage 4: Semantic Fidelity Guardrail
        self.guardrail = guardrail or SemanticFidelityGuard(
            config=self.config.guardrail_config,
        )

    # -------------------------------------------------------------------------
    # Internal Verification Helpers
    # -------------------------------------------------------------------------

    def _contains_internal_placeholders(self, text: str) -> bool:
        """Check if any internal protected placeholders exist in text."""
        placeholder_pattern = re.compile(
            r"__(?:CODE_BLOCK|INLINE_CODE|JSON_BLOCK|YAML_BLOCK|XML_BLOCK|URL|PATH|IDENTIFIER|NUM_CONSTRAINT|REQ_BLOCK|PROTECTED)_\d+(?:_\d+)?__"
        )
        return bool(placeholder_pattern.search(text))

    def _count_tokens(self, text: str) -> Tuple[int, bool]:
        """Unified token counting using the Stage 1 pruner tokenizer."""
        return self.pruner.count_tokens(text)

    # -------------------------------------------------------------------------
    # Core Pipeline Execution
    # -------------------------------------------------------------------------

    def optimize(
        self,
        prompt: str,
        mode: Optional[str] = None,
        enable_stage_1: Optional[bool] = None,
        enable_stage_2: Optional[bool] = None,
        enable_stage_3: Optional[bool] = None,
        enable_stage_4: Optional[bool] = None,
    ) -> PipelineResult:
        """
        Execute end-to-end active prompt optimization across all four stages.

        Args:
            prompt: Raw user input prompt string.
            mode: Optimization mode ("conservative", "balanced", "aggressive").
            enable_stage_1: Toggle for Stage 1 (pruner). Defaults to config.
            enable_stage_2: Toggle for Stage 2 (compressor). Defaults to config.
            enable_stage_3: Toggle for Stage 3 (shaper). Defaults to config.
            enable_stage_4: Toggle for Stage 4 (guardrail). Defaults to config.

        Returns:
            PipelineResult containing optimized prompt, intermediate stage outputs,
            token metrics, latencies, semantic similarities, and retry/rollback telemetry.
        """
        pipeline_start_time = time.perf_counter()
        active_mode = (mode or self.config.mode).lower()

        do_s1 = self.config.enable_stage_1 if enable_stage_1 is None else enable_stage_1
        do_s2 = self.config.enable_stage_2 if enable_stage_2 is None else enable_stage_2
        do_s3 = self.config.enable_stage_3 if enable_stage_3 is None else enable_stage_3
        do_s4 = self.config.enable_stage_4 if enable_stage_4 is None else enable_stage_4

        stage_executions: Dict[str, StageExecution] = {}
        stage_latencies: Dict[str, float] = {}
        warnings: List[str] = []
        failure_reasons: List[str] = []
        retry_history: List[Dict[str, Any]] = []

        # Handle empty or whitespace-only prompts
        if not prompt or not prompt.strip():
            total_lat = (time.perf_counter() - pipeline_start_time) * 1000.0
            return PipelineResult(
                original_prompt=prompt,
                final_prompt=prompt,
                stage_1_output=prompt if do_s1 else None,
                stage_2_output=prompt if do_s2 else None,
                stage_3_output=prompt if do_s3 else None,
                success=True,
                accepted=True,
                rollback_occurred=False,
                rollback_stage="none",
                rollback_reason=None,
                initial_mode=active_mode,
                final_mode=active_mode,
                original_token_count=0,
                final_token_count=0,
                net_token_reduction=0,
                net_token_reduction_pct=0.0,
                is_exact_token_count=True,
                tokenizer_name=self.pruner.tokenizer_name,
                stage_1_token_count=0 if do_s1 else None,
                stage_2_token_count=0 if do_s2 else None,
                stage_3_token_count=0 if do_s3 else None,
                stage_latencies_ms={},
                total_latency_ms=round(total_lat, 2),
                semantic_similarity=1.0,
                chunk_similarities=[],
                chunk_coverage=[],
                guardrail_passed=True,
                preservation_violations=[],
                retry_count=0,
                retry_history=[],
                stage_executions={},
                warnings=[],
                failure_reasons=[],
                fallback_type="none",
                active_retention_rate=None,
                compressor_retention_rate=None,
                final_token_retention_ratio=1.0,
                accepted_compressor_retention_rate=None,
                last_compressor_attempt_retention_rate=None,
                core_similarity=None,
            )

        # Baseline original prompt token count
        orig_tokens, is_exact_tokens = self._count_tokens(prompt)

        # =====================================================================
        # STAGE 1: Structural & Rule-Based Pruner
        # =====================================================================
        s1_input = prompt
        s1_output = prompt
        s1_tokens = orig_tokens

        if do_s1:
            t0 = time.perf_counter()
            try:
                pruner_res: PruningResult = self.pruner.prune(s1_input)
                s1_output = pruner_res.optimized_prompt
                s1_tokens, _ = self._count_tokens(s1_output)
                s1_lat = (time.perf_counter() - t0) * 1000.0
                stage_latencies["stage_1"] = round(s1_lat, 2)
                warnings.extend(pruner_res.warnings)

                stage_executions["stage_1"] = StageExecution(
                    stage_id=1,
                    stage_name="RuleBasedPruner",
                    status="completed",
                    input_tokens=orig_tokens,
                    output_tokens=s1_tokens,
                    token_delta=s1_tokens - orig_tokens,
                    latency_ms=round(s1_lat, 2),
                    method_used="structural_pruning",
                    warnings=pruner_res.warnings,
                    details={
                        "removed_phrases": pruner_res.removed_phrases,
                        "protected_regions_count": len(pruner_res.protected_regions),
                    },
                )
            except Exception as s1_exc:
                s1_lat = (time.perf_counter() - t0) * 1000.0
                s1_output = prompt  # Safe fallback to unpruned input
                s1_tokens = orig_tokens
                err_msg = f"Stage 1 execution error ({type(s1_exc).__name__}: {s1_exc}); falling back to raw input."
                warnings.append(err_msg)
                stage_executions["stage_1"] = StageExecution(
                    stage_id=1,
                    stage_name="RuleBasedPruner",
                    status="fallback",
                    input_tokens=orig_tokens,
                    output_tokens=orig_tokens,
                    token_delta=0,
                    latency_ms=round(s1_lat, 2),
                    method_used="passthrough_fallback",
                    warnings=[err_msg],
                )
        else:
            stage_executions["stage_1"] = StageExecution(
                stage_id=1,
                stage_name="RuleBasedPruner",
                status="skipped",
                input_tokens=orig_tokens,
                output_tokens=orig_tokens,
                token_delta=0,
                latency_ms=0.0,
                method_used="skipped",
            )

        # =====================================================================
        # STAGE 2: Extractive Token Compression
        # =====================================================================
        s2_input = s1_output
        s2_output = s1_output
        s2_tokens = s1_tokens

        if do_s2:
            t0 = time.perf_counter()
            try:
                comp_res: CompressionResult = self.compressor.compress(s2_input, mode=active_mode)
                s2_output = comp_res.compressed_prompt
                s2_tokens, _ = self._count_tokens(s2_output)
                s2_lat = (time.perf_counter() - t0) * 1000.0
                stage_latencies["stage_2"] = round(s2_lat, 2)
                warnings.extend(comp_res.warnings)

                method_label = comp_res.compression_method
                status_label = "fallback" if comp_res.fallback_used else "completed"

                stage_executions["stage_2"] = StageExecution(
                    stage_id=2,
                    stage_name="LLMLinguaCompressor",
                    status=status_label,
                    input_tokens=s1_tokens,
                    output_tokens=s2_tokens,
                    token_delta=s2_tokens - s1_tokens,
                    latency_ms=round(s2_lat, 2),
                    method_used=method_label,
                    warnings=comp_res.warnings,
                    details={
                        "target_retention_rate": comp_res.retention_rate,
                        "compressor_retention_rate": comp_res.retention_rate,
                        "fallback_used": comp_res.fallback_used,
                        "model_available": comp_res.model_available,
                    },
                )
            except Exception as s2_exc:
                s2_lat = (time.perf_counter() - t0) * 1000.0
                s2_output = s1_output  # Safe fallback to Stage 1 output
                s2_tokens = s1_tokens
                err_msg = f"Stage 2 execution error ({type(s2_exc).__name__}: {s2_exc}); falling back to Stage 1 output."
                warnings.append(err_msg)
                stage_executions["stage_2"] = StageExecution(
                    stage_id=2,
                    stage_name="LLMLinguaCompressor",
                    status="fallback",
                    input_tokens=s1_tokens,
                    output_tokens=s1_tokens,
                    token_delta=0,
                    latency_ms=round(s2_lat, 2),
                    method_used="stage1_fallback",
                    warnings=[err_msg],
                )
        else:
            stage_executions["stage_2"] = StageExecution(
                stage_id=2,
                stage_name="LLMLinguaCompressor",
                status="skipped",
                input_tokens=s1_tokens,
                output_tokens=s1_tokens,
                token_delta=0,
                latency_ms=0.0,
                method_used="skipped",
            )

        # =====================================================================
        # STAGE 3: Abstractive Output Directive Shaper
        # =====================================================================
        s3_input = s2_output
        s3_output = s2_output
        s3_tokens = s2_tokens

        if do_s3:
            t0 = time.perf_counter()
            try:
                shaper_res: ShapingResult = self.shaper.shape(s3_input)
                s3_output = shaper_res.shaped_prompt
                s3_tokens, _ = self._count_tokens(s3_output)
                s3_lat = (time.perf_counter() - t0) * 1000.0
                stage_latencies["stage_3"] = round(s3_lat, 2)
                warnings.extend(shaper_res.warnings)

                method_label = shaper_res.shaping_method
                status_label = "completed" if shaper_res.shaping_applied else "completed_noop"

                stage_executions["stage_3"] = StageExecution(
                    stage_id=3,
                    stage_name="OutputDirectiveShaper",
                    status=status_label,
                    input_tokens=s2_tokens,
                    output_tokens=s3_tokens,
                    token_delta=s3_tokens - s2_tokens,
                    latency_ms=round(s3_lat, 2),
                    method_used=method_label,
                    warnings=shaper_res.warnings,
                    details={
                        "shaping_applied": shaper_res.shaping_applied,
                        "fallback_reason": shaper_res.fallback_reason,
                        "model_name": shaper_res.model_name,
                    },
                )
            except Exception as s3_exc:
                s3_lat = (time.perf_counter() - t0) * 1000.0
                s3_output = s2_output  # Safe fallback to Stage 2 output
                s3_tokens = s2_tokens
                err_msg = f"Stage 3 execution error ({type(s3_exc).__name__}: {s3_exc}); preserving Stage 2 output."
                warnings.append(err_msg)
                stage_executions["stage_3"] = StageExecution(
                    stage_id=3,
                    stage_name="OutputDirectiveShaper",
                    status="fallback",
                    input_tokens=s2_tokens,
                    output_tokens=s2_tokens,
                    token_delta=0,
                    latency_ms=round(s3_lat, 2),
                    method_used="stage2_fallback",
                    warnings=[err_msg],
                )
        else:
            stage_executions["stage_3"] = StageExecution(
                stage_id=3,
                stage_name="OutputDirectiveShaper",
                status="skipped",
                input_tokens=s2_tokens,
                output_tokens=s2_tokens,
                token_delta=0,
                latency_ms=0.0,
                method_used="skipped",
            )

        # =====================================================================
        # STAGE 4: Semantic Fidelity Guardrail & Adaptive Recovery Loop
        # =====================================================================
        candidate_to_verify = s3_output
        final_prompt = candidate_to_verify
        accepted = True
        rollback_occurred = False
        rollback_stage = "none"
        rollback_reason = None
        current_mode = active_mode
        retry_count = 0
        similarity_score: Optional[float] = None
        chunk_sims: List[float] = []
        chunk_cov: List[float] = []
        preservation_violations: List[str] = []
        fallback_type: str = "none"
        active_retention_rate: Optional[float] = None
        last_comp_rate: Optional[float] = None
        accepted_comp_rate: Optional[float] = None
        core_similarity: Optional[float] = None

        if do_s4:
            t0 = time.perf_counter()

            # Intermediate stage candidates for Stage 4 directive disambiguation and tracking
            intermediate_stages: Dict[str, str] = {}
            if self.config.pass_intermediate_stages:
                if do_s1:
                    intermediate_stages["stage_1"] = s1_output
                if do_s2:
                    intermediate_stages["stage_2"] = s2_output
                if do_s3:
                    intermediate_stages["stage_3"] = s3_output

            # Adaptive relaxation callback: regenerates from Stage 2 with academic retention sequence
            # Section 6.3.2: tau = 0.40 -> 0.60 -> 0.80
            def pipeline_retry_callback(relaxed_mode: str, iteration: int) -> str:
                nonlocal current_mode, retry_count
                current_mode = relaxed_mode
                retry_count = iteration

                # Map academic retention sequence tau: 0.40 -> 0.60 -> 0.80
                target_tau = RETENTION_MODES.get(relaxed_mode, 0.80)

                # Re-run Stage 2 with relaxed mode and explicit target retention rate
                t_retry_start = time.perf_counter()
                if do_s2:
                    retry_comp = self.compressor.compress(
                        s1_output,
                        mode=relaxed_mode,
                        target_retention_rate=target_tau,
                    )
                    relaxed_s2 = retry_comp.compressed_prompt
                else:
                    relaxed_s2 = s1_output

                # Re-run Stage 3 on relaxed compressed prompt
                if do_s3:
                    retry_shaper = self.shaper.shape(relaxed_s2)
                    new_candidate = retry_shaper.shaped_prompt
                else:
                    new_candidate = relaxed_s2

                retry_lat = (time.perf_counter() - t_retry_start) * 1000.0
                cand_tok, _ = self._count_tokens(new_candidate)
                retry_history.append({
                    "iteration": iteration,
                    "relaxed_mode": relaxed_mode,
                    "retention_rate": target_tau,
                    "candidate_tokens": cand_tok,
                    "latency_ms": round(retry_lat, 2),
                })
                return new_candidate

            try:
                guard_res: GuardrailResult = self.guardrail.evaluate(
                    original_prompt=prompt,
                    candidate_prompt=candidate_to_verify,
                    intermediate_stages=intermediate_stages,
                    retry_callback=pipeline_retry_callback,
                )

                s4_lat = (time.perf_counter() - t0) * 1000.0
                stage_latencies["stage_4"] = round(s4_lat, 2)

                final_prompt = guard_res.final_prompt
                accepted = guard_res.passed
                rollback_occurred = guard_res.rollback_occurred
                rollback_stage = guard_res.rollback_stage or ("original" if not accepted else "none")
                similarity_score = guard_res.similarity_score
                chunk_sims = guard_res.chunk_similarities
                chunk_cov = getattr(guard_res, "chunk_coverage", [])
                preservation_violations = guard_res.preservation_violations
                failure_reasons.extend(guard_res.failure_reasons)
                current_mode = guard_res.final_mode or current_mode
                retry_count = guard_res.retry_count
                fallback_type = getattr(guard_res, "fallback_type", "none")
                core_similarity = getattr(guard_res, "core_similarity", None)
                active_retention_rate = getattr(guard_res, "active_retention_rate", None)
                if do_s2:
                    last_comp_rate = getattr(guard_res, "last_compressor_attempt_retention_rate", active_retention_rate)
                    accepted_comp_rate = getattr(guard_res, "accepted_compressor_retention_rate", None)
                    if rollback_stage in ("stage_1", "original") or not accepted:
                        accepted_comp_rate = None
                else:
                    last_comp_rate = None
                    accepted_comp_rate = None

                if not accepted:
                    rollback_reason = "; ".join(guard_res.failure_reasons) or "Semantic similarity or preservation check failed."

                stage_executions["stage_4"] = StageExecution(
                    stage_id=4,
                    stage_name="SemanticFidelityGuard",
                    status="completed" if accepted else "rolled_back",
                    input_tokens=s3_tokens,
                    output_tokens=self._count_tokens(final_prompt)[0],
                    token_delta=self._count_tokens(final_prompt)[0] - s3_tokens,
                    latency_ms=round(s4_lat, 2),
                    method_used="all-MiniLM-L6-v2_cosine",
                    warnings=guard_res.failure_reasons,
                    details={
                        "similarity_score": similarity_score,
                        "active_threshold": guard_res.active_threshold,
                        "retry_count": retry_count,
                        "rollback_occurred": rollback_occurred,
                        "preservation_violations": preservation_violations,
                        "chunk_similarities": chunk_sims,
                        "chunk_coverage": chunk_cov,
                        "fallback_type": fallback_type,
                        "core_similarity": core_similarity,
                        "active_retention_rate": last_comp_rate,
                        "compressor_retention_rate": accepted_comp_rate,
                        "accepted_compressor_retention_rate": accepted_comp_rate,
                        "last_compressor_attempt_retention_rate": last_comp_rate,
                        "final_token_retention_ratio": round(self._count_tokens(final_prompt)[0] / orig_tokens, 4) if orig_tokens > 0 else 1.0,
                    },
                )
            except Exception as s4_exc:
                s4_lat = (time.perf_counter() - t0) * 1000.0
                stage_latencies["stage_4"] = round(s4_lat, 2)
                final_prompt = prompt  # Emergency safe rollback to original prompt
                accepted = False
                rollback_occurred = True
                rollback_stage = "original"
                fallback_type = "original"
                err_msg = f"Stage 4 execution error ({type(s4_exc).__name__}: {s4_exc}); safely rolling back to original prompt."
                rollback_reason = err_msg
                failure_reasons.append(err_msg)
                stage_executions["stage_4"] = StageExecution(
                    stage_id=4,
                    stage_name="SemanticFidelityGuard",
                    status="failed",
                    input_tokens=s3_tokens,
                    output_tokens=orig_tokens,
                    token_delta=orig_tokens - s3_tokens,
                    latency_ms=round(s4_lat, 2),
                    method_used="exception_rollback",
                    warnings=[err_msg],
                )
        else:
            stage_executions["stage_4"] = StageExecution(
                stage_id=4,
                stage_name="SemanticFidelityGuard",
                status="skipped",
                input_tokens=s3_tokens,
                output_tokens=s3_tokens,
                token_delta=0,
                latency_ms=0.0,
                method_used="skipped",
            )
            final_prompt = candidate_to_verify

        # =====================================================================
        # POST-OPTIMIZATION: Placeholder Cleanup & Token Accounting
        # =====================================================================
        # Verify that internal placeholders are never leaked to user
        if self.config.enforce_placeholder_cleanup and self._contains_internal_placeholders(final_prompt):
            logger.warning("Unrestored internal placeholder detected in final prompt; rolling back to raw original prompt.")
            final_prompt = prompt
            accepted = False
            rollback_occurred = True
            rollback_stage = "original"
            err_msg = "Unrestored internal placeholder detected; safety rollback executed."
            rollback_reason = err_msg
            failure_reasons.append(err_msg)

        final_tokens, _ = self._count_tokens(final_prompt)
        net_reduction = orig_tokens - final_tokens
        net_reduction_pct = (net_reduction / orig_tokens * 100.0) if orig_tokens > 0 else 0.0

        # =====================================================================
        # OPTIMIZATION USEFULNESS GUARD: Prevent Token Expansion
        # =====================================================================
        # A candidate that expands token count fails the primary optimization goal.
        # Safely roll back to original prompt and record the accurate rollback reason.
        if accepted and net_reduction < 0:
            logger.warning(
                f"Optimization candidate increased token count from {orig_tokens} to {final_tokens} "
                f"(delta: {net_reduction}); rolling back to original prompt."
            )
            candidate_expanded_tokens = final_tokens
            final_prompt = prompt
            final_tokens = orig_tokens
            net_reduction = 0
            net_reduction_pct = 0.0
            accepted = False
            rollback_occurred = True
            rollback_stage = "original"
            err_msg = (
                f"Optimization candidate increased token count from {orig_tokens} to "
                f"{candidate_expanded_tokens} (net delta: {orig_tokens - candidate_expanded_tokens}); "
                f"safety rollback to original prompt executed."
            )
            rollback_reason = err_msg
            failure_reasons.append(err_msg)

        total_pipeline_latency_ms = (time.perf_counter() - pipeline_start_time) * 1000.0

        return PipelineResult(
            original_prompt=prompt,
            final_prompt=final_prompt,
            stage_1_output=s1_output if do_s1 else None,
            stage_2_output=s2_output if do_s2 else None,
            stage_3_output=s3_output if do_s3 else None,
            success=True,
            accepted=accepted,
            rollback_occurred=rollback_occurred,
            rollback_stage=rollback_stage,
            rollback_reason=rollback_reason,
            initial_mode=active_mode,
            final_mode=current_mode,
            original_token_count=orig_tokens,
            final_token_count=final_tokens,
            net_token_reduction=net_reduction,
            net_token_reduction_pct=round(net_reduction_pct, 2),
            is_exact_token_count=is_exact_tokens,
            tokenizer_name=self.pruner.tokenizer_name,
            stage_1_token_count=s1_tokens if do_s1 else None,
            stage_2_token_count=s2_tokens if do_s2 else None,
            stage_3_token_count=s3_tokens if do_s3 else None,
            stage_latencies_ms=stage_latencies,
            total_latency_ms=round(total_pipeline_latency_ms, 2),
            semantic_similarity=similarity_score,
            chunk_similarities=chunk_sims,
            chunk_coverage=chunk_cov,
            guardrail_passed=accepted,
            preservation_violations=preservation_violations,
            retry_count=retry_count,
            retry_history=retry_history,
            stage_executions=stage_executions,
            warnings=warnings,
            failure_reasons=failure_reasons,
            fallback_type=fallback_type,
            active_retention_rate=last_comp_rate,
            compressor_retention_rate=accepted_comp_rate,
            accepted_compressor_retention_rate=accepted_comp_rate,
            last_compressor_attempt_retention_rate=last_comp_rate,
            final_token_retention_ratio=round(final_tokens / orig_tokens, 4) if orig_tokens > 0 else 1.0,
            core_similarity=core_similarity,
        )


# Alias for roadmap compatibility
PromptGreenOptimizer = PromptGreenPipeline


def optimize_prompt(
    prompt: str,
    mode: str = "balanced",
    enable_stage_1: bool = True,
    enable_stage_2: bool = True,
    enable_stage_3: bool = True,
    enable_stage_4: bool = True,
    max_retries: int = 2,
    pipeline: Optional[PromptGreenPipeline] = None,
) -> PipelineResult:
    """
    Public top-level helper to optimize a prompt through the unified PromptGreen pipeline.

    Args:
        prompt: Raw user input prompt string.
        mode: Optimization mode ("conservative", "balanced", "aggressive").
        enable_stage_1: Toggle for Stage 1 structural pruner.
        enable_stage_2: Toggle for Stage 2 extractive compressor.
        enable_stage_3: Toggle for Stage 3 output directive shaper.
        enable_stage_4: Toggle for Stage 4 semantic fidelity guardrail.
        max_retries: Max relaxation retries for Stage 4.
        pipeline: Optional pre-configured PromptGreenPipeline instance.

    Returns:
        PipelineResult with optimized prompt and complete telemetry.
    """
    if pipeline is None:
        cfg = PipelineConfig(
            mode=mode,
            enable_stage_1=enable_stage_1,
            enable_stage_2=enable_stage_2,
            enable_stage_3=enable_stage_3,
            enable_stage_4=enable_stage_4,
            max_retries=max_retries,
        )
        pipeline = PromptGreenPipeline(config=cfg)

    return pipeline.optimize(
        prompt=prompt,
        mode=mode,
        enable_stage_1=enable_stage_1,
        enable_stage_2=enable_stage_2,
        enable_stage_3=enable_stage_3,
        enable_stage_4=enable_stage_4,
    )
