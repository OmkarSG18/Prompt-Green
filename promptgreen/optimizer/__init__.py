"""
PromptGreen v2.0 - Active Prompt Optimization Engine
Package initialization for multi-stage prompt compression, structural pruning,
and semantic fidelity enforcement.
"""

from promptgreen.optimizer.rule_pruner import (
    RuleBasedPruner,
    PruningResult,
    ProtectedRegion
)
from promptgreen.optimizer.compressor import (
    LLMLinguaCompressor,
    PromptCompressor,
    CompressorConfig,
    CompressionResult
)
from promptgreen.optimizer.output_shaper import (
    OutputDirectiveShaper,
    ShaperConfig,
    ShapingResult
)
from promptgreen.optimizer.semantic_guard import (
    SemanticFidelityGuard,
    GuardrailConfig,
    GuardrailResult,
    GuardrailMode,
    LocalMiniLMEmbedder,
    compute_cosine_similarity
)
from promptgreen.optimizer.pipeline import (
    PromptGreenPipeline,
    PromptGreenOptimizer,
    PipelineConfig,
    PipelineResult,
    OptimizationResult,
    StageExecution,
    optimize_prompt,
)

__all__ = [
    "RuleBasedPruner",
    "PruningResult",
    "ProtectedRegion",
    "LLMLinguaCompressor",
    "PromptCompressor",
    "CompressorConfig",
    "CompressionResult",
    "OutputDirectiveShaper",
    "ShaperConfig",
    "ShapingResult",
    "SemanticFidelityGuard",
    "GuardrailConfig",
    "GuardrailResult",
    "GuardrailMode",
    "LocalMiniLMEmbedder",
    "compute_cosine_similarity",
    "PromptGreenPipeline",
    "PromptGreenOptimizer",
    "PipelineConfig",
    "PipelineResult",
    "OptimizationResult",
    "StageExecution",
    "optimize_prompt",
]
