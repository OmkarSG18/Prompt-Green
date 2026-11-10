import json
from promptgreen.analysis.diff_parser import PromptDiffAnalyzer
from promptgreen.engine.carbon_engine import CarbonEngine
from promptgreen.gate.prompt_gate import PromptGate

def test_verification():
    analyzer = PromptDiffAnalyzer()
    engine = CarbonEngine(model_key="llama-3-8b", region="US")

    test_prompts = [
        "Generate a detailed report on climate change impacts.",
        "Explain in detail with extensive examples how quantum computing works.",
        "Write a python script in detail with extensive comments to sort a dictionary.",
        "Solve this math problem: 2x + 5 = 15. Think step-by-step and explain every calculation line by line.",
        "Classify sentiment with detailed justifications: Example 1: 'Good' -> Positive, Example 2: 'Bad' -> Negative. Input: 'Decent product.'",
        "Could you please tell me the capital of France?",
        "What is artificial intelligence?",
        "How to boil an egg perfectly?",
        "Write an expansive fantasy world backstory with detailed legends and magic systems.",
        "Explain how photosynthesis works in full detail."
    ]

    print("================================================================================")
    print("PROMPTGREEN CORE ENGINE VERIFICATION SUITE")
    print("================================================================================\n")

    passed_count = 0

    for idx, orig in enumerate(test_prompts, 1):
        green = analyzer.generate_green_alternative(orig)
        res = engine.calculate(orig, green)

        orig_tokens = res.features.old_input_tokens
        green_tokens = res.features.new_input_tokens
        orig_out_pred = res.prediction.predicted_old_output_tokens
        green_out_pred = res.prediction.predicted_new_output_tokens

        orig_carbon = res.old_carbon_per_inf_gco2 * 1000.0  # gCO2 per 1k
        green_carbon = res.new_carbon_per_inf_gco2 * 1000.0
        delta_carbon = res.carbon_delta_per_1k_gco2
        pct_saved = ((orig_carbon - green_carbon) / max(0.00001, orig_carbon)) * 100.0

        is_better = (green != orig) and (green_out_pred <= orig_out_pred) and (delta_carbon < 0 or orig_tokens >= green_tokens)

        if is_better:
            passed_count += 1

        print(f"[{idx}] TEST PROMPT:")
        print(f"  ORIGINAL : '{orig}'")
        print(f"  REVISED  : '{green}'")
        print(f"  INPUT TOKENS : {orig_tokens} -> {green_tokens} ({green_tokens - orig_tokens:+d})")
        print(f"  PRED OUTPUT  : {orig_out_pred:.1f} -> {green_out_pred:.1f} ({green_out_pred - orig_out_pred:+.1f} tok)")
        print(f"  CARBON / 1K  : {orig_carbon:.4f}g -> {green_carbon:.4f}g (Delta: {delta_carbon:+.4f}g | {pct_saved:.1f}% Saved)")
        print(f"  VERDICT      : {'SUCCESS (Better Green Prompt)' if is_better else 'FAIL'}")
        print("--------------------------------------------------------------------------------")

    print(f"\nFINAL VERIFICATION SUMMARY: {passed_count} / {len(test_prompts)} Prompts Verified Successful ({passed_count/len(test_prompts)*100:.1f}%)")

if __name__ == "__main__":
    test_verification()
