"""
PromptGreen v2.0 - Extractive Token Compressor (Stage 2)
Microsoft LLMLingua-2 Extractive Token Compression with Deterministic CPU Fallback.

This module implements the Stage 2 extractive token compressor for the PromptGreen
pipeline. It integrates seamlessly with Stage 1 structural protection (RuleBasedPruner),
isolating protected regions (code blocks, JSON, YAML, XML, URLs, file paths,
identifiers, numerical constraints) so that only eligible natural-language prose
is compressed.

When Microsoft LLMLingua-2 (or its BERT model) is unavailable or offline,
a deterministic information-density lexical pruner runs on CPU to achieve
meaning-preserving token reduction without compromising structural, conditional,
or negative instructions.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from promptgreen.optimizer.rule_pruner import ProtectedRegion, RuleBasedPruner

logger = logging.getLogger("promptgreen.optimizer.compressor")


# Default mode retention rate targets (Chapter 6, Section 6.3.2)
RETENTION_MODES: Dict[str, float] = {
    "conservative": 0.80,
    "balanced": 0.60,
    "aggressive": 0.40,
}

# Multi-word discourse filler replacements: patterns to replace with concise equivalents
DISCOURSE_REPLACEMENTS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\bin order to\b", re.IGNORECASE), "to"),
    (re.compile(r"\bat the present time\b", re.IGNORECASE), "currently"),
    (re.compile(r"\bdue to the fact that\b", re.IGNORECASE), "because"),
    (re.compile(r"\bfor the purpose of\b", re.IGNORECASE), "for"),
    (re.compile(r"\bin the event that\b", re.IGNORECASE), "if"),
    (re.compile(r"\bwith the exception of\b", re.IGNORECASE), "except"),
    (re.compile(r"\bas a matter of fact\b", re.IGNORECASE), ""),
    (re.compile(r"\btake into consideration\b", re.IGNORECASE), "consider"),
    (re.compile(r"\bit should be noted that\b", re.IGNORECASE), ""),
    (re.compile(r"\bit is important to note that\b", re.IGNORECASE), ""),
    (re.compile(r"\bkeep in mind that\b", re.IGNORECASE), ""),
    (re.compile(r"\bbe sure to\b", re.IGNORECASE), "ensure to"),
    (re.compile(r"\bmake sure to\b", re.IGNORECASE), "ensure to"),
    (re.compile(r"\bas well as\b", re.IGNORECASE), "and"),
    (re.compile(r"\bin addition to\b", re.IGNORECASE), "and"),
    (re.compile(r"\ba large number of\b", re.IGNORECASE), "many"),
    (re.compile(r"\ba wide variety of\b", re.IGNORECASE), "various"),
    (re.compile(r"\bprior to\b", re.IGNORECASE), "before"),
    (re.compile(r"\bsubsequent to\b", re.IGNORECASE), "after"),
    (re.compile(r"\bwith regard to\b", re.IGNORECASE), "regarding"),
    (re.compile(r"\bwith respect to\b", re.IGNORECASE), "regarding"),
    (re.compile(r"\bin view of the fact that\b", re.IGNORECASE), "since"),
    (re.compile(r"\bfor the reason that\b", re.IGNORECASE), "because"),
    (re.compile(r"\bis able to\b", re.IGNORECASE), "can"),
    (re.compile(r"\bhas the ability to\b", re.IGNORECASE), "can"),
    (re.compile(r"\bis capable of\b", re.IGNORECASE), "can"),
    (re.compile(r"\bis required to\b", re.IGNORECASE), "must"),
    (re.compile(r"\bhas to\b", re.IGNORECASE), "must"),
    (re.compile(r"\bought to\b", re.IGNORECASE), "should"),
]

# Strict immune words that MUST NEVER be pruned by the fallback compressor
IMMUNE_WORDS: Set[str] = {
    # Negations
    "not", "never", "no", "neither", "nor", "none", "without", "don't", "dont",
    "cannot", "can't", "cant", "won't", "wont", "shouldn't", "shouldnt",
    "mustn't", "mustnt", "doesn't", "doesnt", "isn't", "isnt", "aren't", "arent",
    "hardly", "scarcely", "barely",
    # Conditionals & Exceptions
    "if", "unless", "provided", "except", "excluding", "otherwise", "whether", "whenever",
    # Explicit requirements & Priorities
    "must", "shall", "required", "mandatory", "critical", "essential", "constraint",
    "strictly", "important", "warning", "caution", "only",
    # Key imperative action verbs
    "verify", "check", "implement", "ensure", "return", "create", "fix", "calculate",
    "optimize", "build", "test", "assert", "run", "validate", "analyze", "extract", "parse",
    "deploy", "configure", "update", "delete", "select", "insert"
}

# Weak adverbs / empty intensifiers (Priority 1 for pruning)
WEAK_ADVERBS: Set[str] = {
    "basically", "essentially", "actually", "virtually", "simply", "really",
    "just", "quite", "somewhat", "fairly", "overall", "relatively",
    "definitely", "certainly", "obviously", "clearly", "namely",
    "specifically", "particularly", "extremely", "very", "pretty", "generally"
}

# Low-entropy filler qualifiers (Priority 2 for pruning)
FILLER_QUALIFIERS: Set[str] = {
    "given", "aforesaid", "respective", "particular", "specific", "appropriate",
    "relevant", "various", "certain", "individual", "typical"
}

# Non-essential articles (Pruned only in Aggressive mode)
ARTICLES: Set[str] = {"the", "a", "an"}


@dataclass
class CompressorConfig:
    """Configuration options for the Stage 2 extractive token compressor."""
    mode: str = "balanced"
    target_retention_rate: Optional[float] = None
    model_name: str = "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank"
    device: str = "cpu"
    use_llmlingua2: bool = True
    enable_fallback: bool = True
    timeout_seconds: float = 30.0
    verify_restoration: bool = True
    preserve_sentence_structure: bool = True


@dataclass
class CompressionResult:
    """Comprehensive result object from the Stage 2 extractive compression process."""
    original_prompt: str
    compressed_prompt: str
    original_token_count: int
    compressed_token_count: int
    actual_reduction_percentage: float
    retention_rate: float
    compression_mode: str
    compression_method: str
    model_name: str
    model_available: bool
    is_exact_token_count: bool
    compression_latency_ms: float
    model_loading_latency_ms: float
    protected_region_count: int
    protected_regions_preserved: bool
    warnings: List[str] = field(default_factory=list)
    fallback_used: bool = False
    success: bool = True


class LLMLinguaCompressor:
    """
    Stage 2 Extractive Token Compressor.

    Combines Microsoft LLMLingua-2 with Stage 1 structural region isolation
    and provides a deterministic, CPU-compatible information-density fallback
    when neural models or packages are unavailable.
    """

    _shared_llm_lingua: Optional[Any] = None
    _shared_model_name: Optional[str] = None

    @classmethod
    def reset_shared_model(cls) -> None:
        """Reset the process-level shared LLMLingua model cache."""
        cls._shared_llm_lingua = None
        cls._shared_model_name = None

    @classmethod
    def prewarm(cls, model_name: str = "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank") -> bool:
        """Pre-warm and cache the shared LLMLingua-2 model."""
        if cls._shared_llm_lingua is not None:
            return True
        try:
            from llmlingua import PromptCompressor as LLMLinguaEngine
            cls._shared_llm_lingua = LLMLinguaEngine(
                model_name=model_name,
                device_map="cpu",
                use_llmlingua2=True,
            )
            cls._shared_model_name = model_name
            return True
        except Exception as exc:
            logger.debug(f"LLMLingua prewarm note: {exc}")
            return False

    def __init__(
        self,
        config: Optional[CompressorConfig] = None,
        pruner: Optional[RuleBasedPruner] = None,
        llm_lingua_instance: Optional[Any] = None,
    ) -> None:
        self.config = config or CompressorConfig()
        self.pruner = pruner or RuleBasedPruner()
        self._llm_lingua = llm_lingua_instance
        self._model_loaded = (llm_lingua_instance is not None)
        self._model_loading_latency_ms: float = 0.0
        self._model_available: bool = (llm_lingua_instance is not None)

    # -------------------------------------------------------------------------
    # Model Availability & Lazy Loading
    # -------------------------------------------------------------------------

    def is_model_available(self) -> bool:
        """
        Check if the LLMLingua library is installed AND if model weights exist
        locally in HuggingFace cache or a local directory, without triggering
        an automatic remote download.
        """
        if self._llm_lingua is not None:
            return True

        try:
            import llmlingua  # noqa: F401
            import transformers  # noqa: F401
        except ImportError:
            return False

        # Check local filesystem for model weights
        model_name = self.config.model_name
        if os.path.isdir(model_name):
            return True

        hf_hub_name = "models--" + model_name.replace("/", "--")
        cache_dirs = [
            os.path.expanduser("~/.cache/huggingface/hub"),
            os.environ.get("HF_HOME", ""),
            os.environ.get("TRANSFORMERS_CACHE", ""),
        ]
        for c_dir in cache_dirs:
            if not c_dir or not os.path.isdir(c_dir):
                continue
            target_dir = os.path.join(c_dir, hf_hub_name)
            if os.path.isdir(target_dir):
                snapshots_dir = os.path.join(target_dir, "snapshots")
                if os.path.isdir(snapshots_dir):
                    try:
                        if len(os.listdir(snapshots_dir)) > 0:
                            return True
                    except OSError:
                        pass

        return False

    def load_model(self) -> bool:
        """
        Lazily load the LLMLingua-2 model on CPU.
        Never crashes the application on failure.
        Records model loading latency in milliseconds.
        Reuses process-level shared instance to avoid repeated memory allocations.
        """
        if self._model_loaded and self._llm_lingua is not None:
            return True

        if (
            self.__class__._shared_llm_lingua is not None
            and self.__class__._shared_model_name == self.config.model_name
        ):
            self._llm_lingua = self.__class__._shared_llm_lingua
            self._model_loaded = True
            self._model_available = True
            self._model_loading_latency_ms = 0.0
            return True

        start_time = time.perf_counter()
        if not self.is_model_available():
            self._model_loading_latency_ms = (time.perf_counter() - start_time) * 1000.0
            self._model_available = False
            return False

        try:
            from llmlingua import PromptCompressor as LLMLinguaPromptCompressor

            self._llm_lingua = LLMLinguaPromptCompressor(
                model_name=self.config.model_name,
                device_map=self.config.device,
                use_llmlingua2=self.config.use_llmlingua2,
            )
            self.__class__._shared_llm_lingua = self._llm_lingua
            self.__class__._shared_model_name = self.config.model_name
            self._model_loaded = True
            self._model_available = True
            self._model_loading_latency_ms = (time.perf_counter() - start_time) * 1000.0
            return True
        except Exception as exc:
            self._model_loaded = False
            self._model_available = False
            self._model_loading_latency_ms = (time.perf_counter() - start_time) * 1000.0
            logger.warning("Failed to load LLMLingua model '%s': %s", self.config.model_name, exc)
            return False

    # -------------------------------------------------------------------------
    # Core Compression Method
    # -------------------------------------------------------------------------

    def compress(
        self,
        prompt: str,
        mode: Optional[str] = None,
        target_retention_rate: Optional[float] = None,
    ) -> CompressionResult:
        """
        Compress a prompt using Stage 1 structural protection followed by
        extractive token compression (LLMLingua-2 or deterministic fallback).

        Args:
            prompt: Original raw prompt text.
            mode: "conservative" (0.80), "balanced" (0.60), or "aggressive" (0.40).
                  Defaults to self.config.mode.
            target_retention_rate: Optional explicit target retention rate (e.g. 0.40, 0.60, 0.80).
                  When provided, overrides mode defaults and length-adaptive heuristics.

        Returns:
            CompressionResult containing compressed text and transparent metrics.
        """
        start_time = time.perf_counter()
        warnings: List[str] = []

        # Resolve mode and target retention rate
        active_mode = (mode or self.config.mode).lower()
        if target_retention_rate is not None:
            target_rate = max(0.01, min(1.0, float(target_retention_rate)))
        elif self.config.target_retention_rate is not None:
            target_rate = max(0.01, min(1.0, float(self.config.target_retention_rate)))
        elif active_mode in RETENTION_MODES:
            target_rate = RETENTION_MODES[active_mode]
        else:
            warnings.append(f"Unknown mode '{active_mode}'; defaulting to 'balanced' (0.60).")
            active_mode = "balanced"
            target_rate = RETENTION_MODES["balanced"]

        # Length-adaptive calibration for short prompts: prevent semantic over-compression
        is_short_prompt = False
        if prompt and prompt.strip():
            raw_words = re.findall(r"\b[A-Za-z0-9_-]+\b", prompt)
            if len(raw_words) < 15:
                # Ultra-short atomic queries (< 15 words) use deterministic lexical pruner
                is_short_prompt = True
            elif len(raw_words) < 35 and target_retention_rate is None and self.config.target_retention_rate is None:
                if active_mode == "conservative":
                    target_rate = max(target_rate, 0.92)
                elif active_mode == "balanced":
                    target_rate = max(target_rate, 0.85)
                elif active_mode == "aggressive":
                    target_rate = max(target_rate, 0.75)

        # Handle empty or whitespace-only prompts
        if not prompt or not prompt.strip():
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return CompressionResult(
                original_prompt=prompt,
                compressed_prompt=prompt,
                original_token_count=0,
                compressed_token_count=0,
                actual_reduction_percentage=0.0,
                retention_rate=1.0,
                compression_mode=active_mode,
                compression_method="passthrough",
                model_name=self.config.model_name,
                model_available=self.is_model_available(),
                is_exact_token_count=True,
                compression_latency_ms=latency_ms,
                model_loading_latency_ms=self._model_loading_latency_ms,
                protected_region_count=0,
                protected_regions_preserved=True,
                warnings=warnings,
                fallback_used=False,
                success=True,
            )

        # Initial token count of original prompt
        orig_tokens, is_exact_tokens = self.pruner.count_tokens(prompt)

        # ---------------------------------------------------------------------
        # Step 1: Stage 1 Structural Region Masking
        # ---------------------------------------------------------------------
        masked_prompt, placeholder_map, region_details = self.pruner.mask_protected_regions(prompt)
        masked_prompt, placeholder_map = self._mask_extended_preservation(masked_prompt, placeholder_map)
        protected_region_count = len(placeholder_map)

        # ---------------------------------------------------------------------
        # Step 2: Separate Protected Regions from Natural Prose Chunks
        # ---------------------------------------------------------------------
        # If no protected regions exist, the entire prompt is natural language
        if not placeholder_map:
            chunks: List[Tuple[bool, str]] = [(False, masked_prompt)]
        else:
            sorted_keys = sorted(placeholder_map.keys(), key=len, reverse=True)
            pattern = "(" + "|".join(re.escape(k) for k in sorted_keys) + ")"
            raw_parts = re.split(pattern, masked_prompt)
            chunks = []
            for part in raw_parts:
                if not part:
                    continue
                if part in placeholder_map:
                    chunks.append((True, part))
                else:
                    chunks.append((False, part))

        # ---------------------------------------------------------------------
        # Step 3 & 4: Extractive Compression on Natural Language Content
        # ---------------------------------------------------------------------
        fallback_used = False
        compression_method = "llmlingua-2"
        model_available = self.is_model_available()

        compressed_masked_text = ""
        neural_success = False

        if self.config.use_llmlingua2 and (self._llm_lingua is not None or model_available):
            if self._llm_lingua is None and not self.load_model():
                warnings.append(f"Model loading failed for '{self.config.model_name}'. Using deterministic fallback.")
            elif is_short_prompt and self._llm_lingua is self.__class__._shared_llm_lingua:
                # Ultra-short prompts (< 15 words) with real neural model use deterministic fallback
                # to prevent destructive loss of single-word modifiers
                neural_success = False
            else:
                # Attempt LLMLingua-2 compression
                try:
                    # Attempt whole-masked compression with force_tokens
                    candidate_text, all_preserved = self._compress_with_llmlingua(
                        masked_text=masked_prompt,
                        placeholder_map=placeholder_map,
                        target_rate=target_rate,
                    )
                    if all_preserved:
                        compressed_masked_text = candidate_text
                        neural_success = True
                    else:
                        # Fallback to chunk-by-chunk neural compression
                        candidate_chunks = []
                        for is_protected, content in chunks:
                            if is_protected:
                                candidate_chunks.append(content)
                            else:
                                c_text, _ = self._compress_with_llmlingua(
                                    masked_text=content,
                                    placeholder_map={},
                                    target_rate=target_rate,
                                )
                                candidate_chunks.append(c_text)
                        compressed_masked_text = "".join(candidate_chunks)
                        neural_success = True
                except Exception as exc:
                    logger.warning("Neural LLMLingua-2 compression encountered error: %s", exc)
                    warnings.append(f"LLMLingua-2 compression failed: {exc}. Using deterministic fallback.")
                    neural_success = False

        if not neural_success:
            # Deterministic fallback compression
            fallback_used = True
            compression_method = "deterministic_lexical_fallback"
            if not self.config.enable_fallback:
                # Rollback to uncompressed Stage 1 output
                compressed_masked_text = masked_prompt
                warnings.append("LLMLingua unavailable and fallback disabled; preserving masked prompt.")
            else:
                candidate_chunks = []
                prev_ended_with_sentence_terminal = True

                for is_protected, content in chunks:
                    if is_protected:
                        candidate_chunks.append(content)
                        prev_ended_with_sentence_terminal = bool(content.endswith("\n"))
                    else:
                        c_text = self._compress_fallback_natural_text(
                            text=content,
                            mode=active_mode,
                            target_rate=target_rate,
                            is_start_of_sentence=prev_ended_with_sentence_terminal,
                        )
                        candidate_chunks.append(c_text)
                        stripped_c = c_text.rstrip()
                        if stripped_c:
                            prev_ended_with_sentence_terminal = stripped_c[-1] in ".!?\n"
                        else:
                            prev_ended_with_sentence_terminal = False

                compressed_masked_text = "".join(candidate_chunks)

        # ---------------------------------------------------------------------
        # Step 5 & 6: Restore Protected Regions Exactly
        # ---------------------------------------------------------------------
        restored_prompt, restored_ok = self.pruner.restore_protected_regions(
            compressed_masked_text, placeholder_map
        )

        # ---------------------------------------------------------------------
        # Step 7: Verify Output Integrity
        # ---------------------------------------------------------------------
        protected_regions_preserved = restored_ok
        if restored_ok and placeholder_map:
            for ph, original_content in placeholder_map.items():
                if original_content not in restored_prompt:
                    protected_regions_preserved = False
                    warnings.append(f"Protected content for '{ph}' was corrupted or missing.")
                    break

        # Rollback if structural restoration failed
        if not protected_regions_preserved:
            warnings.append("Structural verification failed; rolling back to Stage 1 output.")
            restored_prompt, _ = self.pruner.restore_protected_regions(
                masked_prompt, placeholder_map
            )
            protected_regions_preserved = True

        # ---------------------------------------------------------------------
        # Step 8: Token Counting and Metric Compilation
        # ---------------------------------------------------------------------
        comp_tokens, _ = self.pruner.count_tokens(restored_prompt)
        token_reduction = max(0, orig_tokens - comp_tokens)
        reduction_pct = (token_reduction / orig_tokens * 100.0) if orig_tokens > 0 else 0.0
        actual_retention = (comp_tokens / orig_tokens) if orig_tokens > 0 else 1.0

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        return CompressionResult(
            original_prompt=prompt,
            compressed_prompt=restored_prompt,
            original_token_count=orig_tokens,
            compressed_token_count=comp_tokens,
            actual_reduction_percentage=round(reduction_pct, 2),
            retention_rate=round(actual_retention, 4),
            compression_mode=active_mode,
            compression_method=compression_method,
            model_name=self.config.model_name,
            model_available=model_available,
            is_exact_token_count=is_exact_tokens,
            compression_latency_ms=round(latency_ms, 2),
            model_loading_latency_ms=round(self._model_loading_latency_ms, 2),
            protected_region_count=protected_region_count,
            protected_regions_preserved=protected_regions_preserved,
            warnings=warnings,
            fallback_used=fallback_used,
            success=True,
        )

    # -------------------------------------------------------------------------
    # Neural LLMLingua-2 Handler
    # -------------------------------------------------------------------------

    def _mask_extended_preservation(
        self, masked_text: str, placeholder_map: Dict[str, str]
    ) -> Tuple[str, Dict[str, str]]:
        """
        Extend structural masking to protect critical semantic regions (Section 5.3):
        - Literal user placeholders (e.g. __CODE_BLOCK_0__)
        - Negative & conditional instructions (e.g. 'Do not delete', 'must never drop')
        - PascalCase / UpperCamelCase identifiers (e.g. 'GreenModelRouter')
        - Numerical values, multipliers & units (e.g. '3.8x', '32 items')
        - Non-ASCII unicode entities (e.g. 'café', 'brûlée', 'λ')
        Operates strictly on non-placeholder text segments to avoid corrupting existing placeholders.
        """
        if not masked_text or not masked_text.strip():
            return masked_text, placeholder_map

        if placeholder_map:
            keys_sorted = sorted(placeholder_map.keys(), key=len, reverse=True)
            split_pattern = "(" + "|".join(re.escape(k) for k in keys_sorted) + ")"
            parts = re.split(split_pattern, masked_text)
        else:
            parts = [masked_text]

        new_parts: List[str] = []
        ext_map = dict(placeholder_map)
        ext_idx = len(placeholder_map)

        for part in parts:
            if part in placeholder_map:
                new_parts.append(part)
                continue

            seg = part

            # 1. User literal placeholders (e.g. __FOO_BAR__)
            def repl_lit(m: re.Match) -> str:
                nonlocal ext_idx
                ph = f"__PG_EXT_LIT_{ext_idx}__"
                ext_idx += 1
                ext_map[ph] = m.group(0)
                return ph
            seg = re.sub(r"__(?:[A-Za-z0-9_]+)__", repl_lit, seg)

            # 2. Negations and critical restrictive / conditional phrases
            def repl_neg(m: re.Match) -> str:
                nonlocal ext_idx
                ph = f"__PG_EXT_NEG_{ext_idx}__"
                ext_idx += 1
                ext_map[ph] = m.group(0)
                return ph
            seg = re.sub(
                r"\b(?:do\s+not|must\s+not|cannot|can\'?t|never|should\s+not|shouldn\'?t|won\'?t|without)\s+[a-zA-Z_]+(?:\s+[a-zA-Z_]+)?\b"
                r"|\b(?:if|unless|whether|provided(?:\s+that)?|except(?:\s+when)?)\b(?:\s+[a-zA-Z_]+){1,2}",
                repl_neg,
                seg,
                flags=re.IGNORECASE,
            )

            # 3. PascalCase / UpperCamelCase identifiers and names with initials
            def repl_pascal(m: re.Match) -> str:
                nonlocal ext_idx
                ph = f"__PG_EXT_ID_{ext_idx}__"
                ext_idx += 1
                ext_map[ph] = m.group(0)
                return ph
            seg = re.sub(
                r"\b(?:[A-Z]\.\s*)+[A-Z][a-z]+\b"
                r"|\b[A-Z][a-z0-9]+(?:[A-Z][a-zA-Z0-9]*)+\b",
                repl_pascal,
                seg,
            )

            # 4. Numerical values, version strings, multipliers, and units
            def repl_num(m: re.Match) -> str:
                nonlocal ext_idx
                ph = f"__PG_EXT_NUM_{ext_idx}__"
                ext_idx += 1
                ext_map[ph] = m.group(0)
                return ph
            seg = re.sub(
                r"\bv?\d+(?:\.\d+)+(?:-[a-zA-Z0-9.]+)?\b"
                r"|\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?:[a-zA-Z%]+)?\b",
                repl_num,
                seg,
            )

            # 5. Non-ASCII unicode entities (complete words or symbols)
            def repl_uni(m: re.Match) -> str:
                nonlocal ext_idx
                ph = f"__PG_EXT_UNI_{ext_idx}__"
                ext_idx += 1
                ext_map[ph] = m.group(0)
                return ph
            seg = re.sub(r"\b\w*[^\x00-\x7F]+\w*\b|[^\x00-\x7F]", repl_uni, seg)

            new_parts.append(seg)

        return "".join(new_parts), ext_map

    def _compress_with_llmlingua(
        self,
        masked_text: str,
        placeholder_map: Dict[str, str],
        target_rate: float,
    ) -> Tuple[str, bool]:
        """
        Execute neural compression using the LLMLingua-2 API.
        Returns the compressed text and a boolean indicating whether all
        placeholders survived intact.
        """
        if not masked_text or not masked_text.strip():
            return masked_text, True

        force_tokens = list(placeholder_map.keys())
        if self.config.preserve_sentence_structure:
            for p in [".", "?", "!", "\n"]:
                if p not in force_tokens:
                    force_tokens.append(p)
        for q in ["how", "why", "what", "which"]:
            if q not in force_tokens:
                force_tokens.append(q)

        # Call LLMLingua PromptCompressor
        res = self._llm_lingua.compress_prompt(
            context=masked_text,
            rate=target_rate,
            force_tokens=force_tokens,
        )

        compressed_text = res.get("compressed_prompt", masked_text) if isinstance(res, dict) else str(res)

        # Verify whether all placeholders survived
        all_preserved = all(ph in compressed_text for ph in placeholder_map)
        return compressed_text, all_preserved

    # -------------------------------------------------------------------------
    # Deterministic Fallback Information-Density Pruner
    # -------------------------------------------------------------------------

    def _compress_fallback_natural_text(
        self,
        text: str,
        mode: str = "balanced",
        target_rate: float = 0.55,
        is_start_of_sentence: bool = True,
    ) -> str:
        """
        Deterministic, CPU-first information-density compressor for natural language.

        Operates in three stages:
        1. Discourse filler reduction (converts multi-word padding to concise equivalents).
        2. Sentence and clause token analysis (identifies immune negations, conditionals,
           imperative verbs, numbers, and technical terms).
        3. Information-density pruning (removes weak adverbs, empty intensifiers, and
           filler qualifiers based on the target retention rate).
        """
        if not text or not text.strip():
            return text

        # Extract leading and trailing whitespace to prevent concatenation glitches
        leading_ws = re.match(r"^\s*", text).group(0)
        trailing_ws = re.search(r"\s*$", text).group(0)
        core = text[len(leading_ws):len(text) - len(trailing_ws) if trailing_ws else len(text)]

        if not core:
            return text

        # Stage A: Replace multi-word discourse fillers
        pruned = core
        for pattern, repl in DISCOURSE_REPLACEMENTS:
            pruned = pattern.sub(repl, pruned)

        # Stage B: Track token frequencies to protect single-occurrence keywords
        words_raw = re.findall(r"\b[A-Za-z0-9_-]+\b", pruned)
        freq: Dict[str, int] = {}
        for w in words_raw:
            lw = w.lower()
            freq[lw] = freq.get(lw, 0) + 1

        # Stage C: Sentence-by-sentence token filtering
        # Protect abbreviations (e.g., i.e., Dr., etc.), initials, single-letter genus (E. coli), and numbers
        sentence_split_pattern = (
            r"(?<!\b[A-Za-z])"
            r"(?<!\be\.g)(?<!\bi\.e)"
            r"(?<!\b[Dd]r)(?<!\b[Mm]r)(?<!\b[Mm]rs)(?<!\b[Mm]s)(?<!\b[Pp]rof)(?<!\b[Vv]s)(?<!\betc)(?<!\bal)"
            r"(?<!\b\d)"
            r"([.!?]+(?:\s+(?=[A-Z0-9\"'`\n])|\n+|$))"
        )
        sentence_chunks = re.split(sentence_split_pattern, pruned)
        processed_sentences: List[str] = []

        for i in range(0, len(sentence_chunks), 2):
            sentence = sentence_chunks[i]
            sep = sentence_chunks[i + 1] if i + 1 < len(sentence_chunks) else ""

            if not sentence.strip():
                processed_sentences.append(sentence + sep)
                continue

            # Tokenize words with their leading whitespace
            token_matches = list(re.finditer(r"(\s*)([^\s]+)", sentence))
            if not token_matches:
                processed_sentences.append(sentence + sep)
                continue

            kept_tokens: List[str] = []
            for tok_idx, match in enumerate(token_matches):
                ws, raw_tok = match.group(1), match.group(2)
                word_clean = raw_tok.strip(".,;:?!'\"()[]{}").lower()

                # Detect if token is a personal initial or initialism (e.g., 'A.', 'B.', 'J.', 'A.B.', 'A. B.')
                next_raw = token_matches[tok_idx + 1].group(2) if tok_idx + 1 < len(token_matches) else ""
                is_initial = self._is_personal_initial(raw_tok, next_raw)

                # Determine if word is immune to pruning
                is_immune = (
                    word_clean in IMMUNE_WORDS
                    or self._is_technical_or_identifier(raw_tok)
                    or is_initial
                    or (
                        freq.get(word_clean, 0) == 1
                        and len(word_clean) > 3
                        and word_clean not in WEAK_ADVERBS
                        and word_clean not in FILLER_QUALIFIERS
                        and word_clean not in ARTICLES
                    )
                )

                drop = False
                if not is_immune:
                    if word_clean in WEAK_ADVERBS:
                        # Protect "very" in collocations like "thank you very much"
                        if word_clean == "very" and kept_tokens and kept_tokens[-1].strip().lower() in ("thank", "thanks", "you"):
                            drop = False
                        else:
                            drop = True
                    elif mode in ("balanced", "aggressive") and word_clean in FILLER_QUALIFIERS:
                        drop = True
                    elif mode == "aggressive" and word_clean in ARTICLES:
                        # In aggressive mode, prune non-essential articles unless at sentence start or an initial
                        if not is_initial:
                            drop = True

                if not drop:
                    kept_tokens.append(ws + raw_tok)

            reconstructed = "".join(kept_tokens).strip()
            if reconstructed:
                reconstructed = re.sub(r"  +", " ", reconstructed)
                should_capitalize = is_start_of_sentence if i == 0 else True
                if should_capitalize:
                    if len(reconstructed) > 1:
                        reconstructed = reconstructed[0].upper() + reconstructed[1:]
                    else:
                        reconstructed = reconstructed.upper()
                processed_sentences.append(reconstructed + sep)
            else:
                processed_sentences.append(sep)

        result = "".join(processed_sentences)
        # Clean up stray spaces before punctuation
        result = re.sub(r" +([.,;?!])", r"\1", result)
        # Fix indefinite article agreement if adverbs were dropped (e.g. "an [extremely] comprehensive" -> "a comprehensive")
        result = self._fix_article_agreement(result)
        # Collapse multiple horizontal spaces while preserving line-leading indentation
        lines = result.split("\n")
        cleaned_lines = []
        for line in lines:
            line_leading_ws = re.match(r"^\s*", line).group(0)
            body = line[len(line_leading_ws):]
            body = re.sub(r"[ \t]{2,}", " ", body)
            cleaned_lines.append(line_leading_ws + body)
        result = "\n".join(cleaned_lines)
        return leading_ws + result + trailing_ws

    @staticmethod
    def _fix_article_agreement(text: str) -> str:
        """
        Ensures correct English indefinite article agreement ('a' vs 'an').
        Corrects 'an <consonant>' -> 'a <consonant>' and 'a <vowel>' -> 'an <vowel>',
        respecting standard phonetic exceptions (silent h, /ju:/ initial sounds).
        """
        def repl_an(m):
            art = m.group(1)
            next_word = m.group(2)
            nw_lower = next_word.lower()
            if nw_lower.startswith(("hour", "honest", "honor", "heir")):
                return m.group(0)
            if re.match(r"^[b-df-hj-np-tv-z]", nw_lower):
                replacement_art = "A" if art[0].isupper() else "a"
                return f"{replacement_art} {next_word}"
            return m.group(0)

        def repl_a(m):
            art = m.group(1)
            next_word = m.group(2)
            nw_lower = next_word.lower()
            if nw_lower.startswith(("user", "univ", "uniq", "unif", "unit", "euro", "euph")):
                return m.group(0)
            if re.match(r"^[aeio]", nw_lower) or (nw_lower.startswith("u") and not nw_lower.startswith(("user", "univ", "uniq", "unif", "unit"))):
                replacement_art = "An" if art[0].isupper() else "an"
                return f"{replacement_art} {next_word}"
            if nw_lower.startswith(("hour", "honest", "honor", "heir")):
                replacement_art = "An" if art[0].isupper() else "an"
                return f"{replacement_art} {next_word}"
            return m.group(0)

        text = re.sub(r"\b(an)\s+([a-zA-Z]+)", repl_an, text)
        text = re.sub(r"\b(a)\s+([a-zA-Z]+)", repl_a, text)
        return text

    @staticmethod
    def _is_personal_initial(token: str, next_token: str = "") -> bool:
        """
        Detect if a token is a personal initial (e.g. 'A.', 'B.', 'J.', 'A.B.', 'A.B.C.'),
        optionally enclosed in quotes or brackets, or followed by punctuation.
        Also detects bare initials followed by another initial (e.g. 'A' in 'A B Smith' or 'A' in 'A B.').
        Prevents personal initials from being mistakenly pruned as English articles ('a').
        """
        stripped = token.strip("'\"()[]{}")
        # 1. Standard single or multi-part dotted initial: A., B., J., A.B., A.B.C., A.-B.
        if re.match(r"^(?:[A-Za-z]\.[-]?)+[,;:?!]?$", stripped):
            return True
        # 2. Standalone uppercase single letter followed by another initial: 'A' in 'A B Smith' or 'A' in 'A B.'
        if len(stripped) == 1 and stripped.isupper() and next_token:
            next_stripped = next_token.strip("'\"()[]{}")
            if re.match(r"^[A-Za-z]\.?", next_stripped) and (len(next_stripped) == 1 or next_stripped.endswith(".")):
                return True
        return False

    @staticmethod
    def _is_technical_or_identifier(token: str) -> bool:
        """
        Detect if a token is a programming identifier, numerical constraint,
        acronym, version string, or domain-specific technical term.
        """
        clean = token.strip(".,;:?!'\"()[]{}")
        if not clean:
            return False
        # Personal initials or initialisms (A., B., J., A.B., etc.)
        if LLMLinguaCompressor._is_personal_initial(token):
            return True
        # Digits (numbers, versions, ports, units)
        if any(c.isdigit() for c in clean):
            return True
        # All-caps acronyms (API, REST, JSON, GPU, etc.)
        if clean.isupper() and len(clean) >= 2:
            return True
        # CamelCase or PascalCase
        if any(c.isupper() for c in clean[1:]):
            return True
        # Identifiers with symbols (snake_case, paths, domains, flags)
        if any(c in clean for c in ["_", "-", "/", "\\", ".", ":", "@", "$", "#", "="]):
            return True
        return False


# Standard alias for pipeline integration
PromptCompressor = LLMLinguaCompressor
