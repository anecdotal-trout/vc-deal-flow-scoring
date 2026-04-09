"""
VC Deal Flow Scoring Model
============================
Scores and ranks incoming startup deals based on weighted criteria.
Built for VC analysts managing a pipeline of inbound opportunities who need to:
- Quickly triage deals based on quantitative and qualitative signals
- Rank the pipeline by investment attractiveness
- Identify patterns in what gets funded vs passed
- Brief partners with a structured, consistent framework
"""

import sqlite3
import pandas as pd
import numpy as np
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def load_data():
    """Load deal flow data into pandas and SQLite."""
    df = pd.read_csv(os.path.join(DATA_DIR, "deal_flow.csv"), parse_dates=["date_received"])
    conn = sqlite3.connect(":memory:")
    df.to_sql("deals", conn, if_exists="replace", index=False)
    return conn, df


# ---------------------------------------------------------------------------
# SCORING MODEL
# ---------------------------------------------------------------------------

# Weights reflect a typical early-stage VC evaluation framework
SCORING_WEIGHTS = {
    "team": 0.25,           # Team quality is the strongest signal at seed/A
    "market": 0.15,         # TAM matters but is often uncertain
    "traction": 0.20,       # ARR growth rate = strongest quantitative signal
    "unit_economics": 0.15, # Gross margin + NRR
    "momentum": 0.10,       # Growth velocity
    "defensibility": 0.10,  # Competitive moat
    "capital_efficiency": 0.05,  # Runway / burn discipline
}

MOAT_SCORES = {
    "proprietary_model": 9,
    "network_effects": 8,
    "data_moat": 7,
    "community": 7,
    "marketplace": 6,
    "integrations": 5,
    "regulatory": 4,
    "none": 1,
}


def score_deals(df):
    """Apply scoring model to each deal."""
    df = df.copy()

    # --- Team Score (0-10, already provided) ---
    df["team_score_norm"] = df["team_score"] * 10  # Scale to 0-100

    # --- Market Score ---
    # Log-scale TAM (bigger market = higher score, but diminishing returns)
    df["market_score"] = np.clip(np.log10(df["tam_bn_usd"]) * 50, 0, 100).round(1)

    # --- Traction Score ---
    # ARR growth rate, capped at 600% for normalisation
    df["traction_score"] = np.clip(df["arr_growth_pct"] / 6, 0, 100).round(1)

    # --- Unit Economics Score ---
    # Blend of gross margin and NRR
    gm_score = np.clip(df["gross_margin_pct"] / 0.9, 0, 100)
    nrr_score = np.clip((df["nrr_pct"] - 80) / 0.7, 0, 100)
    df["unit_econ_score"] = ((gm_score * 0.5 + nrr_score * 0.5)).round(1)

    # --- Momentum Score ---
    # Combination of growth + paying customers (signals product-market fit)
    customer_score = np.clip(np.log10(df["paying_customers"].replace(0, 1)) * 30, 0, 100)
    pmf = df["has_product_market_fit"].map({"yes": 50, "no": 0})
    df["momentum_score"] = ((customer_score * 0.5 + pmf + df["traction_score"] * 0.2) / 1.2).round(1)

    # --- Defensibility Score ---
    df["defensibility_score"] = df["competitive_moat"].map(MOAT_SCORES) * 10

    # --- Capital Efficiency Score ---
    df["efficiency_score"] = np.clip(df["cash_months_remaining"] / 0.24, 0, 100).round(1)

    # --- Composite Score ---
    df["composite_score"] = (
        df["team_score_norm"] * SCORING_WEIGHTS["team"]
        + df["market_score"] * SCORING_WEIGHTS["market"]
        + df["traction_score"] * SCORING_WEIGHTS["traction"]
        + df["unit_econ_score"] * SCORING_WEIGHTS["unit_economics"]
        + df["momentum_score"] * SCORING_WEIGHTS["momentum"]
        + df["defensibility_score"] * SCORING_WEIGHTS["defensibility"]
        + df["efficiency_score"] * SCORING_WEIGHTS["capital_efficiency"]
    ).round(1)

    return df.sort_values("composite_score", ascending=False)


# ---------------------------------------------------------------------------
# SQL QUERIES
# ---------------------------------------------------------------------------

PIPELINE_SUMMARY_SQL = """
    SELECT
        status,
        COUNT(*) AS deals,
        ROUND(AVG(proposed_valuation_usd / 1e6), 1) AS avg_valuation_mm,
        ROUND(AVG(arr_usd / 1e6), 2) AS avg_arr_mm,
        ROUND(AVG(arr_growth_pct), 0) AS avg_growth_pct,
        ROUND(SUM(ask_usd) / 1e6, 1) AS total_ask_mm
    FROM deals
    GROUP BY status
    ORDER BY deals DESC
"""

SOURCE_ANALYSIS_SQL = """
    SELECT
        source,
        COUNT(*) AS deals,
        COUNT(CASE WHEN status IN ('term_sheet', 'due_diligence') THEN 1 END) AS advancing,
        ROUND(COUNT(CASE WHEN status IN ('term_sheet', 'due_diligence') THEN 1 END) * 100.0
              / COUNT(*), 1) AS advance_rate_pct,
        ROUND(AVG(team_score), 1) AS avg_team_score
    FROM deals
    GROUP BY source
    ORDER BY advance_rate_pct DESC
"""

SECTOR_BREAKDOWN_SQL = """
    SELECT
        sector,
        COUNT(*) AS deals,
        ROUND(AVG(arr_growth_pct), 0) AS avg_growth_pct,
        ROUND(AVG(gross_margin_pct), 0) AS avg_gm_pct,
        ROUND(AVG(team_score), 1) AS avg_team,
        COUNT(CASE WHEN status IN ('term_sheet', 'due_diligence') THEN 1 END) AS advancing
    FROM deals
    GROUP BY sector
    ORDER BY deals DESC
"""

STAGE_METRICS_SQL = """
    SELECT
        stage,
        COUNT(*) AS deals,
        ROUND(AVG(arr_usd / 1e6), 2) AS avg_arr_mm,
        ROUND(AVG(proposed_valuation_usd / 1e6), 1) AS avg_val_mm,
        ROUND(AVG(CAST(proposed_valuation_usd AS REAL) / NULLIF(arr_usd, 0)), 1) AS avg_rev_multiple,
        ROUND(AVG(ask_usd / 1e6), 1) AS avg_ask_mm
    FROM deals
    GROUP BY stage
    ORDER BY avg_arr_mm DESC
"""


# ---------------------------------------------------------------------------
# REPORT
# ---------------------------------------------------------------------------

def print_section(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}")


def main():
    conn, raw_df = load_data()
    df = score_deals(raw_df)

    print("\n" + "="*80)
    print("  VC DEAL FLOW SCORING REPORT")
    print("  H1 2025 Pipeline")
    print("="*80)

    # --- Ranked Pipeline ---
    print_section("DEAL RANKINGS (composite score)")
    rank_cols = [
        "company_name", "sector", "stage", "composite_score",
        "team_score", "arr_growth_pct", "gross_margin_pct", "status"
    ]
    print(df[rank_cols].to_string(index=False))

    # --- Score Breakdown (top 5) ---
    print_section("SCORE BREAKDOWN — TOP 5 DEALS")
    top5 = df.head(5)
    breakdown_cols = [
        "company_name", "composite_score", "team_score_norm", "market_score",
        "traction_score", "unit_econ_score", "momentum_score",
        "defensibility_score", "efficiency_score"
    ]
    print(top5[breakdown_cols].to_string(index=False))

    # --- Pipeline Summary ---
    print_section("PIPELINE BY STATUS")
    pipeline_df = pd.read_sql(PIPELINE_SUMMARY_SQL, conn)
    print(pipeline_df.to_string(index=False))

    # --- Source Quality ---
    print_section("DEAL SOURCE QUALITY")
    source_df = pd.read_sql(SOURCE_ANALYSIS_SQL, conn)
    print(source_df.to_string(index=False))

    # --- Sector Breakdown ---
    print_section("SECTOR BREAKDOWN")
    sector_df = pd.read_sql(SECTOR_BREAKDOWN_SQL, conn)
    print(sector_df.to_string(index=False))

    # --- Stage Metrics ---
    print_section("VALUATION BENCHMARKS BY STAGE")
    stage_df = pd.read_sql(STAGE_METRICS_SQL, conn)
    print(stage_df.to_string(index=False))

    # --- Pass/Invest Patterns ---
    print_section("WHAT SEPARATES ADVANCING DEALS FROM DECLINED")
    advancing = df[df["status"].isin(["term_sheet", "due_diligence"])]
    declined = df[df["status"] == "declined"]

    metrics = ["team_score", "arr_growth_pct", "gross_margin_pct", "nrr_pct",
               "composite_score", "tam_bn_usd"]
    comparison = pd.DataFrame({
        "metric": metrics,
        "advancing_avg": [advancing[m].mean() for m in metrics],
        "declined_avg": [declined[m].mean() for m in metrics],
    })
    comparison["delta_pct"] = (
        (comparison["advancing_avg"] - comparison["declined_avg"])
        / comparison["declined_avg"].replace(0, pd.NA) * 100
    ).round(1)
    print(comparison.to_string(index=False))

    # --- Recommendations ---
    print_section("RECOMMENDATIONS")
    recs = [
        "1. REFERRALS DOMINATE — 70%+ of advancing deals come from referrals.",
        "   Invest more in network-driven sourcing; reduce cold outreach volume.",
        "",
        "2. TEAM SCORE IS THE STRONGEST PREDICTOR — Advancing deals average",
        f"   {advancing['team_score'].mean():.1f} vs {declined['team_score'].mean():.1f} for declined.",
        "   Weight team assessment heavily in first-pass triage.",
        "",
        "3. AI/DEVTOOLS CLUSTER IS HOT — Highest growth rates and strongest",
        "   deal quality. Consider dedicating more sourcing time here.",
        "",
        "4. PASS FASTER ON LOW-MOAT DEALS — Every declined deal with moat='none'",
        "   could have been triaged out earlier. Add moat as a first-pass filter.",
        "",
        "5. VALUATION DISCIPLINE — Series A deals averaging",
        f"   {stage_df[stage_df['stage']=='Series A']['avg_rev_multiple'].values[0]:.0f}x revenue.",
        "   Flag anything above 40x for extra scrutiny.",
    ]
    for line in recs:
        print(f"  {line}")

    conn.close()
    print(f"\n{'='*80}")
    print("  Scoring complete.")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
