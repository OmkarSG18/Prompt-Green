"""
PromptGreen v2.0 - Local SLM Output Directive Shaper (Stage 3)
Deterministic Output Bounding and Optional Local Ollama SLM Directive Clarifier.

This module implements the Stage 3 output directive shaper for the PromptGreen
pipeline. It sharpens and bounds the expected response format, structure, and
output constraints (e.g., tables, JSON schemas, bullet points, numbered lists,
code-only boundaries) so that downstream LLMs produce concise, well-structured,
and predictable generations.

It operates strictly on CPU:
- Primary/Optional: Local quantized SLM via Ollama (e.g. qwen2.5:0.5b / qwen2.5:3b)
  with bounded timeout (default 2.0s) and strict preservation validation.
- Fallback/Deterministic: High-efficiency, meaning-preserving rule engine that
  clarifies implicit formatting expectations without inventing arbitrary length caps
  or modifying negative/conditional constraints.
"""

from __future__ import annotations

import json
import logging
import os
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from promptgreen.optimizer.rule_pruner import ProtectedRegion, RuleBasedPruner

logger = logging.getLogger("promptgreen.optimizer.output_shaper")

# Words indicating negation that must never be removed or altered
NEGATION_WORDS: Set[str] = {
    "not", "never", "no", "neither", "nor", "none", "without", "except",
    "don't", "dont", "cannot", "can't", "cant", "won't", "wont",
    "shouldn't", "shouldnt", "mustn't", "mustnt", "doesn't", "doesnt"
}

# Words indicating conditions or exceptions that must never be removed
CONDITIONAL_WORDS: Set[str] = {
    "if", "unless", "provided", "whether", "whenever", "excluding", "otherwise"
}


@dataclass
class ShaperConfig:
    """Configuration options for the Stage 3 output directive shaper."""
    ollama_host: str = "http://127.0.0.1:11434"
    model_name: str = "qwen2.5:0.5b"
    prefer_ollama: bool = True
    timeout_seconds: float = 5.0  # Default 5.0s for consumer CPU generation feasibility
    verify_preservation: bool = True
    temperature: float = 0.1

    def __post_init__(self) -> None:
        """Allow runtime override of timeout, host, and model via environment variables."""
        env_timeout = os.environ.get("PROMPTGREEN_OLLAMA_TIMEOUT")
        if env_timeout is not None:
            try:
                self.timeout_seconds = float(env_timeout)
            except ValueError:
                pass
        env_host = os.environ.get("PROMPTGREEN_OLLAMA_HOST")
        if env_host is not None and env_host.strip():
            self.ollama_host = env_host.strip()
        env_model = os.environ.get("PROMPTGREEN_OLLAMA_MODEL")
        if env_model is not None and env_model.strip():
            self.model_name = env_model.strip()


@dataclass
class ShapingResult:
    """Result object returned by OutputDirectiveShaper."""
    original_prompt: str
    shaped_prompt: str
    shaping_applied: bool
    shaping_method: str  # "deterministic", "ollama", or "none"
    model_name: Optional[str]
    fallback_reason: Optional[str]
    input_token_count: int
    output_token_count: int
    estimated_token_difference: int
    processing_latency_ms: float
    integrity_preserved: bool
    warnings: List[str] = field(default_factory=list)
    success: bool = True
    ollama_latency_ms: float = 0.0


class OutputDirectiveShaper:
    """
    Stage 3 Output Directive Shaper.

    Converts implicit or open-ended output expectations into explicit, bounded
    directives (tables, JSON, lists, code-only bounds) while preserving all
    technical, conditional, numerical, and negative instructions.
    """

    def __init__(
        self,
        config: Optional[ShaperConfig] = None,
        pruner: Optional[RuleBasedPruner] = None,
        ollama_client: Optional[Any] = None,
    ) -> None:
        self.config = config or ShaperConfig()
        self.pruner = pruner or RuleBasedPruner()
        self._ollama_client = ollama_client
        self._available_ollama_models: Optional[List[str]] = None

    # -------------------------------------------------------------------------
    # Ollama Health & Model Availability
    # -------------------------------------------------------------------------

    def is_ollama_available(self) -> bool:
        """
        Check if the local Ollama daemon is reachable and whether the configured
        model (or any local model) is available, without triggering remote pulls.
        """
        if self._ollama_client is not None:
            return True

        url = f"{self.config.ollama_host.rstrip('/')}/api/tags"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "PromptGreen-Optimizer"},
                method="GET"
            )
            # Fast healthcheck with 0.3s timeout
            with urllib.request.urlopen(req, timeout=0.3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    models = [m.get("name") for m in data.get("models", [])]
                    self._available_ollama_models = models
                    # Check if target model or any variant exists
                    target = self.config.model_name
                    target_base = target.split(":")[0]
                    return any(target == m or m.startswith(target_base) for m in models)
        except (urllib.error.URLError, socket.error, TimeoutError, OSError, json.JSONDecodeError):
            pass

        return False

    # -------------------------------------------------------------------------
    # Public Shaping Interface
    # -------------------------------------------------------------------------

    def shape(self, prompt: str) -> ShapingResult:
        """
        Refine a prompt by clarifying response boundaries and structure.

        Args:
            prompt: Raw or compressed prompt text.

        Returns:
            ShapingResult containing shaped prompt, method used, and metrics.
        """
        start_time = time.perf_counter()
        warnings: List[str] = []

        # Handle empty or whitespace-only inputs
        if not prompt or not prompt.strip():
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return ShapingResult(
                original_prompt=prompt,
                shaped_prompt=prompt,
                shaping_applied=False,
                shaping_method="none",
                model_name=None,
                fallback_reason=None,
                input_token_count=0,
                output_token_count=0,
                estimated_token_difference=0,
                processing_latency_ms=round(latency_ms, 2),
                integrity_preserved=True,
                warnings=warnings,
                success=True,
            )

        orig_tokens, _ = self.pruner.count_tokens(prompt)

        # Step 1: Stage 1 Structural Region Masking
        masked_prompt, placeholder_map, region_details = self.pruner.mask_protected_regions(prompt)

        # Step 2: Attempt Ollama SLM shaping if preferred and available
        shaped_masked = ""
        shaping_applied = False
        shaping_method = "none"
        used_model_name: Optional[str] = None
        fallback_reason: Optional[str] = None
        ollama_latency_ms: float = 0.0

        if self.config.prefer_ollama:
            ollama_ready = self.is_ollama_available()
            if ollama_ready:
                t_ollama = time.perf_counter()
                ollama_text, ollama_ok, err = self._shape_with_ollama(masked_prompt, placeholder_map)
                ollama_latency_ms = (time.perf_counter() - t_ollama) * 1000.0
                if ollama_ok:
                    cand_tokens, _ = self.pruner.count_tokens(ollama_text)
                    orig_tokens_m, _ = self.pruner.count_tokens(masked_prompt)
                    # Reject neural output if it significantly expands prompt size
                    if cand_tokens > orig_tokens_m + 10:
                        fallback_reason = (
                            f"Ollama neural output expanded token size ({cand_tokens} > {orig_tokens_m}); "
                            "rejected neural candidate to prevent token bloat."
                        )
                        warnings.append(fallback_reason)
                    else:
                        shaped_masked = ollama_text
                        shaping_applied = (shaped_masked.strip() != masked_prompt.strip())
                        shaping_method = "ollama" if shaping_applied else "none"
                        used_model_name = self.config.model_name
                else:
                    fallback_reason = f"Ollama execution failed: {err}"
                    warnings.append(fallback_reason)
            else:
                fallback_reason = "Ollama daemon unreachable or model unavailable."

        # Step 3: Deterministic fallback if Ollama was not used or failed
        if not shaping_applied and shaping_method != "ollama":
            det_text, det_applied = self._shape_deterministic(masked_prompt)
            shaped_masked = det_text
            shaping_applied = det_applied
            shaping_method = "deterministic" if det_applied else "none"

        # Step 4: Restore Stage 1 protected regions
        restored_prompt, restored_ok = self.pruner.restore_protected_regions(
            shaped_masked, placeholder_map
        )

        # Step 5: Semantic and instruction preservation verification
        integrity_ok, integrity_warnings = self._validate_preservation(
            original=prompt,
            candidate=restored_prompt,
            placeholder_map=placeholder_map,
        )
        warnings.extend(integrity_warnings)

        # If preservation failed, atomically roll back to original prompt
        if not integrity_ok:
            warnings.append("Integrity validation failed; rolling back to original prompt.")
            restored_prompt = prompt
            shaping_applied = False
            shaping_method = "none"

        # Step 6: Compute token counts and differences
        shaped_tokens, _ = self.pruner.count_tokens(restored_prompt)
        token_diff = shaped_tokens - orig_tokens
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        return ShapingResult(
            original_prompt=prompt,
            shaped_prompt=restored_prompt,
            shaping_applied=shaping_applied,
            shaping_method=shaping_method,
            model_name=used_model_name,
            fallback_reason=fallback_reason,
            input_token_count=orig_tokens,
            output_token_count=shaped_tokens,
            estimated_token_difference=token_diff,
            processing_latency_ms=round(latency_ms, 2),
            integrity_preserved=integrity_ok,
            warnings=warnings,
            success=True,
            ollama_latency_ms=round(ollama_latency_ms, 2),
        )

    # -------------------------------------------------------------------------
    # Deterministic Shaping Engine
    # -------------------------------------------------------------------------

    def _shape_deterministic(self, masked_text: str) -> Tuple[str, bool]:
        """
        Conservative rule-based output bounding engine.
        Converts implicit formatting expectations into explicit directives.
        """
        text = masked_text.strip()
        if not text:
            return masked_text, False

        # Pattern 1: Simple explanation / beginners ("in simple terms")
        # e.g., "Explain database normalization in simple terms."
        # or "Explain this function in simple terms:\n__CODE_BLOCK_0__"
        m_simple = re.search(r"\bin\s+simple\s+terms\b[:.]?", text, re.IGNORECASE)
        if m_simple and not re.search(r"clear,\s*simple\s+language", text, re.IGNORECASE):
            prefix = text[:m_simple.start()].strip().rstrip(".")
            suffix = text[m_simple.end():].strip()
            if suffix:
                return f"{prefix}. Use clear, simple language. Organize the explanation into short sections:\n{suffix}", True
            return f"{prefix}. Use clear, simple language. Organize the explanation into short sections.", True

        # Pattern 2: Table presentation / comparison ("in a table", "as a table")
        # e.g., "Compare SQL and NoSQL databases in a table."
        if re.search(r"\b(?:in|as)\s+a\s+table\.?$", text, re.IGNORECASE) and not re.search(r"comparison criteria", text, re.IGNORECASE):
            core = re.sub(r"\s+(?:in|as)\s+a\s+table\.?$", "", text, flags=re.IGNORECASE).rstrip(". ")
            if core != text:
                return f"{core}. Present the comparison in a table. Include the relevant comparison criteria.", True

        # Pattern 3: JSON output with explicit keys
        # e.g., "Return only valid JSON with keys name, age and city."
        m_json_keys = re.search(r"^(.*?)\s+with\s+keys\s+([a-zA-Z0-9_,\s]+)\.?$", text, re.IGNORECASE | re.DOTALL)
        if m_json_keys and re.search(r"\bjson\b", m_json_keys.group(1), re.IGNORECASE):
            keys_raw = m_json_keys.group(2).strip()
            # Standardize "a, b and c" -> "a, b, c"
            keys_clean = re.sub(r"\s+and\s+", ", ", keys_raw)
            keys_clean = re.sub(r"\s*,\s*", ", ", keys_clean)
            return f"Return only valid JSON. Include exactly the requested keys: {keys_clean}.", True

        # Pattern 4: Detailed explanation with an example
        # e.g., "Write a detailed explanation of gradient descent with an example."
        m_det = re.search(r"^(?:Write|Provide)?\s*(?:a\s+)?detailed\s+explanation\s+of\s+(.+?)\s+with\s+an?\s+example\.?$", text, re.IGNORECASE | re.DOTALL)
        if m_det:
            topic = m_det.group(1).strip().rstrip(". ")
            return f"Provide a detailed explanation of {topic} and include a relevant example.", True

        # Pattern 5: Numbered steps ("List 3 key steps to boil an egg perfectly.")
        m_steps = re.search(r"^List\s+(\d+)\s+(?:key\s+)?steps\s+to\s+(.+?)\.?$", text, re.IGNORECASE | re.DOTALL)
        if m_steps and not re.search(r"numbered\s+list", text, re.IGNORECASE):
            num = m_steps.group(1)
            action = m_steps.group(2).strip().rstrip(". ")
            return f"List {num} key steps to {action}. Present them as a clear numbered list.", True

        # Pattern 6: Bullet points ("... in bullet points")
        if re.search(r"\bin\s+bullet\s+points\.?$", text, re.IGNORECASE) and not re.search(r"concise\s+bullet\s+points", text, re.IGNORECASE):
            core = re.sub(r"\s+in\s+bullet\s+points\.?$", "", text, flags=re.IGNORECASE).rstrip(". ")
            return f"{core}. Present the key points as concise bullet points.", True

        # Pattern 7: Numbered list request ("... in a numbered list")
        if re.search(r"\b(?:in|as)\s+a\s+numbered\s+list\.?$", text, re.IGNORECASE) and not re.search(r"clear\s+numbered\s+list", text, re.IGNORECASE):
            core = re.sub(r"\s+(?:in|as)\s+a\s+numbered\s+list\.?$", "", text, flags=re.IGNORECASE).rstrip(". ")
            return f"{core}. Present the items as a clear numbered list.", True

        # Pattern 8: Code only request without explicit exclusions
        # e.g., "... Return code only." -> "... Return only the code implementation without additional conversational text."
        if re.search(r"\breturn\s+code\s+only\.?$", text, re.IGNORECASE) and not re.search(r"without\s+(?:any\s+)?(?:conversational|explanation)", text, re.IGNORECASE):
            core = re.sub(r"\s*\.?\s*return\s+code\s+only\.?$", "", text, flags=re.IGNORECASE).rstrip(". ")
            return f"{core}. Return only the code implementation without additional conversational text.", True

        # Pattern 9: Concise / brief request
        # e.g., "Explain microservices briefly."
        if re.search(r"\b(?:briefly|concisely)\.?$", text, re.IGNORECASE) and not re.search(r"focused\s+on", text, re.IGNORECASE):
            core = re.sub(r"\s+(?:briefly|concisely)\.?$", "", text, flags=re.IGNORECASE).rstrip(". ")
            return f"{core}. Keep the explanation concise and focused on the core concept.", True

        # Pattern 10: Explicit word limit preservation
        # e.g., "Explain Docker in under 50 words."
        m_word_limit = re.search(r"\bin\s+(?:under|less\s+than|at\s+most)\s+(\d+)\s+words\.?$", text, re.IGNORECASE)
        if m_word_limit and not re.search(r"Keep the response under", text, re.IGNORECASE):
            limit = m_word_limit.group(1)
            core = re.sub(r"\s+in\s+(?:under|less\s+than|at\s+most)\s+\d+\s+words\.?$", "", text, flags=re.IGNORECASE).rstrip(". ")
            return f"{core}. Keep the response under {limit} words.", True

        # Prompt already clear or no recognized bounding needed
        return masked_text, False

    # -------------------------------------------------------------------------
    # Model-Assisted Ollama Engine
    # -------------------------------------------------------------------------

    def _shape_with_ollama(
        self,
        masked_text: str,
        placeholder_map: Dict[str, str],
    ) -> Tuple[str, bool, Optional[str]]:
        """
        Invoke local Ollama generate API to clarify output directives.
        Validates output strictly before accepting.
        """
        system_prompt = (
            "You are PromptGreen Output Directive Shaper.\n"
            "Your task is to sharpen output format constraints (tables, JSON schemas, numbered lists, bullet points, code-only boundaries).\n"
            "STRICT RULES:\n"
            "1. Do NOT answer the prompt or write code to solve it. Return only the refined prompt text.\n"
            "2. Do NOT change the user's underlying question, task, or intent.\n"
            "3. Do NOT remove any facts, context, conditions, exceptions, or negative instructions.\n"
            "4. Do NOT invent word limits or restrict length unless the user explicitly requested it.\n"
            "5. Do NOT drop or alter protected placeholders such as __CODE_BLOCK_0__ or __URL_0__.\n"
            "6. Return ONLY the refined prompt text with no intro, greetings, or commentary.\n\n"
            "Example 1:\n"
            "Input: Compare SQL and NoSQL in a table\n"
            "Output: Compare SQL and NoSQL. Present the comparison in a table.\n"
            "Example 2:\n"
            "Input: Give 3 ways to optimize database queries\n"
            "Output: Give 3 ways to optimize database queries as a clear numbered list."
        )

        payload = {
            "model": self.config.model_name,
            "prompt": masked_text,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "top_p": 0.9,
                "num_predict": 256,
            }
        }

        # Use injected mock client if present
        if self._ollama_client is not None:
            try:
                res = self._ollama_client.generate(payload)
                response_text = res.get("response", "").strip()
                if not response_text:
                    return masked_text, False, "Empty response from Ollama"
                # Validate output
                ok, warnings = self._validate_preservation(masked_text, response_text, placeholder_map, is_masked=True)
                if not ok:
                    return masked_text, False, f"Model output failed validation: {'; '.join(warnings)}"
                return response_text, True, None
            except Exception as exc:
                return masked_text, False, str(exc)

        # Real HTTP connection to Ollama daemon
        url = f"{self.config.ollama_host.rstrip('/')}/api/generate"
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "PromptGreen"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    response_text = data.get("response", "").strip()
                    if not response_text:
                        return masked_text, False, "Empty response from Ollama"
                    # Validate output
                    ok, warnings = self._validate_preservation(masked_text, response_text, placeholder_map, is_masked=True)
                    if not ok:
                        return masked_text, False, f"Model output failed validation: {'; '.join(warnings)}"
                    return response_text, True, None
                return masked_text, False, f"Ollama HTTP error {resp.status}"
        except (socket.timeout, TimeoutError):
            return masked_text, False, f"timed out after {self.config.timeout_seconds:.1f}s"
        except urllib.error.URLError as u_err:
            if isinstance(u_err.reason, (socket.timeout, TimeoutError)) or "timed out" in str(u_err).lower():
                return masked_text, False, f"timed out after {self.config.timeout_seconds:.1f}s"
            return masked_text, False, str(u_err)
        except Exception as exc:
            return masked_text, False, str(exc)

    # -------------------------------------------------------------------------
    # Strict Semantic Preservation Validator
    # -------------------------------------------------------------------------

    def _validate_preservation(
        self,
        original: str,
        candidate: str,
        placeholder_map: Dict[str, str],
        is_masked: bool = False,
    ) -> Tuple[bool, List[str]]:
        """
        Verify that candidate text strictly preserves all protected regions,
        negations, conditionals, and numerical constraints.
        If is_masked is True, verifies placeholders; if False, verifies restored raw values.
        """
        warnings: List[str] = []
        if not candidate or not candidate.strip():
            warnings.append("Candidate output is empty.")
            return False, warnings

        # 1. Protected regions integrity
        if is_masked:
            for ph in placeholder_map:
                if ph not in candidate:
                    warnings.append(f"Missing protected placeholder '{ph}'.")
                    return False, warnings
        else:
            for ph, raw_val in placeholder_map.items():
                if raw_val not in candidate:
                    warnings.append(f"Missing protected content for '{ph}'.")
                    return False, warnings

        cand_lower = candidate.lower()
        orig_lower = original.lower()

        # 2. Negations preservation
        for neg in NEGATION_WORDS:
            # Word boundary check in original
            if re.search(rf"\b{re.escape(neg)}\b", orig_lower):
                if not re.search(rf"\b{re.escape(neg)}\b", cand_lower):
                    warnings.append(f"Negation '{neg}' present in original was removed.")
                    return False, warnings

        # 3. Conditional words preservation
        for cond in CONDITIONAL_WORDS:
            if re.search(rf"\b{re.escape(cond)}\b", orig_lower):
                if not re.search(rf"\b{re.escape(cond)}\b", cand_lower):
                    warnings.append(f"Conditional word '{cond}' present in original was removed.")
                    return False, warnings

        # 4. Numerical constraints preservation
        numbers = re.findall(r"\b\d+(?:\.\d+)?(?:ms|s|kb|mb|gb|tb|%|x)?\b", original, re.IGNORECASE)
        for num in numbers:
            if num.lower() not in cand_lower:
                warnings.append(f"Numerical constraint '{num}' present in original was removed.")
                return False, warnings

        # 5. Length sanity check (avoid catastrophic truncation or inflation)
        orig_len = len(original.strip())
        cand_len = len(candidate.strip())
        if orig_len > 20 and (cand_len < orig_len * 0.4 or cand_len > orig_len * 3.0):
            warnings.append(f"Candidate length ({cand_len}) out of acceptable bounds for original ({orig_len}).")
            return False, warnings

        return True, warnings
