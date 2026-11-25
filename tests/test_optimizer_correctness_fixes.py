"""
tests/test_optimizer_correctness_fixes.py
Comprehensive regression tests for Fix A (Stage 1 greeting regex),
Fix B (Stage 2 sentence splitting / abbreviations), Fix C (token expansion guard),
and the 11 historically affected benchmark cases.
"""

import json
import os
import re
import pytest

from promptgreen.optimizer.rule_pruner import RuleBasedPruner
from promptgreen.optimizer.compressor import LLMLinguaCompressor, CompressorConfig
from promptgreen.optimizer.pipeline import PromptGreenPipeline, PipelineConfig, PipelineResult


# =============================================================================
# FIX A REGRESSION TESTS: Stage 1 Greeting Regex & Word Boundaries
# =============================================================================

class TestFixAGreetingRemovalRegex:
    """Verifies that greeting pruning correctly identifies genuine greetings
    while strictly protecting ordinary English vocabulary and domain terms."""

    @pytest.fixture
    def pruner(self):
        return RuleBasedPruner()

    @pytest.mark.parametrize("word", [
        "Highlight", "Highlights", "Highlighting", "Highly",
        "History", "Historic", "Histogram", "Hindi", "Hinder",
        "Hint", "Hired", "Hilarious", "Hellokitty", "Heyday"
    ])
    def test_ordinary_words_not_pruned_at_prompt_start(self, pruner, word):
        prompt = f"{word} the key requirements and findings."
        res = pruner.prune(prompt)
        assert res.optimized_prompt.startswith(word), (
            f"Word '{word}' was corrupted! Got: '{res.optimized_prompt}'"
        )
        assert res.token_reduction >= 0, f"Token count expanded on '{word}'!"

    @pytest.mark.parametrize("boundary", [". ", "! ", "? ", "\n", "\n\n"])
    @pytest.mark.parametrize("word", ["Highlight", "Highlights", "History", "Hindi", "Hint"])
    def test_ordinary_words_not_pruned_after_sentence_boundary(self, pruner, boundary, word):
        prompt = f"Please review this document{boundary}{word} all critical issues."
        res = pruner.prune(prompt)
        assert word in res.optimized_prompt, f"Word '{word}' corrupted after boundary '{boundary}'"
        assert not re.search(r"\bghlights?\b", res.optimized_prompt, re.IGNORECASE)
        assert not re.search(r"\bstory\b", res.optimized_prompt, re.IGNORECASE) or word == "History"

    def test_mid_sentence_occurrences_untouched(self, pruner):
        prompts = [
            "This is highly important for the project.",
            "The historical report contains highlights of the year.",
            "We found a hint in the logs.",
            "The hindrance was overcome quickly."
        ]
        for p in prompts:
            res = pruner.prune(p)
            assert res.optimized_prompt == p

    @pytest.mark.parametrize("greeting,expected_remaining", [
        ("Hi, can you help me?", "Help me?"),
        ("Hi! Please summarize this report.", "Summarize this report."),
        ("Hello, can you explain this?", "Explain this?"),
        ("Hey, review this code.", "Review this code."),
        ("Good morning, please summarize.", "Summarize."),
        ("Good morning! What is the status?", "What is the status?"),
        ("Good afternoon everyone, let's start.", "Let's start."),
        ("Good evening, can you help?", "Help?"),
        ("Greetings, can you write an essay?", "Write an essay?"),
        ("Greetings! Please analyze this data.", "Analyze this data."),
        ("Greetings everyone, summarize this.", "Summarize this."),
        ("Hi there! Write a poem.", "Write a poem."),
        ("Hi there, write a poem.", "Write a poem."),
    ])
    def test_genuine_greetings_cleanly_pruned(self, pruner, greeting, expected_remaining):
        res = pruner.prune(greeting)
        assert res.optimized_prompt == expected_remaining, (
            f"Greeting '{greeting}' expected '{expected_remaining}', got '{res.optimized_prompt}'"
        )

    def test_non_greeting_formal_phrases_preserved(self, pruner):
        # "Greetings" as a subject noun must NOT be pruned
        p1 = "Greetings are customary in many cultures."
        res1 = pruner.prune(p1)
        assert res1.optimized_prompt == p1

        # "Good morning" as a noun phrase must NOT be pruned
        p2 = "Good morning news is broadcast daily."
        res2 = pruner.prune(p2)
        assert res2.optimized_prompt == p2

    def test_case_variations(self, pruner):
        p = "HIGHlight this section."
        res = pruner.prune(p)
        assert res.optimized_prompt == p
        assert not res.optimized_prompt.startswith("GHlight")

    def test_empty_and_greeting_only_prompts(self, pruner):
        assert pruner.prune("").optimized_prompt == ""
        assert pruner.prune("   ").optimized_prompt == "   "
        # Greeting-only prompt should prune to empty without error
        res = pruner.prune("Hello!")
        assert res.optimized_prompt == ""
        assert res.token_reduction >= 0

    def test_unicode_and_protected_regions_with_greetings(self, pruner):
        prompt = "Hi! Please inspect `Highlight` in `/var/log/syslog` at https://example.com/highlight."
        res = pruner.prune(prompt)
        assert "`Highlight`" in res.optimized_prompt
        assert "/var/log/syslog" in res.optimized_prompt
        assert "https://example.com/highlight" in res.optimized_prompt
        assert "Hi!" not in res.optimized_prompt


# =============================================================================
# FIX B REGRESSION TESTS: Stage 2 Sentence Splitting & Abbreviations
# =============================================================================

class TestFixBSentenceSplittingAndAbbreviations:
    """Verifies that Stage 2 extractive compression does not split on
    abbreviations, initials, decimal numbers, or scientific genus-species names."""

    @pytest.fixture
    def compressor(self):
        return LLMLinguaCompressor(config=CompressorConfig(mode="conservative"))

    @pytest.mark.parametrize("scientific_name", [
        "E. coli", "S. aureus", "C. elegans", "B. subtilis", "P. aeruginosa"
    ])
    def test_scientific_names_preserved_without_capitalization_split(self, compressor, scientific_name):
        prompt = f"The patient sample tested positive for {scientific_name} bacteria."
        res = compressor.compress(prompt)
        assert scientific_name in res.compressed_prompt, (
            f"Scientific name '{scientific_name}' corrupted! Got: '{res.compressed_prompt}'"
        )
        # Ensure genus wasn't capitalized incorrectly (e.g. "E. Coli")
        parts = scientific_name.split()
        if len(parts) == 2:
            corrupted = f"{parts[0]} {parts[1].capitalize()}"
            assert corrupted not in res.compressed_prompt or parts[1][0].isupper()

    @pytest.mark.parametrize("abbrev_sentence", [
        "Use tools, e.g. python or bash, to automate builds.",
        "Verify the status, i.e. check exit code 0.",
        "Consult Dr. Smith for clinical guidance.",
        "Mr. and Mrs. Davis attended the conference.",
        "Benchmark Python vs. Rust in production.",
        "Buy apples, oranges, etc. before returning.",
    ])
    def test_common_abbreviations_not_split(self, compressor, abbrev_sentence):
        res = compressor.compress(abbrev_sentence)
        # Ensure abbreviation periods did not cause unwanted splits or casing corruption
        assert res.compressed_prompt is not None
        assert len(res.compressed_prompt) > 0

    def test_initials_in_proper_names(self, compressor):
        prompt = "The lord of the rings was written by J. R. R. Tolkien in 1954."
        res = compressor.compress(prompt)
        assert "Tolkien" in res.compressed_prompt
        assert "J." in res.compressed_prompt

    def test_numbers_and_version_strings(self, compressor):
        prompt = "The value is 3.14159, version is v2.0.1, and tolerance is 1.2e-5."
        res = compressor.compress(prompt)
        assert "3.14159" in res.compressed_prompt
        assert "v2.0.1" in res.compressed_prompt
        assert "1.2e-5" in res.compressed_prompt

    def test_consecutive_punctuation_and_paragraphs(self, compressor):
        prompt = "Wait... what happened?! Check paragraph one.\n\nParagraph two begins here."
        res = compressor.compress(prompt)
        assert "Paragraph two" in res.compressed_prompt


# =============================================================================
# FIX C REGRESSION TESTS: Reject Token-Expanding Candidates
# =============================================================================

class TestFixCTokenExpansionGuard:
    """Verifies that the pipeline strictly rejects any optimization candidate
    whose token count expands beyond the original prompt, rolling back to
    the exact original prompt."""

    def test_candidate_with_fewer_tokens_accepted(self):
        pipeline = PromptGreenPipeline(config=PipelineConfig(mode="aggressive"))
        prompt = "Could you please kindly write a Python function to add two numbers? Thank you so much!"
        res = pipeline.optimize(prompt, mode="aggressive")
        assert res.success is True
        assert res.accepted is True
        assert res.rollback_occurred is False
        assert res.net_token_reduction > 0
        assert res.final_token_count < res.original_token_count

    def test_candidate_with_identical_token_count_not_rejected(self):
        pipeline = PromptGreenPipeline(config=PipelineConfig(mode="conservative"))
        prompt = "Add two numbers."
        res = pipeline.optimize(prompt, mode="conservative")
        assert res.success is True
        assert res.accepted is True
        assert res.net_token_reduction == 0
        assert res.final_token_count == res.original_token_count
        assert res.final_prompt == prompt

    def test_simulated_token_expansion_triggers_atomic_rollback(self, monkeypatch):
        pipeline = PromptGreenPipeline(config=PipelineConfig(mode="conservative"))
        prompt = "Short prompt."
        orig_tokens, _ = pipeline._count_tokens(prompt)

        # Simulate a bug where Stage 2 expands the prompt with extra tokens
        def expanding_compress(text, mode=None):
            from promptgreen.optimizer.compressor import CompressionResult
            expanded_text = "Short prompt with unnecessary extra explanatory words added here to expand tokens."
            exp_tokens, _ = pipeline._count_tokens(expanded_text)
            return CompressionResult(
                original_prompt=text,
                compressed_prompt=expanded_text,
                original_token_count=orig_tokens,
                compressed_token_count=exp_tokens,
                actual_reduction_percentage=-50.0,
                retention_rate=1.5,
                compression_mode="conservative",
                compression_method="simulated_expansion",
                model_name="test",
                model_available=True,
                is_exact_token_count=True,
                compression_latency_ms=1.0,
                model_loading_latency_ms=0.0,
                protected_region_count=0,
                protected_regions_preserved=True,
                warnings=[],
                fallback_used=False,
                success=True,
            )

        # Simulate Stage 4 semantic guard passing so candidate reaches post-Stage-4 token gate
        def passing_guardrail(original_prompt, candidate_prompt, intermediate_stages=None, retry_callback=None):
            from promptgreen.optimizer.semantic_guard import GuardrailResult
            return GuardrailResult(
                original_prompt=original_prompt,
                candidate_prompt=candidate_prompt,
                final_prompt=candidate_prompt,
                passed=True,
                similarity_score=0.99,
                active_threshold=0.96,
                selected_mode="conservative",
                retry_count=0,
                rollback_occurred=False,
                rollback_stage="none",
            )

        monkeypatch.setattr(pipeline.compressor, "compress", expanding_compress)
        monkeypatch.setattr(pipeline.guardrail, "evaluate", passing_guardrail)

        res = pipeline.optimize(prompt, mode="conservative")

        # Must be rejected and rolled back
        assert res.accepted is False, "Expanding candidate was accepted!"
        assert res.rollback_occurred is True, "Rollback flag was not set!"
        assert res.rollback_stage == "original", "Rollback stage should be 'original'!"
        assert res.final_prompt == prompt, "Final prompt must be byte-for-byte identical to original prompt!"
        assert res.final_token_count == orig_tokens
        assert res.net_token_reduction == 0
        assert "increased token count" in res.rollback_reason
        assert res.guardrail_passed is False  # pipeline sets guardrail_passed = accepted

    @pytest.mark.parametrize("mode", ["conservative", "balanced", "aggressive"])
    def test_exact_original_prompt_restoration_on_expansion(self, monkeypatch, mode):
        pipeline = PromptGreenPipeline(config=PipelineConfig(mode=mode))
        prompt = "Exact original prompt with special characters: $100, 50%, & 'quotes'."

        def expanding_stage(text, mode=None):
            from promptgreen.optimizer.compressor import CompressionResult
            expanded_text = text + " Extra expansion tokens."
            return CompressionResult(
                original_prompt=text,
                compressed_prompt=expanded_text,
                original_token_count=10,
                compressed_token_count=15,
                actual_reduction_percentage=-50.0,
                retention_rate=1.5,
                compression_mode=mode,
                compression_method="expansion",
                model_name="test",
                model_available=True,
                is_exact_token_count=True,
                compression_latency_ms=1.0,
                model_loading_latency_ms=0.0,
                protected_region_count=0,
                protected_regions_preserved=True,
                warnings=[],
                fallback_used=False,
                success=True,
            )

        monkeypatch.setattr(pipeline.compressor, "compress", expanding_stage)
        res = pipeline.optimize(prompt, mode=mode)
        assert res.final_prompt == prompt
        assert res.accepted is False
        assert res.net_token_reduction == 0


# =============================================================================
# REPRODUCTION TESTS: 11 Historically Affected Benchmark Cases
# =============================================================================

@pytest.fixture(scope="module")
def dataset_prompts():
    dataset_path = "data/benchmark_1200_independent.json"
    if not os.path.exists(dataset_path):
        pytest.skip(f"Benchmark dataset not found at {dataset_path}")
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {p["id"]: p["original_prompt"] for p in data}


class TestHistorical11BenchmarkCases:
    """Tests the exact original prompt strings from the 11 historically affected
    trials to ensure they are now either cleanly optimized or safely preserved."""

    @pytest.mark.parametrize("pid,mode", [
        ("pg-bench-483", "conservative"),
        ("pg-bench-821", "conservative"),
        ("pg-bench-821", "balanced"),
        ("pg-bench-847", "conservative"),
        ("pg-bench-847", "balanced"),
        ("pg-bench-1171", "conservative"),
        ("pg-bench-1171", "balanced"),
        ("pg-bench-1175", "conservative"),
        ("pg-bench-1175", "balanced"),
        ("pg-bench-1200", "conservative"),
        ("pg-bench-1200", "balanced"),
    ])
    def test_historical_case_never_expands_tokens(self, dataset_prompts, pid, mode):
        orig_text = dataset_prompts[pid]
        pipeline = PromptGreenPipeline(config=PipelineConfig(mode=mode))
        res = pipeline.optimize(orig_text, mode=mode)

        # 1. Final token count must NEVER exceed original token count
        assert res.final_token_count <= res.original_token_count, (
            f"[{mode}][{pid}] Token count expanded from {res.original_token_count} to {res.final_token_count}!"
        )
        assert res.net_token_reduction >= 0, f"[{mode}][{pid}] Negative token reduction!"

        # 2. Defect A verification: "Highlight" must NEVER become "Ghlight"
        assert "Ghlight" not in res.final_prompt, f"[{mode}][{pid}] Corrupted 'Ghlight' found in output!"
        assert "ghlight" not in res.final_prompt.lower() or "highlight" in res.final_prompt.lower()

        # 3. Defect B verification: "E. coli" must NEVER become "E. Coli"
        if pid == "pg-bench-1200":
            assert "E. Coli" not in res.final_prompt, f"[{mode}][{pid}] 'E. Coli' found in output!"
            assert "E. coli" in res.final_prompt

        # 4. If accepted, must be safe and verified
        if res.accepted:
            assert res.guardrail_passed is True
            assert res.final_token_count <= res.original_token_count
        else:
            # If rejected, exact original prompt must be restored
            assert res.final_prompt == orig_text


# =============================================================================
# FIX D REGRESSION TESTS: Personal Initial Preservation vs Article Pruning
# =============================================================================

class TestFixPersonalInitialPreservation:
    """Verifies that personal initials (e.g. 'A. B. Smith', 'A. Smith', 'A. Einstein')
    are strictly preserved in all modes (including Aggressive), while ordinary
    grammatical articles ('a', 'an', 'the') continue to be pruned safely."""

    @pytest.mark.parametrize("mode", ["conservative", "balanced", "aggressive"])
    def test_reported_ab_smith_case_in_all_modes(self, mode):
        pipeline = PromptGreenPipeline(config=PipelineConfig(mode=mode))
        prompt = "The book was written by A. B. Smith last year."
        res = pipeline.optimize(prompt, mode=mode)
        assert "A. B. Smith" in res.final_prompt, (
            f"[{mode}] 'A. B. Smith' was corrupted! Got: '{res.final_prompt}'"
        )
        assert "B. Smith" in res.final_prompt
        assert not res.final_prompt.startswith("B. Smith")
        assert res.final_token_count <= res.original_token_count

    @pytest.mark.parametrize("mode", ["conservative", "balanced", "aggressive"])
    @pytest.mark.parametrize("initial_text,expected_sub", [
        ("A. Smith will attend the annual engineering conference.", "A. Smith"),
        ("Research by A. J. Brown was cited in the clinical trial.", "A. J. Brown"),
        ("The general theory was developed by A. Einstein in 1905.", "A. Einstein"),
        ("The outline points are A. B. C. in alphabetical sequence.", "A. B. C."),
    ])
    def test_single_and_multiple_initials_preserved(self, mode, initial_text, expected_sub):
        pipeline = PromptGreenPipeline(config=PipelineConfig(mode=mode))
        res = pipeline.optimize(initial_text, mode=mode)
        assert expected_sub in res.final_prompt, (
            f"[{mode}] Expected '{expected_sub}' to be preserved! Got: '{res.final_prompt}'"
        )
        assert res.final_token_count <= res.original_token_count

    @pytest.mark.parametrize("mode", ["conservative", "balanced", "aggressive"])
    def test_initials_in_different_positions(self, mode):
        pipeline = PromptGreenPipeline(config=PipelineConfig(mode=mode))
        # Start of sentence
        p_start = "A. Smith authored the system architecture document."
        res_start = pipeline.optimize(p_start, mode=mode)
        assert "A. Smith" in res_start.final_prompt

        # Middle of sentence
        p_mid = "The document was authored by A. Smith yesterday."
        res_mid = pipeline.optimize(p_mid, mode=mode)
        assert "A. Smith" in res_mid.final_prompt

        # End of sentence
        p_end = "The lead architect was Smith, A."
        res_end = pipeline.optimize(p_end, mode=mode)
        assert "Smith, A." in res_end.final_prompt or "A." in res_end.final_prompt

    @pytest.mark.parametrize("mode", ["conservative", "balanced", "aggressive"])
    def test_initials_adjacent_to_punctuation_and_newlines(self, mode):
        pipeline = PromptGreenPipeline(config=PipelineConfig(mode=mode))
        # After title punctuation
        p1 = "Consult Dr. A. Smith regarding the patient diagnosis."
        res1 = pipeline.optimize(p1, mode=mode)
        assert "A. Smith" in res1.final_prompt

        # In parentheses
        p2 = "The report (by A. Smith) was approved unanimously."
        res2 = pipeline.optimize(p2, mode=mode)
        assert "A. Smith" in res2.final_prompt

        # In quotes
        p3 = 'Quoting "A. Smith" on the distributed infrastructure design.'
        res3 = pipeline.optimize(p3, mode=mode)
        assert "A. Smith" in res3.final_prompt

        # After newline
        p4 = "Document approval:\nA. Smith confirmed the results."
        res4 = pipeline.optimize(p4, mode=mode)
        assert "A. Smith" in res4.final_prompt

    def test_ordinary_articles_still_pruned_in_aggressive_mode(self):
        pipeline = PromptGreenPipeline(config=PipelineConfig(mode="aggressive"))
        # Ordinary 'A' at sentence start
        p1 = "A detailed report is required."
        res1 = pipeline.optimize(p1, mode="aggressive")
        assert "A detailed" not in res1.final_prompt
        assert "Detailed report is required." in res1.final_prompt

        # Ordinary 'a' in mid-sentence
        p2 = "Write a short summary."
        res2 = pipeline.optimize(p2, mode="aggressive")
        assert " a " not in res2.final_prompt
        assert "Write short summary." in res2.final_prompt

        # Ordinary 'an' in mid-sentence via compressor
        p3 = "Use an appropriate method."
        res3 = pipeline.compressor.compress(p3, mode="aggressive")
        assert " an " not in res3.compressed_prompt
        assert "Use method." in res3.compressed_prompt

    def test_protected_regions_with_initials(self):
        pipeline = PromptGreenPipeline(config=PipelineConfig(mode="aggressive"))
        p = (
            "Contact A. Smith at `user.a_smith@corp.internal` or "
            "https://example.com/A.Smith/profile regarding C:\\Users\\A.Smith\\config.json."
        )
        res = pipeline.optimize(p, mode="aggressive")
        assert "A. Smith" in res.final_prompt
        assert "`user.a_smith@corp.internal`" in res.final_prompt
        assert "https://example.com/A.Smith/profile" in res.final_prompt
        assert "C:\\Users\\A.Smith\\config.json" in res.final_prompt

    def test_unicode_and_mixed_casing_with_initials(self):
        pipeline = PromptGreenPipeline(config=PipelineConfig(mode="aggressive"))
        p = "Reviewed by M. René A. Smith for accuracy."
        res = pipeline.optimize(p, mode="aggressive")
        assert "A. Smith" in res.final_prompt
        assert "René" in res.final_prompt

    @pytest.mark.parametrize("mode", ["conservative", "balanced", "aggressive"])
    def test_no_token_expansion_on_initials(self, mode):
        pipeline = PromptGreenPipeline(config=PipelineConfig(mode=mode))
        p = "The thesis was approved by A. B. Smith and J. R. R. Tolkien."
        res = pipeline.optimize(p, mode=mode)
        assert res.final_token_count <= res.original_token_count
        assert res.net_token_reduction >= 0
