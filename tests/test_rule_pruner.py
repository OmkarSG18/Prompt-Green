import unicodedata
import pytest
from promptgreen.optimizer.rule_pruner import RuleBasedPruner, PruningResult


@pytest.fixture
def pruner():
    return RuleBasedPruner()


def test_1_ordinary_conversational_prompt(pruner):
    """Scenario 1: Ordinary conversational prompt with polite filler."""
    prompt = "Hello! Could you please kindly explain how photosynthesis works? Thank you very much in advance!"
    res = pruner.prune(prompt)

    assert isinstance(res, PruningResult)
    assert res.token_reduction > 0
    assert "Explain how photosynthesis works" in res.optimized_prompt
    assert "Could you please kindly" not in res.optimized_prompt
    assert "Thank you very much" not in res.optimized_prompt
    assert len(res.removed_phrases) >= 2


def test_2_prompt_containing_python_code(pruner):
    """Scenario 2: Prompt containing fenced Python code."""
    code_block = (
        "```python\n"
        "def fibonacci(n: int) -> int:\n"
        "    if n <= 1:\n"
        "        return n\n"
        "    return fibonacci(n - 1) + fibonacci(n - 2)\n"
        "```"
    )
    prompt = f"Hi there! Please write a test for this Python function:\n{code_block}\nThanks a lot!"
    res = pruner.prune(prompt)

    # Protected code block must remain byte-for-byte identical
    assert code_block in res.optimized_prompt
    assert res.protected_regions
    assert any(r.region_type == "fenced_code" for r in res.region_details)
    assert "Write a test for this Python function:" in res.optimized_prompt


def test_3_prompt_containing_json(pruner):
    """Scenario 3: Prompt containing JSON objects and schemas."""
    json_snippet = (
        "{\n"
        '  "userId": 42,\n'
        '  "roles": ["admin", "developer"],\n'
        '  "settings": {"active": true, "quota": 1000}\n'
        "}"
    )
    prompt = f"Could you please validate this user profile payload against schema:\n{json_snippet}\nLet me know what you think!"
    res = pruner.prune(prompt)

    # JSON block must remain byte-for-byte identical
    assert json_snippet in res.optimized_prompt
    assert any(r.region_type == "json" for r in res.region_details)
    assert "Validate this user profile payload against schema:" in res.optimized_prompt


def test_4_prompt_containing_yaml(pruner):
    """Scenario 4: Prompt containing YAML configuration blocks."""
    yaml_block = (
        "---\n"
        "apiVersion: apps/v1\n"
        "kind: Deployment\n"
        "metadata:\n"
        "  name: nginx-deployment\n"
    )
    prompt = f"Hello assistant! I would really appreciate it if you could inspect this manifest:\n{yaml_block}\nHope this helps!"
    res = pruner.prune(prompt)

    assert yaml_block in res.optimized_prompt
    assert any(r.region_type == "yaml" for r in res.region_details)
    assert "Inspect this manifest:" in res.optimized_prompt


def test_5_prompt_containing_inline_code(pruner):
    """Scenario 5: Prompt containing inline backtick code."""
    prompt = "Please explain the difference between `asyncio.gather()` and `asyncio.wait()` in Python."
    res = pruner.prune(prompt)

    assert "`asyncio.gather()`" in res.optimized_prompt
    assert "`asyncio.wait()`" in res.optimized_prompt
    assert any(r.region_type == "inline_code" for r in res.region_details)


def test_6_prompt_containing_file_paths_and_identifiers(pruner):
    """Scenario 6: Prompt containing file paths and programming identifiers."""
    prompt = (
        "Could you please check `src/controllers/user_controller.py` and inspect "
        "the function `calculate_user_retention_rate` and `getUserProfile`? "
        "Also verify C:\\Windows\\System32\\drivers\\etc\\hosts."
    )
    res = pruner.prune(prompt)

    assert "src/controllers/user_controller.py" in res.optimized_prompt
    assert "calculate_user_retention_rate" in res.optimized_prompt
    assert "getUserProfile" in res.optimized_prompt
    assert "C:\\Windows\\System32\\drivers\\etc\\hosts" in res.optimized_prompt
    assert any(r.region_type in ["file_path", "identifier", "inline_code"] for r in res.region_details)


def test_7_prompt_containing_urls(pruner):
    """Scenario 7: Prompt containing web URLs."""
    url = "https://api.electricitymap.org/v3/carbon-intensity/latest?zone=US"
    prompt = f"Please fetch the current carbon data from {url}. Have a wonderful day!"
    res = pruner.prune(prompt)

    assert url in res.optimized_prompt
    assert any(r.region_type == "url" for r in res.region_details)
    assert "Have a wonderful day" not in res.optimized_prompt


def test_8_prompt_containing_numerical_constraints(pruner):
    """Scenario 8: Prompt containing numerical constraints and quotas."""
    prompt = (
        "Please generate a response within 5 seconds with a limit of 100 words. "
        "Keep latency <= 50ms and set memory limit to 512MB."
    )
    res = pruner.prune(prompt)

    assert "within 5 seconds" in res.optimized_prompt or "5 seconds" in res.optimized_prompt
    assert "100 words" in res.optimized_prompt
    assert "<= 50" in res.optimized_prompt or "50ms" in res.optimized_prompt
    assert "512MB" in res.optimized_prompt
    assert any(r.region_type == "numerical_constraint" for r in res.region_details)


def test_9_prompt_containing_mixed_blocks(pruner):
    """Scenario 9: Prompt containing mixed natural language, code, schemas, and requirements."""
    code = "```python\ndef compute_delta(a, b):\n    return a - b\n```"
    prompt = (
        "Hello! I would really appreciate it if you could optimize this calculation:\n\n"
        f"{code}\n\n"
        "MUST: Output execution time must be under 30ms.\n"
        "Check endpoint https://internal.dev/metrics. Thank you so much!"
    )
    res = pruner.prune(prompt)

    assert code in res.optimized_prompt
    assert "MUST: Output execution time must be under 30ms" in res.optimized_prompt
    assert "https://internal.dev/metrics" in res.optimized_prompt
    assert "Hello!" not in res.optimized_prompt
    assert "Thank you so much!" not in res.optimized_prompt
    assert res.token_reduction > 0


def test_10_empty_and_whitespace_input(pruner):
    """Scenario 10: Handling empty and pure whitespace inputs."""
    res_empty = pruner.prune("")
    assert res_empty.original_prompt == ""
    assert res_empty.optimized_prompt == ""
    assert res_empty.token_reduction == 0

    res_spaces = pruner.prune("     \n\t   ")
    assert res_spaces.original_token_count == 0
    assert res_spaces.token_reduction == 0


def test_11_unicode_text_handling(pruner):
    """Scenario 11: Handling Unicode text, diacritics, and international greetings."""
    # Unicode text with decomposed accents and non-ASCII characters
    decomposed_str = "Caf\u0065\u0301"  # "Café" in NFD
    prompt = f"Bonjour! Could you please kindly summarize the history of {decomposed_str} in São Paulo?"
    res = pruner.prune(prompt)

    # Verify NFC normalization
    assert unicodedata.is_normalized("NFC", res.optimized_prompt)
    assert "Café" in res.optimized_prompt
    assert "São Paulo" in res.optimized_prompt
    assert "Could you please kindly" not in res.optimized_prompt


def test_12_restoration_failure_handling(pruner, monkeypatch):
    """Scenario 12: Safety fallback when placeholder restoration fails."""
    # Force restore_protected_regions to simulate an integrity failure
    def mock_broken_restore(masked_text, placeholder_map):
        return "BROKEN_TEXT_WITH_UNRESTORED___CODE_BLOCK_0__", False

    monkeypatch.setattr(pruner, "restore_protected_regions", mock_broken_restore)

    prompt = "Hello! Please examine ```python\nx = 1\n```. Thanks!"
    res = pruner.prune(prompt)

    # When restoration fails, the safety fallback must return the original prompt verbatim
    assert res.optimized_prompt == prompt
    assert any("Restoration integrity verification failed" in w for w in res.warnings)


def test_immutability_of_original_input(pruner):
    """Verifies that the original input string object is never mutated."""
    original = "Could you please kindly explain Docker containers? Thank you!"
    original_copy = str(original)
    res = pruner.prune(original)

    assert original == original_copy
    assert res.original_prompt == original_copy


# ==============================================================================
# STAGE 1.1 CORRECTIVE REGRESSION SUITE (TASKS A - I)
# ==============================================================================

def test_a_subordinate_conditional_clause_preservation(pruner):
    """Task A: Verify conditional instructions and subordinate clauses are never stripped."""
    cases = [
        ("Check if you can reproduce the error.", "Check if you can reproduce the error."),
        ("Verify if you can ping the server.", "Verify if you can ping the server."),
        ("Determine if you could access the database.", "Determine if you could access the database."),
        ("Could you please check the API?", "Check the API?"),
        ("If you can, validate the output.", "If you can, validate the output."),
        ("Do not proceed if you cannot verify the result.", "Do not proceed if you cannot verify the result.")
    ]
    for prompt, expected in cases:
        res = pruner.prune(prompt)
        assert res.optimized_prompt == expected, f"Failed on '{prompt}': got '{res.optimized_prompt}' expected '{expected}'"


def test_b_meaningful_uses_of_please(pruner):
    """Task B: Verify meaningful mid-sentence uses of 'please' are preserved."""
    p1 = "Please say please before entering."
    res1 = pruner.prune(p1)
    assert res1.optimized_prompt == "Say please before entering."
    assert "Say please" in res1.optimized_prompt

    p2 = "You must include please in the command."
    res2 = pruner.prune(p2)
    assert res2.optimized_prompt == "You must include please in the command."
    assert "include please" in res2.optimized_prompt


def test_c_explicit_placeholder_collision(pruner):
    """Task C: Prompt contains literal string '__CODE_BLOCK_0__' alongside a fenced block."""
    code = "```python\nx = 100\n```"
    prompt = f"Here is literal placeholder __CODE_BLOCK_0__: {code}. Please review."
    res = pruner.prune(prompt)

    # Both literal string and code block must survive
    assert "__CODE_BLOCK_0__" in res.optimized_prompt
    assert code in res.optimized_prompt
    # Verify collision salting was applied
    assert any("__CODE_BLOCK_0_1__" in r.placeholder for r in res.region_details)


def test_d_multiple_adjacent_fenced_code_blocks(pruner):
    """Task D: Verify multiple adjacent fenced code blocks are separately preserved and restored."""
    block1 = "```python\ndef first(): return 1\n```"
    block2 = "```python\ndef second(): return 2\n```"
    prompt = f"Please inspect these two functions:\n{block1}\n{block2}\nThanks in advance!"
    res = pruner.prune(prompt)

    assert block1 in res.optimized_prompt
    assert block2 in res.optimized_prompt
    fenced_regions = [r for r in res.region_details if r.region_type == "fenced_code"]
    assert len(fenced_regions) == 2
    assert fenced_regions[0].original_text == block1
    assert fenced_regions[1].original_text == block2


def test_e_unclosed_fenced_code_block(pruner):
    """Task E: Unclosed fenced code block must be preserved without corruption or crash."""
    unclosed_code = "```python\nx = 10\ny = 20\n"
    prompt = f"Please check this partial code:\n{unclosed_code}"
    res = pruner.prune(prompt)

    # Content must not be silently removed or corrupted
    assert "x = 10" in res.optimized_prompt
    assert "y = 20" in res.optimized_prompt
    assert "```python" in res.optimized_prompt
    assert "Check this partial code:" in res.optimized_prompt


def test_f_decomposed_unicode_inside_fenced_code(pruner):
    """Task F: Decomposed Unicode (NFD) inside code blocks must retain exact raw code points."""
    # "Café" in NFD: 'C', 'a', 'f', 'e', '\u0301' (5 code points)
    nfd_token = "Caf\u0065\u0301"
    assert len(nfd_token) == 5

    code_block = f"```python\nname = '{nfd_token}'\n```"
    prompt = f"Hello! Please verify this code:\n{code_block}\nThank you!"
    res = pruner.prune(prompt)

    # Protected code block must retain the 5-character NFD sequence, NOT 4-character NFC
    assert nfd_token in res.optimized_prompt
    assert f"name = '{nfd_token}'" in res.optimized_prompt
    for r in res.region_details:
        if r.region_type == "fenced_code":
            assert nfd_token in r.original_text


def test_g_decomposed_unicode_inside_json_strings(pruner):
    """Task G: Decomposed Unicode inside JSON strings must retain exact raw code points."""
    nfd_city = "S\u0061\u0303o Paulo"  # "São" with decomposed tilde (a + \u0303)
    json_block = f'{{\n  "city": "{nfd_city}",\n  "status": "active"\n}}'
    prompt = f"Please check this JSON payload:\n{json_block}\nThanks!"
    res = pruner.prune(prompt)

    assert json_block in res.optimized_prompt
    assert nfd_city in res.optimized_prompt


def test_h_negative_instructions_and_exceptions(pruner):
    """Task H: Negative instructions and exceptions must be preserved completely."""
    prompts = [
        ("Do not remove the API key.", "Do not remove the API key."),
        ("Never modify the original JSON.", "Never modify the original JSON."),
        ("Only proceed if validation succeeds.", "Only proceed if validation succeeds."),
        ("Do not continue unless all tests pass.", "Do not continue unless all tests pass.")
    ]
    for p, expected in prompts:
        res = pruner.prune(p)
        assert res.optimized_prompt == expected


def test_i_mixed_natural_language_and_multiple_protected_regions(pruner):
    """Task I: Mixed prompt with greetings, code, JSON, URLs, paths, constraints, and negative instructions."""
    code = "```python\ndef run(): return True\n```"
    json_str = '{"port": 8080, "host": "127.0.0.1"}'
    prompt = (
        "Hello! Could you please review this microservice setup:\n\n"
        f"{code}\n\n"
        f"Config: {json_str}\n"
        "Endpoint: https://api.service.internal/v1/health\n"
        "Log path: /var/log/service.log\n"
        "MUST: Execution latency <= 50ms with 3 retries.\n"
        "Never delete the backup directory.\n"
        "Thank you so much in advance!"
    )
    res = pruner.prune(prompt)

    # Conversational filler stripped
    assert "Hello!" not in res.optimized_prompt
    assert "Could you please" not in res.optimized_prompt
    assert "Thank you so much in advance!" not in res.optimized_prompt

    # All protected structures and instructions preserved
    assert code in res.optimized_prompt
    assert json_str in res.optimized_prompt
    assert "https://api.service.internal/v1/health" in res.optimized_prompt
    assert "/var/log/service.log" in res.optimized_prompt
    assert "MUST: Execution latency <= 50ms with 3 retries" in res.optimized_prompt
    assert "Never delete the backup directory." in res.optimized_prompt
    assert res.token_reduction > 0
