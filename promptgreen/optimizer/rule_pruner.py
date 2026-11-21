import re
import ast
import json
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any

try:
    import tiktoken
    _TIKTOKEN_AVAILABLE = True
except ImportError:
    _TIKTOKEN_AVAILABLE = False


@dataclass
class ProtectedRegion:
    """Represents a syntactically or semantically critical content block protected from pruning."""
    placeholder: str
    original_text: str
    region_type: str
    start_pos: int = -1
    end_pos: int = -1


@dataclass
class PruningResult:
    """Encapsulates the complete outcome of a rule-based pruning execution."""
    original_prompt: str
    optimized_prompt: str
    masked_prompt: str
    protected_regions: Dict[str, str]
    region_details: List[ProtectedRegion]
    removed_phrases: List[str]
    original_token_count: int
    optimized_token_count: int
    token_reduction: int
    token_reduction_pct: float
    is_exact_token_count: bool
    tokenizer_name: str
    warnings: List[str] = field(default_factory=list)


class RuleBasedPruner:
    """
    PromptGreen v2.0 - Stage 1: Structural & Rule-Based Prompt Pruner.

    Responsibility:
    1. Structural Identification & Immutable Masking:
       - Markdown fenced code blocks (Python, JavaScript, etc.)
       - Python AST code snippets
       - JSON objects, arrays, and schemas
       - YAML configuration blocks
       - XML and HTML elements
       - Inline backtick code snippets
       - File paths (POSIX and Windows)
       - Variable names, functions, and identifiers
       - URLs (HTTP, HTTPS, FTP)
       - Strict numerical constraints and quotas
       - Explicit user requirements and bulleted constraints
    2. Conversational Boilerplate Pruning:
       - Conservative removal of conversational filler, politeness prefixes,
         empty greetings, and redundant closures.
       - Preservation of core directives, contexts, and instructions.
       - Unicode NFC normalization on non-protected text segments.
    3. Collision-Free Deterministic Restoration:
       - Safe placeholder mapping with collision detection.
       - Byte-for-byte exact restoration of all protected content.
       - Atomic rollback fallback if restoration integrity is compromised.
    """

    # Conversational opening greetings & filler prefixes (anchored to sentence / clause beginnings)
    POLITE_PREFIX_PATTERNS = [
        (r"(?i)(?:^|(?<=[.!?\n]))\s*(?:hello|hi|hey|good\s+(?:morning|afternoon|evening)|greetings)\s*[,!.-]*\s*(?:dear\s+ai|ai\s+assistant|assistant|there)?\s*[,!.-]*\s*", "greeting"),
        (r"(?i)(?:^|(?<=[.!?\n]))\s*(?:could|can|would)\s+you\s+(?:please\s+)?(?:kindly\s+)?(?:be\s+so\s+kind\s+as\s+to\s+)?", "polite_modal_request"),
        (r"(?i)(?:^|(?<=[.!?\n]))\s*i\s+(?:would\s+(?:really\s+)?appreciate\s+it\s+if\s+you\s+(?:could|can|would)|am\s+hoping\s+you\s+could|was\s+wondering\s+if\s+you\s+could)\s*", "polite_appreciation_start"),
        (r"(?i)(?:^|(?<=[.!?\n]))\s*if\s+(?:it\s+is\s+not\s+too\s+much\s+trouble|you\s+don't\s+mind)\s*[,]?\s*", "trouble_filler"),
        (r"(?i)(?:^|(?<=[.!?\n]))\s*please\s+(?:try\s+your\s+best\s+to|do\s+your\s+best\s+to|take\s+your\s+time\s+to)\s*", "effort_filler"),
        (r"(?i)(?:^|(?<=[.!?\n]))\s*i\s+would\s+like\s+to\s+(?:request\s+(?:that\s+you\s+)?|ask\s+you\s+to\s+)", "desire_preamble"),
        (r"(?i)(?:^|(?<=[.!?\n]))\s*i\s+(?:just\s+)?wanted\s+to\s+(?:ask\s+(?:you\s+)?(?:to\s+)?|know\s+if\s+you\s+could\s+)", "wanted_to_ask"),
        (r"(?i)(?:^|(?<=[.!?\n]))\s*feel\s+free\s+to\s*", "feel_free"),
        (r"(?i)(?:^|(?<=[.!?\n]))\s*as\s+an\s+ai\s+(?:language\s+model|assistant|expert)\s*[,]?\s*(?:please\s*)?", "ai_role_filler"),
        (r"(?i)(?:^|(?<=[.!?\n]))\s*i\s+am\s+(?:a\s+beginner|new\s+to\s+this)\s+(?:and\s+)?(?:so\s+)?", "beginner_disclaimer"),
        (r"(?i)(?:^|(?<=[.!?\n]))\s*kindly\s+", "kindly_opening"),
        (r"(?i)(?:^|(?<=[.!?\n]))\s*please\s+", "please_opening"),
    ]

    # Conversational polite sign-offs & closures
    POLITE_CLOSURE_PATTERNS = [
        (r"(?i)\bthank\s+you(?:\s+(?:very\s+much|so\s+much|a\s+lot))?(?:\s+in\s+advance)?\s*[,!.-]*\s*$", "thank_you"),
        (r"(?i)\bthanks(?:\s+(?:a\s+lot|again|very\s+much))?(?:\s+in\s+advance)?\s*[,!.-]*\s*$", "thanks"),
        (r"(?i)\bhope\s+this\s+helps\s*[,!.-]*\s*$", "hope_helps"),
        (r"(?i)\bhave\s+a\s+(?:wonderful|great|nice)\s+day\s*[,!.-]*\s*$", "have_a_day"),
        (r"(?i)\blooking\s+forward\s+to\s+your\s+(?:reply|response|answer)\s*[,!.-]*\s*$", "looking_forward"),
        (r"(?i)\blet\s+me\s+know\s+(?:if\s+you\s+have\s+any\s+questions|what\s+you\s+think)\s*[,!.-]*\s*$", "let_me_know"),
        (r"(?i)\bany\s+help\s+(?:would\s+be|is)\s+(?:greatly\s+)?appreciated\s*[,!.-]*\s*$", "help_appreciated")
    ]

    def __init__(self, tokenizer_name: str = "cl100k_base"):
        self.tokenizer_name = tokenizer_name
        self._tiktoken_enc = None
        self._tiktoken_failed = False

        if _TIKTOKEN_AVAILABLE:
            try:
                self._tiktoken_enc = tiktoken.get_encoding(tokenizer_name)
            except Exception:
                self._tiktoken_enc = None
                self._tiktoken_failed = True

    def count_tokens(self, text: str) -> Tuple[int, bool]:
        """
        Counts tokens using tiktoken if available locally without network requests;
        otherwise safely falls back to a standardized 1.3x word-count estimate.

        Returns:
            Tuple[int, bool]: (token_count, is_exact_token_count)
        """
        if not text or not text.strip():
            return 0, True

        if self._tiktoken_enc is not None:
            try:
                return len(self._tiktoken_enc.encode(text)), True
            except Exception:
                pass

        # Fallback heuristic calculation
        words = len(text.split())
        return max(1, int(words * 1.3)), False

    # --------------------------------------------------------------------------
    # REGION 1: STRUCTURAL IDENTIFICATION AND PROTECTION
    # --------------------------------------------------------------------------

    def _generate_placeholder(self, region_type: str, index: int, base_text: str) -> str:
        """Generates a guaranteed collision-free deterministic placeholder."""
        type_prefix_map = {
            "fenced_code": "CODE_BLOCK",
            "inline_code": "INLINE_CODE",
            "json": "JSON_BLOCK",
            "yaml": "YAML_BLOCK",
            "xml_html": "XML_BLOCK",
            "url": "URL",
            "file_path": "PATH",
            "identifier": "IDENTIFIER",
            "numerical_constraint": "NUM_CONSTRAINT",
            "requirement_block": "REQ_BLOCK"
        }
        tag = type_prefix_map.get(region_type, "PROTECTED")
        candidate = f"__{tag}_{index}__"

        # Check for potential collision in the base text
        if candidate not in base_text:
            return candidate

        # Collision avoidance salt
        salt = 1
        while f"__{tag}_{index}_{salt}__" in base_text:
            salt += 1
        return f"__{tag}_{index}_{salt}__"

    def _extract_fenced_code(self, text: str) -> Tuple[str, List[ProtectedRegion]]:
        """Extracts and masks markdown fenced code blocks (both closed and unclosed)."""
        regions: List[ProtectedRegion] = []
        # Pattern matches both ```lang\ncode``` and ~~~lang\ncode~~~
        pattern_closed = re.compile(r"(```[a-zA-Z0-9_-]*\n[\s\S]*?```|~~~[a-zA-Z0-9_-]*\n[\s\S]*?~~~|```[\s\S]*?```)")

        def repl(match: re.Match) -> str:
            original = match.group(0)
            idx = len(regions)
            placeholder = self._generate_placeholder("fenced_code", idx, text)
            regions.append(ProtectedRegion(
                placeholder=placeholder,
                original_text=original,
                region_type="fenced_code",
                start_pos=match.start(),
                end_pos=match.end()
            ))
            return placeholder

        masked_text = pattern_closed.sub(repl, text)

        # Check for unclosed fenced code block (e.g., prompt terminates before closing fence)
        pattern_unclosed = re.compile(r"((?:```|~~~)[a-zA-Z0-9_-]*\s*\n[\s\S]*$)")
        unclosed_match = pattern_unclosed.search(masked_text)
        if unclosed_match:
            original = unclosed_match.group(0)
            idx = len(regions)
            placeholder = self._generate_placeholder("fenced_code", idx, text)
            regions.append(ProtectedRegion(
                placeholder=placeholder,
                original_text=original,
                region_type="fenced_code",
                start_pos=unclosed_match.start(),
                end_pos=unclosed_match.end()
            ))
            masked_text = masked_text[:unclosed_match.start()] + placeholder

        return masked_text, regions

    def _extract_xml_html(self, text: str) -> Tuple[str, List[ProtectedRegion]]:
        """Extracts XML and HTML tags, structures, and schemas."""
        regions: List[ProtectedRegion] = []
        # Matches full tags: <tag ...>...</tag> or self-closing <tag ... />
        pattern = re.compile(
            r"(<([a-zA-Z][a-zA-Z0-9_-]*)\b[^>]*>[\s\S]*?<\/\2>|<[a-zA-Z][a-zA-Z0-9_-]*\b[^>]*\/>)"
        )

        def repl(match: re.Match) -> str:
            original = match.group(0)
            idx = len(regions)
            placeholder = self._generate_placeholder("xml_html", idx, text)
            regions.append(ProtectedRegion(
                placeholder=placeholder,
                original_text=original,
                region_type="xml_html",
                start_pos=match.start(),
                end_pos=match.end()
            ))
            return placeholder

        masked_text = pattern.sub(repl, text)
        return masked_text, regions

    def _extract_json_blocks(self, text: str) -> Tuple[str, List[ProtectedRegion]]:
        """Extracts syntactically valid JSON objects and arrays."""
        regions: List[ProtectedRegion] = []

        # Find curly brace blocks that parse as valid JSON
        # Look for candidate blocks starting with { and ending with }
        def scan_json_candidates(s: str) -> List[Tuple[int, int, str]]:
            candidates = []
            n = len(s)
            i = 0
            while i < n:
                if s[i] == '{':
                    start = i
                    brace_count = 0
                    in_str = False
                    escape = False
                    j = i
                    while j < n:
                        c = s[j]
                        if in_str:
                            if escape:
                                escape = False
                            elif c == '\\':
                                escape = True
                            elif c == '"':
                                in_str = False
                        else:
                            if c == '"':
                                in_str = True
                            elif c == '{':
                                brace_count += 1
                            elif c == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    snippet = s[start:j+1]
                                    # Verify if it parses as valid JSON
                                    try:
                                        parsed = json.loads(snippet)
                                        if isinstance(parsed, (dict, list)):
                                            candidates.append((start, j+1, snippet))
                                            i = j
                                    except Exception:
                                        pass
                                    break
                        j += 1
                i += 1
            return candidates

        json_spans = scan_json_candidates(text)
        if not json_spans:
            return text, regions

        # Replace spans in reverse order to preserve string offsets
        result_chars = list(text)
        for idx, (start, end, original) in enumerate(json_spans):
            placeholder = self._generate_placeholder("json", idx, text)
            regions.append(ProtectedRegion(
                placeholder=placeholder,
                original_text=original,
                region_type="json",
                start_pos=start,
                end_pos=end
            ))

        # Reconstruct masked text with placeholders
        offset = 0
        new_text_parts = []
        last_end = 0
        for r in regions:
            new_text_parts.append(text[last_end:r.start_pos])
            new_text_parts.append(r.placeholder)
            last_end = r.end_pos
        new_text_parts.append(text[last_end:])
        masked_text = "".join(new_text_parts)

        return masked_text, regions

    def _extract_yaml_blocks(self, text: str) -> Tuple[str, List[ProtectedRegion]]:
        """Extracts YAML configuration blocks denoted by --- or multiline key-value indentation."""
        regions: List[ProtectedRegion] = []
        # Pattern for explicit YAML document: --- \n ... (until next blank line or end)
        pattern = re.compile(r"(^---\s*\n(?:[ \t]*[a-zA-Z0-9_-]+:[^\n]*\n)+)", re.MULTILINE)

        def repl(match: re.Match) -> str:
            original = match.group(0)
            idx = len(regions)
            placeholder = self._generate_placeholder("yaml", idx, text)
            regions.append(ProtectedRegion(
                placeholder=placeholder,
                original_text=original,
                region_type="yaml",
                start_pos=match.start(),
                end_pos=match.end()
            ))
            return placeholder

        masked_text = pattern.sub(repl, text)
        return masked_text, regions

    def _extract_inline_code(self, text: str) -> Tuple[str, List[ProtectedRegion]]:
        """Extracts backtick inline code expressions (`code`)."""
        regions: List[ProtectedRegion] = []
        pattern = re.compile(r"(`[^`\n]+`)")

        def repl(match: re.Match) -> str:
            original = match.group(0)
            idx = len(regions)
            placeholder = self._generate_placeholder("inline_code", idx, text)
            regions.append(ProtectedRegion(
                placeholder=placeholder,
                original_text=original,
                region_type="inline_code",
                start_pos=match.start(),
                end_pos=match.end()
            ))
            return placeholder

        masked_text = pattern.sub(repl, text)
        return masked_text, regions

    def _extract_urls(self, text: str) -> Tuple[str, List[ProtectedRegion]]:
        """Extracts HTTP, HTTPS, and FTP web URLs."""
        regions: List[ProtectedRegion] = []
        pattern = re.compile(r"(https?:\/\/[^\s<>\"]+|ftp:\/\/[^\s<>\"]+)")

        def repl(match: re.Match) -> str:
            original = match.group(0)
            # Trim trailing punctuation if accidentally captured
            trailing = ""
            while original and original[-1] in ".,;!?)]":
                trailing = original[-1] + trailing
                original = original[:-1]

            idx = len(regions)
            placeholder = self._generate_placeholder("url", idx, text)
            regions.append(ProtectedRegion(
                placeholder=placeholder,
                original_text=original,
                region_type="url",
                start_pos=match.start(),
                end_pos=match.start() + len(original)
            ))
            return placeholder + trailing

        masked_text = pattern.sub(repl, text)
        return masked_text, regions

    def _extract_file_paths(self, text: str) -> Tuple[str, List[ProtectedRegion]]:
        """Extracts Windows and POSIX absolute and relative file paths."""
        regions: List[ProtectedRegion] = []
        # Matches POSIX paths: /path/to/file or ./relative/path.ext or ../path
        # Matches Windows paths: C:\dir\file.ext or D:/dir/file.ext
        pattern = re.compile(
            r"(?:\b[a-zA-Z]:[\\/](?:[a-zA-Z0-9_.\-]+[\\/])+[a-zA-Z0-9_.\-]+\b"
            r"|(?:\.{1,2}[\\/]|[\\/])[a-zA-Z0-9_.\-]+(?:[\\/][a-zA-Z0-9_.\-]+)*\.[a-zA-Z0-9_]{1,8}\b"
            r"|\b[a-zA-Z0-9_.\-]+[\\/][a-zA-Z0-9_.\-]+(?:[\\/][a-zA-Z0-9_.\-]+)*\.[a-zA-Z0-9_]{1,8}\b)"
        )

        def repl(match: re.Match) -> str:
            original = match.group(0)
            # Avoid protecting standard words with dots like e.g. or etc.
            if original.lower() in ["e.g.", "i.e.", "etc.", "vs.", "al."]:
                return original

            idx = len(regions)
            placeholder = self._generate_placeholder("file_path", idx, text)
            regions.append(ProtectedRegion(
                placeholder=placeholder,
                original_text=original,
                region_type="file_path",
                start_pos=match.start(),
                end_pos=match.end()
            ))
            return placeholder

        masked_text = pattern.sub(repl, text)
        return masked_text, regions

    def _extract_numerical_constraints(self, text: str) -> Tuple[str, List[ProtectedRegion]]:
        """Extracts strict numerical limits, timings, budgets, and quota constraints."""
        regions: List[ProtectedRegion] = []
        # Patterns like: 30s, 500ms, 100MB, 2.5GB, <= 0.05, 3 retries, max 100 words, limit 5
        pattern = re.compile(
            r"(?:\b(?:max(?:imum)?|min(?:imum)?|limit|at\s+least|at\s+most|up\s+to|within|less\s+than|more\s+than|top)\s+\d+(?:\.\d+)?\s*(?:tokens?|words?|items?|seconds?|minutes?|hours?|ms|MB|GB|KB|%|lines?|retries)?\b"
            r"|\b(?:<=?|>=?|==|!=)\s*\d+(?:\.\d+)?\b"
            r"|\b\d+(?:\.\d+)?\s*(?:ms|s|sec|seconds?|min|minutes?|hrs?|hours?|MB|GB|KB|TB|%|percent)\b"
            r"|\b\d+\s+(?:retries|attempts|epochs|iterations)\b)"
            , re.IGNORECASE
        )

        def repl(match: re.Match) -> str:
            original = match.group(0)
            idx = len(regions)
            placeholder = self._generate_placeholder("numerical_constraint", idx, text)
            regions.append(ProtectedRegion(
                placeholder=placeholder,
                original_text=original,
                region_type="numerical_constraint",
                start_pos=match.start(),
                end_pos=match.end()
            ))
            return placeholder

        masked_text = pattern.sub(repl, text)
        return masked_text, regions

    def _extract_code_identifiers(self, text: str) -> Tuple[str, List[ProtectedRegion]]:
        """Extracts programming identifiers (snake_case, camelCase, CONSTANT_CASE, method calls)."""
        regions: List[ProtectedRegion] = []
        # Look for tokens with explicit programming characteristics:
        # 1. snake_case with at least one underscore (e.g. user_id, prompt_records)
        # 2. CONST_CASE with all upper and underscore (e.g. MAX_BUFFER_SIZE)
        # 3. camelCase with lower followed by upper (e.g. parseDiff, getUserProfile)
        # 4. Method / property calls (e.g. model.predict, config.timeout)
        pattern = re.compile(
            r"(?:\b[a-zA-Z_]\w*\.[a-zA-Z_]\w*(?:\(\))?\b"
            r"|\b[a-z]+[A-Z][a-zA-Z0-9]*\b"
            r"|\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b"
            r"|\b[a-z0-9]+_[a-z0-9_]+\b)"
        )

        def repl(match: re.Match) -> str:
            original = match.group(0)
            # Ignore standard English contractions like don't, can't
            if "'" in original:
                return original

            idx = len(regions)
            placeholder = self._generate_placeholder("identifier", idx, text)
            regions.append(ProtectedRegion(
                placeholder=placeholder,
                original_text=original,
                region_type="identifier",
                start_pos=match.start(),
                end_pos=match.end()
            ))
            return placeholder

        masked_text = pattern.sub(repl, text)
        return masked_text, regions

    def _extract_requirement_blocks(self, text: str) -> Tuple[str, List[ProtectedRegion]]:
        """Extracts explicit constraint headers (e.g., 'Must:', 'Required:', 'Do not:')."""
        regions: List[ProtectedRegion] = []
        pattern = re.compile(
            r"(?m)^(?:[-*]\s*)?(?:MUST|REQUIRED|DO NOT|NEVER|ALWAYS|CRITICAL|IMPORTANT|CONSTRAINT):\s*[^\n]+"
        )

        def repl(match: re.Match) -> str:
            original = match.group(0)
            idx = len(regions)
            placeholder = self._generate_placeholder("requirement_block", idx, text)
            regions.append(ProtectedRegion(
                placeholder=placeholder,
                original_text=original,
                region_type="requirement_block",
                start_pos=match.start(),
                end_pos=match.end()
            ))
            return placeholder

        masked_text = pattern.sub(repl, text)
        return masked_text, regions

    # --------------------------------------------------------------------------
    # PUBLIC MASK AND RESTORE INTERFACES
    # --------------------------------------------------------------------------

    def mask_protected_regions(self, prompt: str) -> Tuple[str, Dict[str, str], List[ProtectedRegion]]:
        """
        Sequentially identifies and masks all protected structural regions.

        Order of extraction ensures nested structures (such as code blocks containing
        URLs or identifiers) are safely encapsulated in their outer container.

        Returns:
            Tuple[str, Dict[str, str], List[ProtectedRegion]]:
                - masked_text
                - placeholder_to_original_map
                - detailed_region_metadata_list
        """
        all_regions: List[ProtectedRegion] = []
        current_text = prompt

        # 1. Fenced Code Blocks (Highest precedence)
        current_text, r1 = self._extract_fenced_code(current_text)
        all_regions.extend(r1)

        # 2. XML / HTML Tags
        current_text, r2 = self._extract_xml_html(current_text)
        all_regions.extend(r2)

        # 3. YAML Configuration Blocks
        current_text, r3 = self._extract_yaml_blocks(current_text)
        all_regions.extend(r3)

        # 4. JSON Objects & Schemas
        current_text, r4 = self._extract_json_blocks(current_text)
        all_regions.extend(r4)

        # 5. Inline Code (`code`)
        current_text, r5 = self._extract_inline_code(current_text)
        all_regions.extend(r5)

        # 6. Requirement Blocks ('Must: ...')
        current_text, r6 = self._extract_requirement_blocks(current_text)
        all_regions.extend(r6)

        # 7. Web URLs
        current_text, r7 = self._extract_urls(current_text)
        all_regions.extend(r7)

        # 8. File Paths
        current_text, r8 = self._extract_file_paths(current_text)
        all_regions.extend(r8)

        # 9. Numerical Constraints
        current_text, r9 = self._extract_numerical_constraints(current_text)
        all_regions.extend(r9)

        # 10. Code Identifiers
        current_text, r10 = self._extract_code_identifiers(current_text)
        all_regions.extend(r10)

        # Map placeholder -> original text
        placeholder_map = {r.placeholder: r.original_text for r in all_regions}
        return current_text, placeholder_map, all_regions

    def restore_protected_regions(self, masked_text: str, placeholder_map: Dict[str, str]) -> Tuple[str, bool]:
        """
        Restores all protected regions from placeholders back to their byte-for-byte original content.

        Returns:
            Tuple[str, bool]: (restored_text, is_fully_restored)
        """
        if not placeholder_map:
            return masked_text, True

        restored = masked_text
        for placeholder, original in placeholder_map.items():
            if placeholder in restored:
                restored = restored.replace(placeholder, original)

        # Verify that no placeholders remain un-restored
        remaining_placeholders = [p for p in placeholder_map if p in restored]
        return restored, (len(remaining_placeholders) == 0)

    # --------------------------------------------------------------------------
    # REGION 2: CONSERVATIVE RULE-BASED PRUNING
    # --------------------------------------------------------------------------

    def prune_boilerplate(self, masked_text: str) -> Tuple[str, List[str]]:
        """
        Conservative pruning of conversational language on masked text.
        Preserves all placeholders and core instructions intact.
        """
        text = masked_text
        removed_phrases: List[str] = []

        # 1. Strip polite openings and conversational preambles
        for pattern, label in self.POLITE_PREFIX_PATTERNS:
            matches = list(re.finditer(pattern, text))
            if matches:
                for m in matches:
                    matched_str = m.group(0).strip()
                    if matched_str:
                        removed_phrases.append(f"prefix:{label} ('{matched_str}')")
                text = re.sub(pattern, " ", text)

        # 2. Strip polite closures and sign-offs
        for pattern, label in self.POLITE_CLOSURE_PATTERNS:
            matches = list(re.finditer(pattern, text))
            if matches:
                for m in matches:
                    matched_str = m.group(0).strip()
                    if matched_str:
                        removed_phrases.append(f"closure:{label} ('{matched_str}')")
                text = re.sub(pattern, " ", text)

        # 3. Clean consecutive spaces while preserving newline structure
        lines = []
        for line in text.split("\n"):
            # Collapse multiple spaces within the line
            cleaned_line = re.sub(r"[ \t]+", " ", line).strip()
            lines.append(cleaned_line)

        # 4. Collapse excessive blank lines (more than 2 consecutive newlines -> 2 newlines)
        reconstructed = "\n".join(lines)
        reconstructed = re.sub(r"\n{3,}", "\n\n", reconstructed).strip()

        # 5. Fix sentence casing if an opening was removed (e.g. "explain how..." -> "Explain how...")
        if reconstructed and reconstructed[0].islower():
            reconstructed = reconstructed[0].upper() + reconstructed[1:]

        return reconstructed, removed_phrases

    # --------------------------------------------------------------------------
    # PRIMARY EXECUTION ENTRYPOINT
    # --------------------------------------------------------------------------

    def prune(self, prompt: str) -> PruningResult:
        """
        Executes Stage 1 structural protection, conservative pruning, and safe restoration.

        Args:
            prompt (str): Raw input prompt string.

        Returns:
            PruningResult: Dataclass containing optimized prompt, token deltas,
                           protected region metadata, and safety warnings.
        """
        warnings: List[str] = []

        # Edge case: Empty or whitespace input
        if not prompt or not prompt.strip():
            return PruningResult(
                original_prompt=prompt,
                optimized_prompt=prompt,
                masked_prompt="",
                protected_regions={},
                region_details=[],
                removed_phrases=[],
                original_token_count=0,
                optimized_token_count=0,
                token_reduction=0,
                token_reduction_pct=0.0,
                is_exact_token_count=True,
                tokenizer_name=self.tokenizer_name if self._tiktoken_enc else "fallback_word_ratio_1.3x",
                warnings=[]
            )

        orig_tokens, is_exact_orig = self.count_tokens(prompt)
        if not is_exact_orig and not self._tiktoken_failed:
            warnings.append("Tiktoken unavailable; token counts calculated via 1.3x word-count estimate.")

        try:
            # Step 1: Preserve raw original prompt
            raw_prompt = prompt

            # Step 2: Structural Masking from raw prompt (protecting code/JSON without pre-normalization)
            masked_text, placeholder_map, region_details = self.mask_protected_regions(raw_prompt)

            # Step 3: Normalize only unprotected natural-language text
            norm_masked_text = unicodedata.normalize("NFC", masked_text)

            # Step 4: Conservative Rule-Based Pruning on normalized masked text
            pruned_masked, removed_phrases = self.prune_boilerplate(norm_masked_text)

            # Step 5: Deterministic Content Restoration from raw un-normalized content
            restored_prompt, is_success = self.restore_protected_regions(pruned_masked, placeholder_map)

            # Step 6 & 7: Integrity Verification & Atomic Fallback Rollback
            if not is_success:
                warnings.append("Restoration integrity verification failed; fell back safely to original prompt.")
                restored_prompt = raw_prompt

            opt_tokens, is_exact_opt = self.count_tokens(restored_prompt)
            reduction = orig_tokens - opt_tokens
            reduction_pct = round((reduction / max(1, orig_tokens)) * 100.0, 2)

            return PruningResult(
                original_prompt=prompt,
                optimized_prompt=restored_prompt,
                masked_prompt=masked_text,
                protected_regions=placeholder_map,
                region_details=region_details,
                removed_phrases=removed_phrases,
                original_token_count=orig_tokens,
                optimized_token_count=opt_tokens,
                token_reduction=reduction,
                token_reduction_pct=reduction_pct,
                is_exact_token_count=is_exact_orig and is_exact_opt,
                tokenizer_name=self.tokenizer_name if is_exact_orig else "fallback_word_ratio_1.3x",
                warnings=warnings
            )

        except Exception as e:
            # Absolute Safety Fallback: Guarantee no unhandled crashes
            warnings.append(f"Unexpected exception during pruning ({type(e).__name__}: {str(e)}); safely returning original prompt.")
            return PruningResult(
                original_prompt=prompt,
                optimized_prompt=prompt,
                masked_prompt=prompt,
                protected_regions={},
                region_details=[],
                removed_phrases=[],
                original_token_count=orig_tokens,
                optimized_token_count=orig_tokens,
                token_reduction=0,
                token_reduction_pct=0.0,
                is_exact_token_count=is_exact_orig,
                tokenizer_name=self.tokenizer_name if is_exact_orig else "fallback_word_ratio_1.3x",
                warnings=warnings
            )
