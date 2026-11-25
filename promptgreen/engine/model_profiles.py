"""
Model profiles, hardware configurations, and regional grid intensity scenarios
for PromptGreen V2 thermodynamic energy and carbon modeling.
"""

import math
from dataclasses import dataclass
from typing import Dict, Optional, List


THESIS_PROVENANCE_WARNING = (
    "Thesis-provided representative coefficients; external provenance and independent calibration not yet verified."
)

GRID_PROVENANCE_ILLUSTRATIVE_385 = (
    "385 gCO2e/kWh, illustrative scenario, source and reference year unverified."
)

GRID_PROVENANCE_THESIS_367 = (
    "367 gCO2e/kWh, thesis-provided scenario, not independently calibrated and not a verified global average."
)

# Aliases for backward compatibility during transition
GRID_PROVENANCE_US_ILLUSTRATIVE = GRID_PROVENANCE_ILLUSTRATIVE_385
GRID_PROVENANCE_THESIS_GLOBAL = GRID_PROVENANCE_THESIS_367

WATER_COEFFICIENT_WARNING = (
    "Illustrative assumed water-use coefficient (1.8 mL/Wh = 1.8 L/kWh); not universally applicable."
)

CPU_POWER_ESTIMATE_WARNING = (
    "Configurable unmeasured engineering estimate (default: 35.0W active CPU load)."
)


@dataclass(frozen=True)
class HardwareProfile:
    """
    Descriptive hardware chip specification for datacenter LLM serving.

    IMPORTANT METHODOLOGICAL NOTE:
      The TDP (Thermal Design Power) and typical operating power values defined
      here represent manufacturer electrical envelope specifications and heuristic
      datacenter engineering estimates, NOT measured inference energy per token.

      Actual per-token inference energy depends dynamically on batch size, context
      length, memory bandwidth, quantization, and software runtime optimizations.
      Hardware profiles are decoupled from the core thermodynamic calculation engine
      (which uses ModelTierProfile mWh/token coefficients directly) and serve as
      informational metadata and architecture targets for future hardware-aware routing.
    """
    hardware_id: str
    name: str
    tdp_watts: float
    typical_operating_watts: float
    memory_gb: float
    cooling_type: str = "air/liquid"
    notes: str = ""

    def __post_init__(self):
        if not isinstance(self.hardware_id, str) or not self.hardware_id.strip():
            raise ValueError("hardware_id must be a non-empty string")
        if isinstance(self.tdp_watts, bool) or not isinstance(self.tdp_watts, (int, float)) or not math.isfinite(self.tdp_watts) or self.tdp_watts <= 0:
            raise ValueError(f"tdp_watts must be a finite positive number, got {self.tdp_watts}")
        if isinstance(self.typical_operating_watts, bool) or not isinstance(self.typical_operating_watts, (int, float)) or not math.isfinite(self.typical_operating_watts) or self.typical_operating_watts <= 0:
            raise ValueError(f"typical_operating_watts must be a finite positive number, got {self.typical_operating_watts}")
        if isinstance(self.memory_gb, bool) or not isinstance(self.memory_gb, (int, float)) or not math.isfinite(self.memory_gb) or self.memory_gb <= 0:
            raise ValueError(f"memory_gb must be a finite positive number, got {self.memory_gb}")


@dataclass(frozen=True)
class ModelTierProfile:
    """
    Model tier configuration defining prefill and decode energy coefficients.
    Coefficients are stored strictly in milliWatt-hours per token (mWh/token).
    """
    tier_id: str
    display_name: str
    alpha_prefill_mwh: float
    alpha_decode_mwh: float
    hardware_id: str
    provenance: str = THESIS_PROVENANCE_WARNING
    description: str = ""
    is_ratio_unusual: bool = False
    ratio_note: str = ""

    def __post_init__(self):
        if not isinstance(self.tier_id, str) or not self.tier_id.strip():
            raise ValueError("tier_id must be a non-empty string")
        if not isinstance(self.hardware_id, str) or not self.hardware_id.strip():
            raise ValueError("hardware_id must be a non-empty string")

        # Validate alpha_prefill_mwh
        if isinstance(self.alpha_prefill_mwh, bool) or not isinstance(self.alpha_prefill_mwh, (int, float)):
            raise TypeError(
                f"alpha_prefill_mwh must be a float or int, got {type(self.alpha_prefill_mwh).__name__}"
            )
        if not math.isfinite(self.alpha_prefill_mwh) or self.alpha_prefill_mwh <= 0:
            raise ValueError(
                f"alpha_prefill_mwh must be a finite positive number, got {self.alpha_prefill_mwh}"
            )

        # Validate alpha_decode_mwh
        if isinstance(self.alpha_decode_mwh, bool) or not isinstance(self.alpha_decode_mwh, (int, float)):
            raise TypeError(
                f"alpha_decode_mwh must be a float or int, got {type(self.alpha_decode_mwh).__name__}"
            )
        if not math.isfinite(self.alpha_decode_mwh) or self.alpha_decode_mwh <= 0:
            raise ValueError(
                f"alpha_decode_mwh must be a finite positive number, got {self.alpha_decode_mwh}"
            )

        # Non-rejecting check for unusual decode-to-prefill ratio
        # In standard autoregressive transformers, decode energy is typically 3x-4x prefill.
        # However, specialized architectures (e.g. non-autoregressive, parallel decoding, speculative drafting)
        # may legitimately exhibit decode lower than prefill. This is recorded as metadata without rejection.
        if self.alpha_decode_mwh < self.alpha_prefill_mwh:
            object.__setattr__(self, "is_ratio_unusual", True)
            if not self.ratio_note:
                object.__setattr__(
                    self,
                    "ratio_note",
                    f"Unusual coefficient ratio: alpha_decode_mwh ({self.alpha_decode_mwh}) is lower than "
                    f"alpha_prefill_mwh ({self.alpha_prefill_mwh}). Valid for specialized or non-autoregressive architectures."
                )

    @property
    def decode_to_prefill_ratio(self) -> float:
        """Ratio of decode energy to prefill energy."""
        return self.alpha_decode_mwh / self.alpha_prefill_mwh


@dataclass(frozen=True)
class GridIntensityScenario:
    """Regional grid carbon intensity configuration."""
    region_code: str
    carbon_intensity_gco2_kwh: float
    provenance: str
    is_illustrative: bool = True

    def __post_init__(self):
        if not isinstance(self.region_code, str) or not self.region_code.strip():
            raise ValueError("region_code must be a non-empty string")
        if isinstance(self.carbon_intensity_gco2_kwh, bool) or not isinstance(self.carbon_intensity_gco2_kwh, (int, float)) or not math.isfinite(self.carbon_intensity_gco2_kwh) or self.carbon_intensity_gco2_kwh <= 0:
            raise ValueError(
                f"carbon_intensity_gco2_kwh must be a finite positive number, got {self.carbon_intensity_gco2_kwh}"
            )


# Standard reference hardware profiles
# NOTE: Hardware profiles provide descriptive datacenter hardware specifications.
# They are decoupled from the core thermodynamic calculation engine and serve as
# informational architecture targets. They do NOT represent measured per-token energy.
STANDARD_HARDWARE_PROFILES: Dict[str, HardwareProfile] = {
    "h100_pcie": HardwareProfile(
        hardware_id="h100_pcie",
        name="NVIDIA H100 PCIe (80GB)",
        tdp_watts=700.0,
        typical_operating_watts=480.0,
        memory_gb=80.0,
        cooling_type="air/liquid",
        notes="700W represents SXM5 host board envelope; PCIe card spec is 350W TDP. Unmeasured manufacturer specification."
    ),
    "a100_sxm4": HardwareProfile(
        hardware_id="a100_sxm4",
        name="NVIDIA A100 SXM4 (80GB)",
        tdp_watts=400.0,
        typical_operating_watts=280.0,
        memory_gb=80.0,
        cooling_type="liquid",
        notes="NVIDIA A100 SXM4 manufacturer 400W TDP limit; operating power is an unmeasured estimate."
    ),
    "l4_pcie": HardwareProfile(
        hardware_id="l4_pcie",
        name="NVIDIA L4 PCIe (24GB)",
        tdp_watts=72.0,
        typical_operating_watts=60.0,
        memory_gb=24.0,
        cooling_type="air",
        notes="NVIDIA L4 PCIe manufacturer 72W TDP limit; operating power is an unmeasured estimate."
    ),
}


# Four Thesis-Provided Representative Model Tiers
# Stored strictly in mWh/token
STANDARD_MODEL_TIERS: Dict[str, ModelTierProfile] = {
    "frontier_dense": ModelTierProfile(
        tier_id="frontier_dense",
        display_name="Frontier Dense (GPT-4o / Claude 3.5 Sonnet Class)",
        alpha_prefill_mwh=0.42,
        alpha_decode_mwh=1.60,
        hardware_id="h100_pcie",
        provenance=THESIS_PROVENANCE_WARNING,
        description="High-capacity frontier multi-head attention models requiring dense matrix execution."
    ),
    "large_reasoning": ModelTierProfile(
        tier_id="large_reasoning",
        display_name="Large Reasoning (Llama-3 70B / Qwen-2.5 72B Class)",
        alpha_prefill_mwh=0.35,
        alpha_decode_mwh=1.35,
        hardware_id="a100_sxm4",
        provenance=THESIS_PROVENANCE_WARNING,
        description="70B parameter open-weights reasoning class on multi-GPU A100 clusters."
    ),
    "mid_tier": ModelTierProfile(
        tier_id="mid_tier",
        display_name="Mid-Tier MoE/Dense (Mixtral 8x7B / Command-R Class)",
        alpha_prefill_mwh=0.24,
        alpha_decode_mwh=0.92,
        hardware_id="a100_sxm4",
        provenance=THESIS_PROVENANCE_WARNING,
        description="Mixture-of-Experts or mid-size dense models with selective parameter activation."
    ),
    "compact_green": ModelTierProfile(
        tier_id="compact_green",
        display_name="Compact Green (Llama-3.2 3B / Phi-3.5 3.8B Class)",
        alpha_prefill_mwh=0.04,
        alpha_decode_mwh=0.15,
        hardware_id="l4_pcie",
        provenance=THESIS_PROVENANCE_WARNING,
        description="Small parameter efficiency class runnable on single-card accelerators."
    ),
}


# Retained Selectable Grid Intensity Scenarios (strictly limited to approved scope)
# Neither scenario is presented as a regional or universal default.
STANDARD_GRID_SCENARIOS: Dict[str, GridIntensityScenario] = {
    "ILLUSTRATIVE_385": GridIntensityScenario(
        region_code="ILLUSTRATIVE_385",
        carbon_intensity_gco2_kwh=385.0,
        provenance=GRID_PROVENANCE_ILLUSTRATIVE_385,
        is_illustrative=True
    ),
    "THESIS_367": GridIntensityScenario(
        region_code="THESIS_367",
        carbon_intensity_gco2_kwh=367.0,
        provenance=GRID_PROVENANCE_THESIS_367,
        is_illustrative=True
    ),
}


# Explicitly documented unavailable regional placeholders.
# These regions lack independently verified sources and reference years.
# PromptGreen refuses to silently invent numbers or substitute ILLUSTRATIVE_385 or THESIS_367.
UNAVAILABLE_REGIONAL_PLACEHOLDERS: Dict[str, str] = {
    "US": (
        "The 'US' identifier has been renamed to 'ILLUSTRATIVE_385' to avoid presenting an unverified "
        "illustrative figure as an empirical US national grid intensity. Please use 'ILLUSTRATIVE_385' "
        "or provide an explicit user-supplied numeric float."
    ),
    "THESIS_GLOBAL": (
        "The 'THESIS_GLOBAL' identifier has been renamed to 'THESIS_367' to clarify that this is a "
        "thesis-provided scenario and not a verified global average. Please use 'THESIS_367' "
        "or provide an explicit user-supplied numeric float."
    ),
    "IN": (
        "India national grid carbon intensity lacks an independently verified reference year and source "
        "in the thesis. PromptGreen will not silently substitute ILLUSTRATIVE_385 or THESIS_367. "
        "Please provide an explicit user-supplied numeric gCO2e/kWh value and specify its provenance separately."
    ),
    "IN-WE": (
        "India Western regional grid carbon intensity lacks an independently verified reference year. "
        "Please provide an explicit user-supplied numeric value."
    ),
    "IN-SO": (
        "India Southern regional grid carbon intensity lacks an independently verified reference year. "
        "Please provide an explicit user-supplied numeric value."
    ),
    "EU": (
        "European Union average grid carbon intensity lacks an independently verified reference year and boundary. "
        "Please provide an explicit user-supplied numeric value."
    ),
    "UK": (
        "United Kingdom grid carbon intensity lacks an independently verified reference year. "
        "Please provide an explicit user-supplied numeric value."
    ),
    "DE": (
        "Germany grid carbon intensity lacks an independently verified reference year. "
        "Please provide an explicit user-supplied numeric value."
    ),
    "FR": (
        "France grid carbon intensity lacks an independently verified reference year. "
        "Please provide an explicit user-supplied numeric value."
    ),
    "GLOBAL": (
        "Global average grid carbon intensity lacks an independently verified reference year and source dataset. "
        "Please provide an explicit user-supplied numeric value."
    ),
}


class ModelProfileRegistry:
    """
    Registry for model tier profiles, hardware profiles, and grid scenarios.
    Permits configuration and user injection of verified custom profiles.
    """

    def __init__(self):
        self._tiers: Dict[str, ModelTierProfile] = dict(STANDARD_MODEL_TIERS)
        self._hardware: Dict[str, HardwareProfile] = dict(STANDARD_HARDWARE_PROFILES)
        self._grid: Dict[str, GridIntensityScenario] = dict(STANDARD_GRID_SCENARIOS)

    def register_tier(self, tier: ModelTierProfile) -> None:
        """Register or override a model tier profile."""
        if not isinstance(tier, ModelTierProfile):
            raise TypeError(f"Expected ModelTierProfile, got {type(tier).__name__}")
        self._tiers[tier.tier_id.lower()] = tier

    def get_tier(self, tier_id: str) -> ModelTierProfile:
        """Retrieve a model tier profile by ID."""
        key = tier_id.lower().strip()
        if key not in self._tiers:
            available = ", ".join(self._tiers.keys())
            raise KeyError(f"Unknown model tier '{tier_id}'. Available tiers: {available}")
        return self._tiers[key]

    def list_tiers(self) -> List[str]:
        """List all registered model tier IDs."""
        return list(self._tiers.keys())

    def register_hardware(self, hardware: HardwareProfile) -> None:
        """Register or override a hardware profile."""
        if not isinstance(hardware, HardwareProfile):
            raise TypeError(f"Expected HardwareProfile, got {type(hardware).__name__}")
        self._hardware[hardware.hardware_id.lower()] = hardware

    def get_hardware(self, hardware_id: str) -> HardwareProfile:
        """Retrieve a hardware profile by ID."""
        key = hardware_id.lower().strip()
        if key not in self._hardware:
            available = ", ".join(self._hardware.keys())
            raise KeyError(f"Unknown hardware ID '{hardware_id}'. Available profiles: {available}")
        return self._hardware[key]

    def list_hardware(self) -> List[str]:
        """List all registered hardware profile IDs."""
        return list(self._hardware.keys())

    def register_grid_scenario(self, scenario: GridIntensityScenario) -> None:
        """Register or override a grid intensity scenario."""
        if not isinstance(scenario, GridIntensityScenario):
            raise TypeError(f"Expected GridIntensityScenario, got {type(scenario).__name__}")
        self._grid[scenario.region_code.upper()] = scenario

    def list_grid_scenarios(self) -> List[str]:
        """List all selectable registered grid scenario codes."""
        return list(self._grid.keys())

    def get_grid_scenario(self, region_code: str) -> GridIntensityScenario:
        """
        Retrieve a grid intensity scenario by region code.
        Only verified / explicitly retained scenarios ('ILLUSTRATIVE_385', 'THESIS_367') can be retrieved by code.
        Unverified or renamed regional codes raise KeyError explaining that empirical data is not bundled
        and that PromptGreen will not silently substitute ILLUSTRATIVE_385 or THESIS_367.
        """
        key = region_code.upper().strip()
        if key in self._grid:
            return self._grid[key]
        if key in UNAVAILABLE_REGIONAL_PLACEHOLDERS:
            raise KeyError(
                f"Grid intensity for region '{key}' is unavailable without user specification: "
                f"{UNAVAILABLE_REGIONAL_PLACEHOLDERS[key]}"
            )
        available = ", ".join(self._grid.keys())
        raise KeyError(
            f"Unknown grid region '{region_code}'. Selectable verified scenarios: {available}. "
            f"To evaluate a specific regional intensity, provide an explicit user-supplied float."
        )


# Global default registry instance
DEFAULT_PROFILE_REGISTRY = ModelProfileRegistry()

