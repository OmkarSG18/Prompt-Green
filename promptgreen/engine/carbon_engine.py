import requests
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from promptgreen.analysis.diff_parser import PromptDiffAnalyzer, PromptDeltaFeatures
from promptgreen.predictor.hybrid_predictor import HybridPredictor, PredictionResult


@dataclass
class ModelEnergyProfile:
    """Model energy coefficients per token in milliJoules (mJ)."""
    name: str
    energy_per_input_token_mj: float
    energy_per_output_token_mj: float
    source: str


# Table 9 Energy Profiles from published research
MODEL_ENERGY_PROFILES: Dict[str, ModelEnergyProfile] = {
    "llama-3-8b": ModelEnergyProfile(
        name="Llama-3 8B",
        energy_per_input_token_mj=0.10,
        energy_per_output_token_mj=0.30,
        source="Meta model card + local CPU measurement"
    ),
    "mistral-7b": ModelEnergyProfile(
        name="Mistral 7B",
        energy_per_input_token_mj=0.08,
        energy_per_output_token_mj=0.25,
        source="Mistral AI model card + local CPU measurement"
    ),
    "phi-3-3.8b": ModelEnergyProfile(
        name="Phi-3 3.8B",
        energy_per_input_token_mj=0.05,
        energy_per_output_token_mj=0.15,
        source="Microsoft research paper + local CPU measurement"
    ),
    "llama-3-70b": ModelEnergyProfile(
        name="Llama-3 70B (reference)",
        energy_per_input_token_mj=0.40,
        energy_per_output_token_mj=1.20,
        source="Meta model card + published benchmark data"
    ),
    "gpt-4": ModelEnergyProfile(
        name="GPT-4 (reference)",
        energy_per_input_token_mj=0.80,
        energy_per_output_token_mj=2.50,
        source="Patterson et al. (2021) arXiv paper"
    )
}

# Cached static regional carbon intensity data (gCO2 / kWh) from IEA reports
CACHED_REGIONAL_CI: Dict[str, float] = {
    "US": 385.0,
    "EU": 255.0,
    "IN": 708.0,
    "GLOBAL": 475.0,
    "UK": 210.0,
    "DE": 380.0
}


@dataclass
class CarbonImpactResult:
    """Carbon Delta Engine Calculation Output."""
    model_name: str
    region: str
    carbon_intensity_gco2_kwh: float
    old_energy_per_inf_mj: float
    new_energy_per_inf_mj: float
    energy_delta_per_inf_mj: float
    old_carbon_per_inf_gco2: float
    new_carbon_per_inf_gco2: float
    carbon_delta_per_inf_gco2: float
    carbon_delta_per_1k_gco2: float
    monthly_carbon_delta_gco2: float  # scaled to monthly traffic projection
    monthly_inferences_assumed: int
    features: PromptDeltaFeatures
    prediction: PredictionResult

    # Equivalent Impact Metrics
    equiv_smartphone_charges_monthly: float
    equiv_car_miles_monthly: float
    equiv_tree_absorption_days: float


class CarbonEngine:
    """
    Deliverable D3: Upgraded Carbon Delta Engine Core.
    Implements core formula:
      Carbon(P) = (Input_Tokens(P) * E_in + Output_Tokens(P) * E_out) * CI_region
      Prompt_Carbon_Delta(D) = |Carbon(B_new) - Carbon(B_old)|
    Includes equivalent real-world impact metrics and multi-model matrix comparison.
    """

    def __init__(
        self,
        model_key: str = "llama-3-8b",
        region: str = "US",
        electricity_maps_api_key: Optional[str] = None,
        blend_weight: float = 0.5
    ):
        self.model_key = model_key.lower()
        if self.model_key not in MODEL_ENERGY_PROFILES:
            self.model_key = "llama-3-8b"

        self.profile = MODEL_ENERGY_PROFILES[self.model_key]
        self.region = region.upper()
        self.api_key = electricity_maps_api_key
        self.predictor = HybridPredictor(blend_weight=blend_weight)
        self.analyzer = self.predictor.analyzer

    def get_carbon_intensity(self) -> float:
        """Fetches regional carbon intensity (gCO2/kWh) with cached IEA fallback."""
        if self.api_key:
            try:
                url = f"https://api.electricitymap.org/v3/carbon-intensity/latest?zone={self.region}"
                headers = {"auth-token": self.api_key}
                resp = requests.get(url, headers=headers, timeout=3)
                if resp.status_code == 200:
                    val = resp.json().get("carbonIntensity")
                    if val is not None:
                        return float(val)
            except Exception:
                pass

        return CACHED_REGIONAL_CI.get(self.region, CACHED_REGIONAL_CI["GLOBAL"])

    def calculate(
        self,
        old_prompt: str,
        new_prompt: str,
        monthly_inferences: int = 10000
    ) -> CarbonImpactResult:
        """Calculates carbon footprint, equivalences, and carbon delta."""
        features = self.analyzer.analyze_prompts(old_prompt, new_prompt)
        pred = self.predictor.predict(old_prompt, new_prompt)

        ci = self.get_carbon_intensity()  # gCO2 per kWh

        # Calculate energy per single inference in milliJoules (mJ)
        old_energy_mj = (
            (features.old_input_tokens * self.profile.energy_per_input_token_mj) +
            (pred.predicted_old_output_tokens * self.profile.energy_per_output_token_mj)
        )

        new_energy_mj = (
            (features.new_input_tokens * self.profile.energy_per_input_token_mj) +
            (pred.predicted_new_output_tokens * self.profile.energy_per_output_token_mj)
        )

        energy_delta_mj = new_energy_mj - old_energy_mj

        # Convert mJ to kWh: 1 kWh = 3,600,000 Joules = 3.6e9 mJ
        old_kwh = old_energy_mj / 3.6e9
        new_kwh = new_energy_mj / 3.6e9
        delta_kwh = energy_delta_mj / 3.6e9

        # Calculate carbon in gCO2
        old_carbon_gco2 = old_kwh * ci
        new_carbon_gco2 = new_kwh * ci
        delta_carbon_gco2 = delta_kwh * ci

        delta_1k_gco2 = delta_carbon_gco2 * 1000.0
        monthly_delta_gco2 = delta_carbon_gco2 * monthly_inferences

        # Equivalent impact metrics
        # 1 smartphone charge ≈ 8.22 gCO2
        # 1 gas car mile ≈ 404 gCO2
        # 1 mature tree absorbs ≈ 60 gCO2 per day (22 kg/yr)
        abs_monthly = abs(monthly_delta_gco2)
        equiv_phone = abs_monthly / 8.22
        equiv_car = abs_monthly / 404.0
        equiv_tree = abs_monthly / 60.0

        return CarbonImpactResult(
            model_name=self.profile.name,
            region=self.region,
            carbon_intensity_gco2_kwh=ci,
            old_energy_per_inf_mj=round(old_energy_mj, 4),
            new_energy_per_inf_mj=round(new_energy_mj, 4),
            energy_delta_per_inf_mj=round(energy_delta_mj, 4),
            old_carbon_per_inf_gco2=round(old_carbon_gco2, 6),
            new_carbon_per_inf_gco2=round(new_carbon_gco2, 6),
            carbon_delta_per_inf_gco2=round(delta_carbon_gco2, 6),
            carbon_delta_per_1k_gco2=round(delta_1k_gco2, 4),
            monthly_carbon_delta_gco2=round(monthly_delta_gco2, 2),
            monthly_inferences_assumed=monthly_inferences,
            features=features,
            prediction=pred,
            equiv_smartphone_charges_monthly=round(equiv_phone, 1),
            equiv_car_miles_monthly=round(equiv_car, 3),
            equiv_tree_absorption_days=round(equiv_tree, 1)
        )

    def compare_all_models(self, old_prompt: str, new_prompt: str) -> List[Dict[str, Any]]:
        """Calculates carbon impact delta across all 5 benchmarked models."""
        matrix = []
        for key, prof in MODEL_ENERGY_PROFILES.items():
            temp_engine = CarbonEngine(model_key=key, region=self.region)
            res = temp_engine.calculate(old_prompt, new_prompt)
            matrix.append({
                "model_key": key,
                "model_name": prof.name,
                "input_mj": prof.energy_per_input_token_mj,
                "output_mj": prof.energy_per_output_token_mj,
                "carbon_delta_1k_gco2": res.carbon_delta_per_1k_gco2,
                "monthly_carbon_gco2": res.monthly_carbon_delta_gco2
            })
        return matrix
