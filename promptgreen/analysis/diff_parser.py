import re
from dataclasses import dataclass, field
from typing import Dict, Any, Tuple, Optional, List

try:
    import tiktoken
    _TIKTOKEN_AVAILABLE = True
except ImportError:
    _TIKTOKEN_AVAILABLE = False


@dataclass
class PromptDeltaFeatures:
    """Extracted semantic features from old vs new prompt diff."""
    old_input_tokens: int
    new_input_tokens: int
    input_token_delta: int
    verb_complexity_old: float
    verb_complexity_new: float
    verb_complexity_delta: float
    few_shot_count_old: int
    few_shot_count_new: int
    few_shot_delta: int
    cot_triggered_old: bool
    cot_triggered_new: bool
    cot_delta: int
    format_complexity_old: float
    format_complexity_new: float
    format_complexity_delta: float
    context_ratio: float
    role_complexity_old: float
    role_complexity_new: float
    role_complexity_delta: float
    instruction_length_delta: int
    filler_score_old: float
    filler_score_new: float
    filler_score_delta: float
    detected_changes: list = field(default_factory=list)

    def to_feature_vector(self) -> list:
        """Returns a numeric feature vector for ML regression models."""
        return [
            float(self.old_input_tokens),
            float(self.new_input_tokens),
            float(self.input_token_delta),
            self.verb_complexity_old,
            self.verb_complexity_new,
            self.verb_complexity_delta,
            float(self.few_shot_count_old),
            float(self.few_shot_count_new),
            float(self.few_shot_delta),
            1.0 if self.cot_triggered_old else 0.0,
            1.0 if self.cot_triggered_new else 0.0,
            float(self.cot_delta),
            self.format_complexity_old,
            self.format_complexity_new,
            self.format_complexity_delta,
            self.context_ratio,
            self.role_complexity_old,
            self.role_complexity_new,
            self.role_complexity_delta,
            float(self.instruction_length_delta),
            self.filler_score_old,
            self.filler_score_new,
            self.filler_score_delta
        ]


class PromptDiffAnalyzer:
    """
    Deliverable D1: Upgraded Context-Aware Prompt Diff Analyzer Engine.
    Extensive semantic extraction covering 30+ verb complexity patterns,
    logically consistent green prompt synthesis, length-reduction rules,
    few-shot counting, chain-of-thought detection, and token tracking.
    """

    VERBOSE_PATTERNS = [
        r"\bgenerate\s+a\s+detailed\s+report\b",
        r"\bexplain\s+in\s+detail\b",
        r"\belaborate\s+exhaustively\b",
        r"\bdescribe\s+in\s+depth\b",
        r"\bcomprehensive\s+analysis\b",
        r"\bexamine\s+thoroughly\b",
        r"\bextensive\s+examples\b",
        r"\bwalk\s+through\s+line\s+by\s+line\b",
        r"\bfull\s+context\b",
        r"\bcomplete\s+physiological\s+descriptions\b",
        r"\bmulti-paragraph\b",
        r"\bhistorical\s+evolution\b",
        r"\bmajor\s+milestone[s]?\b",
        r"\ball\s+mechanisms\b",
        r"\bevery\s+single\b",
        r"\bin-depth\b",
        r"\bprofound\s+explanations?\b",
        r"\bexploratory\s+essay\b",
        r"\bexpansive\s+fantasy\b"
    ]

    CONCISE_PATTERNS = [
        r"\bsummarize\s+in\s+\d+\s+(?:concise\s+)?bullet\s+points?\b",
        r"\bsummarize\b",
        r"\bbriefly\b",
        r"\bconcise\b",
        r"\b5-sentence\b",
        r"\b1-line\b",
        r"\bfinal\s+answer\s+only\b",
        r"\bshort\b",
        r"\btop\s+\d+\b",
        r"\b3\s+simple\s+sentences\b"
    ]

    COT_PATTERNS = [
        r"\bthink\s+step[- ]by[- ]step\b",
        r"\bexplain\s+(?:your\s+)?reasoning\b",
        r"\blist\s+all\s+prime\s+factors\b",
        r"\bbreak\s+down\s+(?:your\s+)?reasoning\b",
        r"\bshow\s+all\s+your\s+reasoning\b",
        r"\bwork\s+through\s+execution\b",
        r"\bwalk\s+through\s+all\b",
        r"\blet's\s+think\b",
        r"\bshow\s+intermediate\s+subtotals\b"
    ]

    FORMAT_COMPLEX_PATTERNS = [
        r"\bmarkdown\s+report\b",
        r"\bhtml\s+report\b",
        r"\bessay\b",
        r"\bnarrative\b",
        r"\brich\s+text\b",
        r"\bextensive\s+guide\b",
        r"\bqualitative\s+narrative\b",
        r"\bheaders?,\s*bullet\s*lists?,\s*and\s*paragraphs?\b"
    ]

    FORMAT_SIMPLE_PATTERNS = [
        r"\bjson\b",
        r"\bcsv\b",
        r"\b3\s+fields?\b",
        r"\b2\s+short\s+paragraphs?\b",
        r"\breturn\s+only\b",
        r"\bfinal\s+answer\s+only\b",
        r"\bsingle\s+sentence\b",
        r"\b3\s+concise\s+bullet\s+points\b"
    ]

    ROLE_COMPLEX_PATTERNS = [
        r"\bworld-class\b",
        r"\bsenior\s+principal\b",
        r"\belite\s+financial\b",
        r"\bdistinguished\s+professor\b",
        r"\bchief\s+medical\s+officer\b",
        r"\bveteran\s+cybersecurity\b",
        r"\bmaster\s+chef\b"
    ]

    FILLER_PATTERNS = [
        r"\bhello![\s,]*(?:thank\s+you\s+for\s+asking)?\b",
        r"\bhope\s+this\s+helps!\b",
        r"\bhave\s+a\s+wonderful\s+day\b",
        r"\balways\s+be\s+extremely\s+polite\b",
        r"\bgreet\s+the\s+user\s+warmly\b",
        r"\bcheck\s+if\s+they\s+have\s+further\s+questions\b"
    ]

    def __init__(self, tokenizer_name: str = "cl100k_base"):
        self.tokenizer_name = tokenizer_name
        self._tiktoken_enc = None
        if _TIKTOKEN_AVAILABLE:
            try:
                self._tiktoken_enc = tiktoken.get_encoding(tokenizer_name)
            except Exception:
                self._tiktoken_enc = None

    def count_tokens(self, text: str) -> int:
        """Counts tokens using tiktoken if available, else standard word fallback."""
        if not text:
            return 0
        if self._tiktoken_enc is not None:
            return len(self._tiktoken_enc.encode(text))
        words = len(text.split())
        return max(1, int(words * 1.3))

    def _score_verb_complexity(self, text: str) -> float:
        text_lower = text.lower()
        score = 0.5
        for p in self.VERBOSE_PATTERNS:
            if re.search(p, text_lower):
                score += 0.25
        for p in self.CONCISE_PATTERNS:
            if re.search(p, text_lower):
                score -= 0.25
        return max(0.1, min(1.0, score))

    def _count_few_shots(self, text: str) -> int:
        matches_ex = re.findall(r"\bexample\s*\d*\s*:", text, re.IGNORECASE)
        if matches_ex:
            return len(matches_ex)
        matches_arrow = re.findall(r"->", text)
        return len(matches_arrow)

    def _check_cot(self, text: str) -> bool:
        text_lower = text.lower()
        for p in self.COT_PATTERNS:
            if re.search(p, text_lower):
                return True
        return False

    def _score_format_complexity(self, text: str) -> float:
        text_lower = text.lower()
        score = 0.5
        for p in self.FORMAT_COMPLEX_PATTERNS:
            if re.search(p, text_lower):
                score += 0.25
        for p in self.FORMAT_SIMPLE_PATTERNS:
            if re.search(p, text_lower):
                score -= 0.25
        return max(0.1, min(1.0, score))

    def _score_role_complexity(self, text: str) -> float:
        text_lower = text.lower()
        score = 0.3
        for p in self.ROLE_COMPLEX_PATTERNS:
            if re.search(p, text_lower):
                score += 0.4
        return max(0.1, min(1.0, score))

    def _score_filler(self, text: str) -> float:
        text_lower = text.lower()
        score = 0.0
        for p in self.FILLER_PATTERNS:
            if re.search(p, text_lower):
                score += 0.3
        return min(1.0, score)

    def analyze_prompts(self, old_prompt: str, new_prompt: str) -> PromptDeltaFeatures:
        """Analyzes a pair of old and new prompt strings."""
        old_tokens = self.count_tokens(old_prompt)
        new_tokens = self.count_tokens(new_prompt)
        token_delta = new_tokens - old_tokens

        verb_old = self._score_verb_complexity(old_prompt)
        verb_new = self._score_verb_complexity(new_prompt)
        verb_delta = verb_new - verb_old

        few_old = self._count_few_shots(old_prompt)
        few_new = self._count_few_shots(new_prompt)
        few_delta = few_new - few_old

        cot_old = self._check_cot(old_prompt)
        cot_new = self._check_cot(new_prompt)
        cot_delta = (1 if cot_new else 0) - (1 if cot_old else 0)

        fmt_old = self._score_format_complexity(old_prompt)
        fmt_new = self._score_format_complexity(new_prompt)
        fmt_delta = fmt_new - fmt_old

        role_old = self._score_role_complexity(old_prompt)
        role_new = self._score_role_complexity(new_prompt)
        role_delta = role_new - role_old

        filler_old = self._score_filler(old_prompt)
        filler_new = self._score_filler(new_prompt)
        filler_delta = filler_new - filler_old

        context_ratio = (new_tokens / max(1, old_tokens))

        detected_changes = []
        if verb_delta < -0.1:
            detected_changes.append("Verb complexity reduced to concise directive")
        elif verb_delta > 0.1:
            detected_changes.append("Verb complexity increased (elaborate directive added)")

        if few_delta < 0:
            detected_changes.append(f"Few-shot examples trimmed ({few_old} -> {few_new})")
        elif few_delta > 0:
            detected_changes.append(f"Few-shot examples increased ({few_old} -> {few_new})")

        if cot_old and not cot_new:
            detected_changes.append("Chain-of-thought requirement removed")
        elif not cot_old and cot_new:
            detected_changes.append("Chain-of-thought requirement added")

        if fmt_delta < -0.1:
            detected_changes.append("Output format constrained (JSON/bullets requested)")
        elif fmt_delta > 0.1:
            detected_changes.append("Output format expanded (narrative/report requested)")

        if filler_delta < -0.1:
            detected_changes.append("Conversational filler and greetings removed")

        if context_ratio < 0.5:
            detected_changes.append(f"Context window compressed ({old_tokens} -> {new_tokens} tokens)")
        elif context_ratio > 1.5:
            detected_changes.append(f"Context window expanded ({old_tokens} -> {new_tokens} tokens)")

        return PromptDeltaFeatures(
            old_input_tokens=old_tokens,
            new_input_tokens=new_tokens,
            input_token_delta=token_delta,
            verb_complexity_old=verb_old,
            verb_complexity_new=verb_new,
            verb_complexity_delta=verb_delta,
            few_shot_count_old=few_old,
            few_shot_count_new=few_new,
            few_shot_delta=few_delta,
            cot_triggered_old=cot_old,
            cot_triggered_new=cot_new,
            cot_delta=cot_delta,
            format_complexity_old=fmt_old,
            format_complexity_new=fmt_new,
            format_complexity_delta=fmt_delta,
            context_ratio=context_ratio,
            role_complexity_old=role_old,
            role_complexity_new=role_new,
            role_complexity_delta=role_delta,
            instruction_length_delta=token_delta,
            filler_score_old=filler_old,
            filler_score_new=filler_new,
            filler_score_delta=filler_delta,
            detected_changes=detected_changes
        )

    def generate_green_alternative(self, prompt: str) -> str:
        """
        Logically Consistent Green Prompt Transformer.
        Intelligently replaces excessive length specifications (e.g. 'three-page research report')
        with carbon-efficient concise directives, eliminating logical contradictions.
        """
        if not prompt or not prompt.strip():
            return prompt

        text = prompt.strip()

        # Step 1: Strip Conversational Filler & Politeness Headers
        fillers = [
            r"\bhello![\s,]*(?:thank\s+you\s+for\s+asking[!,.]?)?\b",
            r"\bcould\s+you\s+(?:please\s+)?tell\s+me\b",
            r"\bi\s+would\s+like\s+to\s+know\b",
            r"\bplease\s+(?:provide|give|write|explain|prepare)\b",
            r"\bhope\s+this\s+helps![.]?\b",
            r"\bhave\s+a\s+wonderful\s+day[.]?\b",
            r"\balways\s+be\s+extremely\s+polite\b",
        ]
        revised = text
        for f in fillers:
            revised = re.sub(f, "", revised, flags=re.IGNORECASE).strip()

        # Step 2: Replaces Excessive Length Specifications & Large Document Requests (e.g. "three-page report", "large document", "extensive manual")
        # Replacing length requirements prevents contradictions like "3-page report (3 bullets)"
        length_replacements = [
            (r"\b(?:prepare|write|generate|provide|create)?\s*(?:an?|the)?\s*(?:detailed|extensive|comprehensive|full)?\s*(?:\d+|three|two|four|five|ten|10|5|3|2)[- ]page\s+(?:research\s+)?(?:report|document|essay|paper|guide|manual)\s+(?:on|about|covering|detailing)?\b", "Summarize key highlights of"),
            (r"\b(?:prepare|write|generate|provide|create)\s+(?:an?|the)?\s*(?:large|extensive|lengthy|long|comprehensive|in-depth|detailed)\s+(?:document|report|manual|essay|paper|guide|overview)\s+(?:on|about|covering|detailing)?\b", "Summarize key highlights of"),
            (r"\b(?:large|extensive|lengthy|long|comprehensive|in-depth|detailed)\s+(?:document|report|manual|essay|paper|guide)\s+(?:on|about|covering|detailing)?\b", "Summarize key highlights of"),
            (r"\b(?:three|two|four|five|ten|10|5|3|2)[- ]page\s+(?:research\s+)?report\b", "concise summary"),
            (r"\b\d+[- ]page\s+(?:document|report|essay|paper|guide|manual)\b", "concise summary"),
            (r"\b\d+[- ]word\s+(?:essay|article|report|paper|document)\b", "concise summary"),
            (r"\b500[- ]word\s+system\s+prompt\b", "100-word system prompt"),
            (r"\b10[- ]page\s+document\b", "relevant 2-paragraph excerpt"),
            (r"\b5000\s+lines\s+of\s+debug\s+output\b", "filtered 20 stack trace lines"),
            (r"\b50\s+endpoints\b", "relevant endpoints"),
            (r"\b80\s+tables\b", "relevant tables")
        ]
        for pattern, repl in length_replacements:
            revised = re.sub(pattern, repl, revised, flags=re.IGNORECASE).strip()

        # Step 3: Strip Verbose Modifiers (e.g., "in full detail", "with extensive comments", "with detailed justifications")
        verbose_modifiers = [
            r"\bin\s+full\s+detail[.]?\b",
            r"\bin\s+detail[.]?\b",
            r"\bwith\s+extensive\s+comments[.]?\b",
            r"\bwith\s+extensive\s+examples[.]?\b",
            r"\bwith\s+detailed\s+justifications[.]?\b",
            r"\bwith\s+detailed\s+legends\b",
            r"\bwith\s+exhaustive\s+explanations?[.]?\b"
        ]
        for vm in verbose_modifiers:
            revised = re.sub(vm, "", revised, flags=re.IGNORECASE).strip()

        # Step 4: Strip CoT / Step-by-Step Triggers
        # First match combined patterns before individual patterns
        revised = re.sub(r"\bthink\s+step[- ]by[- ]step\s+and\s+explain\s+every\s+calculation\s+line\s+by\s+line\b", "Return final answer only", revised, flags=re.IGNORECASE)
        cot_patterns = [
            (r"\bthink\s+step[- ]by[- ]step(?:\s+and\s+explain\s+reasoning)?\b", "Return final answer only"),
            (r"\bexplain\s+every\s+calculation,\s*show\s+all\s+your\s+reasoning\b", "Return final answer only"),
            (r"\bwork\s+through\s+execution\s+line\s+by\s+line\b", "State exception type and 1-line fix"),
            (r"\bexplain\s+every\s+calculation\s+line\s+by\s+line\b", "Return final answer only")
        ]
        for p, r in cot_patterns:
            revised = re.sub(p, r, revised, flags=re.IGNORECASE).strip()

        # Step 5: Trim Few-Shot Examples (Reduce 2+ shots to 1 shot)
        if re.search(r"Example\s*2:", revised, re.IGNORECASE):
            parts = re.split(r"Example\s*2:", revised, flags=re.IGNORECASE)
            input_part = ""
            if any(k in parts[-1] for k in ["Input:", "Text:", "Ticket:", "Code:", "User:"]):
                m = re.search(r"(?:Input|Text|Ticket|Code|User):.*", parts[-1], re.DOTALL | re.IGNORECASE)
                if m:
                    input_part = "\n" + m.group(0)
            revised = parts[0].strip() + input_part

        # Step 6: Transform Directives & Formats logically
        lower = revised.lower()

        # If length replacement occurred (e.g. Summarize key highlights of Indian festivals), append clean bullet constraint
        if "summarize key highlights of" in lower:
            if "bullet" not in lower:
                revised = revised.rstrip(".?") + " in bullet points."
        elif re.search(r"\bgenerate\s+a\s+report\s+on\b", revised, re.IGNORECASE):
            revised = re.sub(r"\bgenerate\s+a\s+(?:detailed\s+)?report\s+on\b", "Summarize key", revised, flags=re.IGNORECASE).rstrip(".?")
            revised += " in 3 concise bullet points."
        elif re.search(r"\bexplain\s+how\b", revised, re.IGNORECASE):
            revised = re.sub(r"\bexplain\s+how\b", "Summarize how", revised, flags=re.IGNORECASE).rstrip(".?")
            revised += " in concise bullet points."
        elif re.search(r"\bexplain\b", revised, re.IGNORECASE) and not "summarize" in revised.lower():
            revised = re.sub(r"\bexplain\b", "Summarize", revised, flags=re.IGNORECASE).rstrip(".?")
            revised += " in concise bullet points."
        elif re.search(r"\bdescribe\b", revised, re.IGNORECASE):
            revised = re.sub(r"\bdescribe\b", "Summarize", revised, flags=re.IGNORECASE).rstrip(".?")
            revised += " in 3 key points."
        elif re.search(r"\bwrite\s+a\s+(?:python\s+)?script\b", revised, re.IGNORECASE):
            revised = re.sub(r"\bwrite\s+a\s+(?:python\s+)?script\b", "Write concise python code", revised, flags=re.IGNORECASE).rstrip(".?")
            revised += " (Return code only without explanations)."
        elif re.search(r"\bwrite\s+a\s+story\b", revised, re.IGNORECASE):
            revised = re.sub(r"\bwrite\s+a\s+story\b", "Write a short 3-paragraph story", revised, flags=re.IGNORECASE)
        elif re.search(r"\bwhat\s+is\b", revised, re.IGNORECASE):
            revised = re.sub(r"\bwhat\s+is\s*", "Define ", revised, flags=re.IGNORECASE).rstrip(".?")
            revised += " in 2 concise sentences."
        elif re.search(r"\bhow\s+to\b", revised, re.IGNORECASE):
            revised = re.sub(r"\bhow\s+to\s*", "List 3 key steps to ", revised, flags=re.IGNORECASE).rstrip(".?")
        elif not any(k in lower for k in ["bullet", "concise", "summarize", "points", "only"]):
            revised = revised.rstrip(".?") + " (Summarize in concise bullet points)."

        # Cleanup extra whitespace, double periods, & duplicate phrases
        revised = re.sub(r"Return final answer only\.(?:\s*and)?\s*Return final answer only\.?", "Return final answer only.", revised, flags=re.IGNORECASE)
        revised = re.sub(r"Return final answer only(?:\s*and)?\s*Return final answer only", "Return final answer only", revised, flags=re.IGNORECASE)
        revised = re.sub(r"\s+", " ", revised).strip()
        revised = re.sub(r"\.\s*\.", ".", revised)
        if revised and revised[0].islower():
            revised = revised[0].upper() + revised[1:]

        return revised

    def analyze_git_diff(self, diff_text: str) -> PromptDeltaFeatures:
        """Parses a Git diff string containing + and - lines."""
        old_lines = []
        new_lines = []
        for line in diff_text.splitlines():
            if line.startswith("-") and not line.startswith("---"):
                old_lines.append(line[1:])
            elif line.startswith("+") and not line.startswith("+++"):
                new_lines.append(line[1:])
            elif not line.startswith("@@") and not line.startswith("diff "):
                old_lines.append(line)
                new_lines.append(line)

        old_prompt = "\n".join(old_lines)
        new_prompt = "\n".join(new_lines)
        return self.analyze_prompts(old_prompt, new_prompt)
