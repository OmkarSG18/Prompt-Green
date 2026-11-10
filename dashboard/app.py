import sys
import os

# Ensure project root is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from promptgreen.ledger.database import PromptLedger
from promptgreen.engine.carbon_engine import CarbonEngine, MODEL_ENERGY_PROFILES, CACHED_REGIONAL_CI
from promptgreen.analysis.diff_parser import PromptDiffAnalyzer
from promptgreen.predictor.hybrid_predictor import HybridPredictor
from promptgreen.validation.benchmark import BenchmarkSuiteRunner

st.set_page_config(
    page_title="PromptGreen Carbon Review App",
    page_icon="🌱",
    layout="wide"
)

st.title("🌱 PromptGreen — Carbon Emission Estimator & GUI Benchmark Simulator")
st.markdown("*Zero-Budget Carbon-Aware Prompt Review for Sustainable LLM Deployment*")

db = PromptLedger()
db.seed_demo_data_if_empty()
analyzer = PromptDiffAnalyzer()

# Sidebar controls
st.sidebar.header("⚙️ App Configuration")
model_choice = st.sidebar.selectbox("LLM Model Profile", list(MODEL_ENERGY_PROFILES.keys()), index=0)
region_choice = st.sidebar.selectbox("Grid Region", list(CACHED_REGIONAL_CI.keys()), index=0)
monthly_inf_choice = st.sidebar.number_input("Monthly Traffic (Inferences)", min_value=100, max_value=10000000, value=10000, step=1000)

summary = db.get_cumulative_carbon_debt()
records = db.get_recent_records(limit=25)
df_records = pd.DataFrame(records)

# Top Key Performance Indicators (KPIs)
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Prompt Reviews", summary.get("total_reviews", 0))

with col2:
    st.metric("Passed Deployment Gates", summary.get("passed_reviews", 0), delta=f"{summary.get('passed_reviews', 0)} Approved")

with col3:
    net_1k = summary.get("total_carbon_delta_1k", 0.0)
    st.metric("Net Carbon Delta / 1K Inf", f"{net_1k:+.4f} gCO2", delta_color="inverse" if net_1k > 0 else "normal")

with col4:
    net_monthly = summary.get("total_monthly_carbon", 0.0)
    st.metric("Net Monthly Footprint", f"{net_monthly:+.2f} gCO2", delta_color="inverse" if net_monthly > 0 else "normal")

st.divider()

# Interactive Main Tabs
tab_simulator, tab_estimator, tab_trends, tab_leaderboard, tab_models, tab_ledger = st.tabs([
    "🎛️ GUI Benchmark Simulator",
    "🔍 Carbon Estimator & Prompt Comparison",
    "📈 Per-Version Trends",
    "🏆 Team Sustainability Leaderboard",
    "⚡ Model Profiles & Energy Data",
    "📜 Ledger History"
])


# ==============================================================================
# TAB 1: GUI Benchmark Simulator & Parameter Tuner
# ==============================================================================
with tab_simulator:
    st.header("🎛️ Interactive GUI Benchmark Simulator & Parameter Tuner")
    st.markdown(
        "Tune predictor weights, energy profiles, carbon intensity, and budget thresholds in real time to simulate system performance "
        "across the 50-pair benchmark suite."
    )

    sim_col1, sim_col2 = st.columns(2)

    with sim_col1:
        sim_blend = st.slider(
            "Predictor Blend Weight (Rule vs ML Layer)",
            min_value=0.0,
            max_value=1.0,
            value=0.5,
            step=0.05,
            help="1.0 = Pure Rule-Based; 0.0 = Pure ML Regressor; 0.5 = Blended Ensemble."
        )
        sim_model = st.selectbox("Simulation Target Model", list(MODEL_ENERGY_PROFILES.keys()), index=0)

    with sim_col2:
        sim_region = st.selectbox("Simulation Region Grid Factor", list(CACHED_REGIONAL_CI.keys()), index=0)
        sim_budget = st.slider(
            "Gate Budget Threshold (gCO2 / 1K Inferences)",
            min_value=0.01,
            max_value=2.0,
            value=0.5,
            step=0.05,
            help="Carbon threshold above which deployments trigger warnings/blocks."
        )

    if st.button("▶ Run Live Benchmark Simulation", type="primary"):
        runner = BenchmarkSuiteRunner()
        sim_res = runner.run_evaluation(
            blend_weight=sim_blend,
            model_key=sim_model,
            region=sim_region,
            budget_threshold=sim_budget
        )

        st.markdown("### 📊 Simulation Metric Results")

        sc1, sc2, sc3, sc4 = st.columns(4)
        with sc1:
            st.metric(
                "Directional Accuracy",
                f"{sim_res['directional_accuracy_pct']:.1f}%",
                delta="Target > 85%",
                delta_color="normal" if sim_res['directional_accuracy_pct'] >= 85.0 else "inverse"
            )
        with sc2:
            st.metric(
                "Mean Absolute Pct Error (MAPE)",
                f"{sim_res['mape_pct']:.1f}%",
                delta="Target < 20%",
                delta_color="normal" if sim_res['mape_pct'] <= 20.0 else "inverse"
            )
        with sc3:
            st.metric(
                "R² Regression Score",
                f"{sim_res['r2_score']:.4f}",
                delta="Target > 0.80",
                delta_color="normal" if sim_res['r2_score'] >= 0.80 else "inverse"
            )
        with sc4:
            st.metric(
                "Gate Pass Rate",
                f"{sim_res['gate_pass_rate_pct']:.1f}%",
                help="Percentage of benchmark prompt diffs passing gate budget."
            )

        st.divider()

        # Visual Breakdown Charts
        cat_data = []
        for cat, info in sim_res["category_summary"].items():
            cat_data.append({
                "Category": cat,
                "Directional Accuracy (%)": info["directional_accuracy_pct"],
                "MAPE (%)": info["mean_ape_pct"],
                "Avg Carbon Delta (gCO2 / 1K)": info["avg_carbon_delta_1k"]
            })
        df_cat = pd.DataFrame(cat_data)

        fig_acc = px.bar(
            df_cat,
            x="Category",
            y="Directional Accuracy (%)",
            color="Category",
            title="Directional Accuracy by Benchmark Category",
            text="Directional Accuracy (%)"
        )
        fig_acc.add_hline(y=85.0, line_dash="dash", line_color="red", annotation_text="85% Target")
        st.plotly_chart(fig_acc, use_container_width=True)

        st.markdown("### 📋 Category Performance Summary Table")
        st.dataframe(df_cat, use_container_width=True)


# ==============================================================================
# TAB 2: Carbon Emission Estimation & Prompt Comparison Feature
# ==============================================================================
with tab_estimator:
    st.header("🌱 Prompt Carbon Emission Estimator & Optimizer")
    st.markdown(
        "Enter any prompt below to calculate its **estimated carbon emissions**, generate a **greener alternative prompt**, "
        "and view a **side-by-side prompt comparison** with highlighted semantic differences."
    )

    col_inp1, col_inp2 = st.columns(2)

    with col_inp1:
        orig_prompt_input = st.text_area(
            "Original Prompt Text:",
            value="Generate a detailed report on climate change impacts.",
            height=130,
            help="Enter the original prompt to estimate carbon footprint."
        )

    # Generate auto-suggested green prompt
    suggested_green_prompt = analyzer.generate_green_alternative(orig_prompt_input)

    with col_inp2:
        use_custom = st.checkbox("Custom Revised Prompt (User or Website Provided)", value=False)
        if use_custom:
            rev_prompt_input = st.text_area(
                "Revised Prompt Text:",
                value=suggested_green_prompt,
                height=100,
                help="Enter custom revised prompt text."
            )
        else:
            st.text_area(
                "Suggested Greener Alternative Prompt (App Auto-Generated):",
                value=suggested_green_prompt,
                height=100,
                disabled=True
            )
            rev_prompt_input = suggested_green_prompt

    if st.button("🚀 Calculate Emissions & Compare Prompts", type="primary"):
        if not orig_prompt_input.strip():
            st.warning("Please enter an original prompt text.")
        else:
            engine = CarbonEngine(model_key=model_choice, region=region_choice)
            res = engine.calculate(orig_prompt_input, rev_prompt_input, monthly_inferences=monthly_inf_choice)

            # Convert gCO2 to kg CO2e for display compatibility
            orig_kg_1k = (res.old_carbon_per_inf_gco2 * 1000.0) / 1000.0
            rev_kg_1k = (res.new_carbon_per_inf_gco2 * 1000.0) / 1000.0
            saved_kg_1k = orig_kg_1k - rev_kg_1k
            pct_savings = ((orig_kg_1k - rev_kg_1k) / max(0.00001, orig_kg_1k)) * 100.0

            st.markdown("### 📊 Estimated Carbon Emissions Output")

            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            with m_col1:
                st.metric(
                    "Original Prompt Emissions",
                    f"{res.old_carbon_per_inf_gco2:.6f} g CO2e",
                    help="Carbon footprint per single inference."
                )
                st.caption(f"Per 1K Inf: **{orig_kg_1k:.4f} kg CO2e**")

            with m_col2:
                st.metric(
                    "Revised Prompt Emissions",
                    f"{res.new_carbon_per_inf_gco2:.6f} g CO2e",
                    help="Carbon footprint of greener prompt per inference."
                )
                st.caption(f"Per 1K Inf: **{rev_kg_1k:.4f} kg CO2e**")

            with m_col3:
                st.metric(
                    "Emissions Savings",
                    f"{res.carbon_delta_per_1k_gco2:+.4f} g CO2e / 1K",
                    delta=f"{pct_savings:.1f}% Reduction",
                    delta_color="normal" if pct_savings > 0 else "inverse"
                )

            with m_col4:
                st.metric(
                    "Output Token Inflation",
                    f"{res.prediction.predicted_output_token_delta:+.1f} Tokens",
                    delta=f"{res.prediction.inflation_percentage:+.1f}% Tokens"
                )

            st.divider()

            st.markdown("### 🔄 Side-by-Side Prompt Comparison")

            # Determine difference summary description
            diff_descriptions = []
            feats = res.features
            if feats.input_token_delta < 0:
                diff_descriptions.append("Input prompt length reduced")
            elif feats.input_token_delta > 0:
                diff_descriptions.append("Input prompt length increased")

            if feats.verb_complexity_delta < 0:
                diff_descriptions.append("Verb complexity reduced to concise directive")

            if "in bullet points" in rev_prompt_input.lower() or "bullet" in rev_prompt_input.lower():
                diff_descriptions.append("Format changed to concise bullet points")

            if feats.few_shot_delta < 0:
                diff_descriptions.append(f"Few-shot examples trimmed ({feats.few_shot_count_old} -> {feats.few_shot_count_new})")

            if feats.cot_triggered_old and not feats.cot_triggered_new:
                diff_descriptions.append("Chain-of-thought requirement removed")

            if not diff_descriptions:
                diff_descriptions.append("Minor textual refinements")

            diff_summary_str = "; ".join(diff_descriptions) + "."

            # Construct Side-by-Side Comparison Table matching specification example
            comp_df = pd.DataFrame([
                {
                    "Original Prompt": orig_prompt_input,
                    "Revised Prompt": rev_prompt_input,
                    "Differences": diff_summary_str
                }
            ])

            st.table(comp_df)

            # Detailed Token & Energy Comparison Breakdown
            with st.expander("🔍 Detailed Token & Energy Breakdown"):
                t_df = pd.DataFrame([
                    {
                        "Prompt Version": "Original Prompt",
                        "Input Tokens": res.features.old_input_tokens,
                        "Predicted Output Tokens": res.prediction.predicted_old_output_tokens,
                        "Energy per Inf (mJ)": res.old_energy_per_inf_mj,
                        "Carbon per Inf (g CO2e)": res.old_carbon_per_inf_gco2,
                        "Carbon per 1K Inf (g CO2e)": res.old_carbon_per_inf_gco2 * 1000.0
                    },
                    {
                        "Prompt Version": "Revised (Greener) Prompt",
                        "Input Tokens": res.features.new_input_tokens,
                        "Predicted Output Tokens": res.prediction.predicted_new_output_tokens,
                        "Energy per Inf (mJ)": res.new_energy_per_inf_mj,
                        "Carbon per Inf (g CO2e)": res.new_carbon_per_inf_gco2,
                        "Carbon per 1K Inf (g CO2e)": res.new_carbon_per_inf_gco2 * 1000.0
                    }
                ])
                st.dataframe(t_df, use_container_width=True)

            # Record review into SQLite database ledger
            db.record_prompt_review(
                commit_hash="app-ui",
                author="interactive-user",
                team="Product App",
                model_name=res.model_name,
                region=res.region,
                old_prompt=orig_prompt_input[:100],
                new_prompt=rev_prompt_input[:100],
                input_token_delta=res.features.input_token_delta,
                predicted_output_token_delta=res.prediction.predicted_output_token_delta,
                carbon_delta_gco2_1k=res.carbon_delta_per_1k_gco2,
                monthly_carbon_delta_gco2=res.monthly_carbon_delta_gco2,
                status="PASS" if res.carbon_delta_per_1k_gco2 <= 0.5 else "WARN"
            )
            st.success("✔ Prompt review and emission estimates logged into local Prompt Carbon Ledger.")

    st.divider()

    # Expandable Documented Methodology Section
    with st.expander("📖 Transparent Methodology & Emission Estimation Formula Documentation"):
        st.markdown(
            """
            ### Carbon Emission Estimation Methodology
            PromptGreen calculates the estimated carbon footprint of a prompt using a transparent, published hardware-free formula:

            $$\\text{Carbon}(P) = \\left(\\text{Input\\_Tokens}(P) \\times E_{\\text{in}} + \\text{Predicted\\_Output\\_Tokens}(P) \\times E_{\\text{out}}\\right) \\times \\text{CI}_{\\text{region}}$$

            - **Input & Output Tokens:** Input tokens are counted using HuggingFace / TikToken tokenizers. Output tokens are predicted using the **Hybrid Token Inflation Predictor** (Layer 1 NLP rule scoring + Layer 2 Scikit-Learn regression trained on Ollama benchmark data).
            - **Model Energy Profiles ($E_{\\text{in}}, E_{\\text{out}}$):** Published energy-per-token coefficients (in milliJoules mJ) from Patterson et al. (2021) and Meta/Mistral model cards (Table 9).
            - **Grid Carbon Intensity ($\text{CI}_{\\text{region}}$):** Regional emissions factor in $\\text{gCO}_2 / \\text{kWh}$ (sourced from Electricity Maps API / IEA regional fallbacks: US = 385, EU = 255, IN = 708, Global = 475).
            """
        )


# ==============================================================================
# TAB 3: Per-Version Trends
# ==============================================================================
with tab_trends:
    st.subheader("Per-Version Prompt Carbon Delta Trends")
    if not df_records.empty:
        fig_trend = px.line(
            df_records.sort_values("id"),
            x="id",
            y="carbon_delta_gco2_1k",
            color="model_name",
            markers=True,
            title="Carbon Delta per 1K Inferences Across Prompt Deployments",
            labels={"id": "Review ID", "carbon_delta_gco2_1k": "gCO2 Delta / 1K Inferences"}
        )
        fig_trend.add_hline(y=0, line_dash="dash", line_color="gray")
        st.plotly_chart(fig_trend, use_container_width=True)


# ==============================================================================
# TAB 4: Team Sustainability Leaderboard
# ==============================================================================
with tab_leaderboard:
    st.subheader("Team Sustainability Leaderboard")
    leaderboard = db.get_team_leaderboard()
    if leaderboard:
        df_lb = pd.DataFrame(leaderboard)
        fig_lb = px.bar(
            df_lb,
            x="team",
            y="net_carbon_delta_1k",
            color="team",
            title="Net Carbon Delta per Team (Lower / Negative is Better)",
            labels={"net_carbon_delta_1k": "Net Carbon Delta (gCO2 / 1K)"}
        )
        st.plotly_chart(fig_lb, use_container_width=True)


# ==============================================================================
# TAB 5: Model Profiles & Energy Data
# ==============================================================================
with tab_models:
    st.subheader("Model Energy & Carbon Profiles (Table 9)")
    model_data = []
    for k, p in MODEL_ENERGY_PROFILES.items():
        model_data.append({
            "Model": p.name,
            "Input Energy (mJ/token)": p.energy_per_input_token_mj,
            "Output Energy (mJ/token)": p.energy_per_output_token_mj,
            "Output/Input Energy Ratio": round(p.energy_per_output_token_mj / p.energy_per_input_token_mj, 2),
            "Source": p.source
        })
    df_models = pd.DataFrame(model_data)

    fig_models = px.bar(
        df_models,
        x="Model",
        y=["Input Energy (mJ/token)", "Output Energy (mJ/token)"],
        barmode="group",
        title="Energy Consumption per Token by Model"
    )
    st.plotly_chart(fig_models, use_container_width=True)
    st.table(df_models)


# ==============================================================================
# TAB 6: Ledger History
# ==============================================================================
with tab_ledger:
    st.subheader("Recent Prompt Carbon Ledger Entries")
    if not df_records.empty:
        st.dataframe(
            df_records[[
                "id", "commit_hash", "author", "team", "model_name", "region",
                "input_token_delta", "predicted_output_token_delta",
                "carbon_delta_gco2_1k", "monthly_carbon_delta_gco2", "status", "timestamp"
            ]],
            use_container_width=True
        )
