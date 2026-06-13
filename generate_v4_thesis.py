"""
Generate v4 Investment Thesis PDF
==================================
Reads artifacts produced by strategy_selection_v2.py (v4 run):
  - v4_chained_series.csv     (chained portfolio vs SPX, daily)
  - v4_cohort_regimes.csv     (per-cohort selection + regime label)
  - strategy_selection_v4_results.csv  (per-cohort metrics table)

Builds OTP2.0_v4_investment_thesis.pdf with cover/text, equity curve,
drawdown chart, per-cohort metrics chart, regime timeline, and a final
v1-v4 vs SPX comparison table.

Usage:
  python generate_v4_thesis.py
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_pdf import PdfPages

series = pd.read_csv("v4_chained_series.csv", parse_dates=["date"])
regimes = pd.read_csv("v4_cohort_regimes.csv")
cohorts = pd.read_csv("strategy_selection_v4_results.csv")

COMPARISON_ROWS = [
    ("v1 (original, 5yr cohorts, top8)",        0.625, 8.89,  -17.7),
    ("v2 (50-stock universe, fixed threshold)", 0.642, 13.12, -52.0),
    ("v3 (regime tertiles, tech tilt)",         0.617, 11.06, -33.4),
    ("v4 (+ CAPE froth override)",              0.654, 11.25, -26.1),
    ("SPX Buy & Hold",                          0.322, 9.17,  -56.8),
]

REGIME_COLORS = {
    "Momentum (high)": "#2e7d32",
    "Default (mid)": "#9e9e9e",
    "Defensive (low)": "#1565c0",
}

with PdfPages("OTP2.0_v4_investment_thesis.pdf") as pdf:

    # ── Page 1: Cover / thesis text ─────────────────────────────────────────
    fig = plt.figure(figsize=(8.5, 11))
    fig.text(0.5, 0.95, "OTP2.0 v4 — Investment Thesis", ha="center", fontsize=18, weight="bold")
    fig.text(0.5, 0.915, "Active-management overlay on a tech-tilted equity sleeve",
             ha="center", fontsize=11, style="italic")

    body = """
STRATEGY OVERVIEW

OTP2.0 v4 combines two pillars:

1. Security Selection: a 54-stock universe spanning old-economy mega-caps
   (MSFT, JNJ, PG, JPM, ...) and modern growth/tech leaders (NVDA, META,
   AMZN, AVGO, TSLA, AMD, ...). Every 3 years, stocks are ranked on a
   5-factor composite score:
     - F1 12-month momentum            30%
     - F2 % days above 50-day SMA      20%
     - F3 3-yr CAGR / volatility       20%
     - F4 Drawdown resilience (1/|MaxDD|, 5yr)  10%
     - F5 252-day relative strength vs SPX      20%
   The top 7 stocks form an equal-weighted "cohort" held for 3 years.

2. Timing Overlay (OTP1.0, locked engine): a daily two-bucket
   (invested/cash) allocator that scales exposure using realized
   volatility, trend (SMA50/100/200), VIX-based risk triggers, and a
   gradual reload mechanism after risk-off periods.

REGIME-AWARE CONFIGURATION (v4's key addition)

Each cohort's timing configuration is set ex-ante (no lookahead) based on
two signals measured at the selection date:

  - Composite-tertile: cohorts whose mean factor-composite score is in the
    top third get a "Momentum" config (higher vol target, faster reloads);
    bottom third get a tighter "Defensive" config; middle third use the
    default OTP1.0 config.

  - CAPE valuation override: if the Shiller CAPE ratio at the selection
    date is >= 30 (roughly the top decile of its 1881-present history),
    the cohort is forced to the Defensive config REGARDLESS of its
    momentum tertile. This flags 1999, 2020, and 2026 as "frothy" markets
    where momentum-based optimism historically preceded sharp corrections.

RESULT vs. THE BAR

Target bar: chained Sharpe > 1.0  OR  CAGR > 15%, with a "significant
margin" over the market (SPX B&H: Sharpe 0.322, CAGR 9.17%).

  v4 chained (1993-2026, hindsight-free, sequential cohorts):
     Sharpe   0.654   (≈2.0x SPX)
     CAGR     11.25%  (SPX 9.17%, +2.1pp)
     MaxDD   -26.1%   (SPX -56.8%, less than half)

  -> Bar NOT reached. v4 delivers a real, repeatable risk-adjusted edge
     (roughly double SPX's Sharpe) and a materially shallower drawdown,
     but the absolute return edge over SPX (+2.1pp CAGR) is modest, not
     the "significant margin" the bar requires.

This thesis presents v4 as the best-performing of four iterations tested
(v1-v4), with full transparency on its regime behavior and where its edge
comes from.
"""
    fig.text(0.07, 0.88, body, ha="left", va="top", fontsize=8.3, family="monospace",
             wrap=True)
    fig.text(0.5, 0.02, "Page 1 of 6", ha="center", fontsize=8, color="gray")
    pdf.savefig(fig)
    plt.close(fig)

    # ── Page 2: Equity curve ────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(8.5, 11 * 0.55))
    ax.plot(series["date"], series["v4_portfolio"], label="OTP2.0 v4 (selection + timing overlay)",
            color="#1565c0", linewidth=1.3)
    ax.plot(series["date"], series["spx_portfolio"], label="SPX Buy & Hold",
            color="#9e9e9e", linewidth=1.3)
    ax.set_yscale("log")
    ax.set_title("Chained Equity Curve (Hindsight-Free, 1993-2026)\nStarting value = 100, log scale")
    ax.set_ylabel("Portfolio value (log scale)")
    ax.set_xlabel("Date")
    ax.legend(loc="upper left")
    ax.grid(True, which="both", alpha=0.3)

    # cohort boundary markers
    cohort_starts = pd.to_datetime([c.split("-")[0] + "-01-04" for c in cohorts["Cohort"]],
                                    errors="coerce")
    for d in cohort_starts:
        if pd.notna(d) and d >= series["date"].min() and d <= series["date"].max():
            ax.axvline(d, color="black", alpha=0.08, linewidth=0.8)

    fig.text(0.5, 0.02, "Page 2 of 6", ha="center", fontsize=8, color="gray")
    pdf.savefig(fig)
    plt.close(fig)

    # ── Page 3: Drawdown chart ───────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(8.5, 11 * 0.55))
    for col, label, color in [("v4_portfolio", "OTP2.0 v4", "#1565c0"),
                                ("spx_portfolio", "SPX Buy & Hold", "#9e9e9e")]:
        vals = series[col].values
        running_max = np.maximum.accumulate(vals)
        dd = (vals - running_max) / running_max * 100
        ax.fill_between(series["date"], dd, 0, alpha=0.3, color=color, label=label)
        ax.plot(series["date"], dd, color=color, linewidth=0.8)

    ax.set_title("Underwater Equity (Drawdown from Running Peak)\n"
                  "v4 MaxDD -26.1% vs SPX MaxDD -56.8%")
    ax.set_ylabel("Drawdown (%)")
    ax.set_xlabel("Date")
    ax.legend(loc="lower left")
    ax.grid(True, alpha=0.3)
    fig.text(0.5, 0.02, "Page 3 of 6", ha="center", fontsize=8, color="gray")
    pdf.savefig(fig)
    plt.close(fig)

    # ── Page 4: Per-cohort Sharpe & CAGR ─────────────────────────────────────
    fig, axes = plt.subplots(2, 1, figsize=(8.5, 11 * 0.75))
    x = np.arange(len(cohorts))
    width = 0.25

    sharpe_cols = [("OT2.0 Sharpe", "v4 Overlay", "#1565c0"),
                    ("Cohort B&H Sharpe", "Cohort B&H", "#66bb6a"),
                    ("SPX Sharpe", "SPX B&H", "#9e9e9e")]
    for i, (col, label, color) in enumerate(sharpe_cols):
        axes[0].bar(x + (i - 1) * width, cohorts[col].astype(float), width, label=label, color=color)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(cohorts["Cohort"], rotation=45, ha="right", fontsize=7)
    axes[0].axhline(0, color="black", linewidth=0.6)
    axes[0].set_title("Per-Cohort Sharpe Ratio")
    axes[0].legend(fontsize=8)
    axes[0].grid(True, axis="y", alpha=0.3)

    cagr_cols = [("OT2.0 CAGR", "v4 Overlay", "#1565c0"),
                   ("Cohort B&H CAGR", "Cohort B&H", "#66bb6a"),
                   ("SPX CAGR", "SPX B&H", "#9e9e9e")]
    for i, (col, label, color) in enumerate(cagr_cols):
        vals = cohorts[col].astype(str).str.rstrip("%").astype(float)
        axes[1].bar(x + (i - 1) * width, vals, width, label=label, color=color)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(cohorts["Cohort"], rotation=45, ha="right", fontsize=7)
    axes[1].axhline(0, color="black", linewidth=0.6)
    axes[1].set_title("Per-Cohort CAGR (%)")
    axes[1].legend(fontsize=8)
    axes[1].grid(True, axis="y", alpha=0.3)

    fig.suptitle("Per-Cohort Performance: v4 Overlay vs. Cohort Buy&Hold vs. SPX", y=0.99)
    fig.tight_layout(rect=[0, 0.03, 1, 0.97])
    fig.text(0.5, 0.01, "Page 4 of 6", ha="center", fontsize=8, color="gray")
    pdf.savefig(fig)
    plt.close(fig)

    # ── Page 5: Regime timeline ───────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(8.5, 11 * 0.55))
    for i, row in regimes.iterrows():
        label = row["RegimeLabel"]
        base_label = label.split(" (")[0] if "(" in label else label
        if "Defensive (CAPE" in label:
            color = "#c62828"
            base_label = "Defensive (CAPE frothy)"
        else:
            color = REGIME_COLORS.get(label, "#bdbdbd")
        ax.barh(i, 1, left=0, color=color, edgecolor="white")
        ax.text(0.5, i, f"{row['Cohort']}\n{label}\nmean composite={row['MeanComposite']:.3f}",
                ha="center", va="center", fontsize=7.5, color="white", weight="bold")

    ax.set_yticks([])
    ax.set_xticks([])
    ax.set_ylim(-0.5, len(regimes) - 0.5)
    ax.invert_yaxis()
    ax.set_title("Regime-Tilt Timeline: Timing Configuration Assigned per Cohort\n"
                  "(green=Momentum, gray=Default, blue=Defensive-tertile, red=Defensive-CAPE-frothy)")

    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    fig.text(0.5, 0.01, "Page 5 of 6", ha="center", fontsize=8, color="gray")
    pdf.savefig(fig)
    plt.close(fig)

    # ── Page 6: Final comparison table ───────────────────────────────────────
    fig, ax = plt.subplots(figsize=(8.5, 11 * 0.45))
    ax.axis("off")
    col_labels = ["Variant", "Sharpe", "CAGR", "MaxDD"]
    table_data = [[name, f"{s:.3f}", f"{c:.2f}%", f"{d:.1f}%"] for name, s, c, d in COMPARISON_ROWS]
    tbl = ax.table(cellText=table_data, colLabels=col_labels, loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    tbl.scale(1, 2)
    for (r, c), cell in tbl.get_celld().items():
        if r == 0:
            cell.set_facecolor("#1565c0")
            cell.set_text_props(color="white", weight="bold")
        elif table_data[r - 1][0].startswith("v4"):
            cell.set_facecolor("#e3f2fd")

    ax.set_title("Final Comparison: v1-v4 vs. SPX Buy & Hold\n"
                  "(Chained, hindsight-free, 1993-2026)\n\n"
                  "Target bar: Sharpe > 1.0  OR  CAGR > 15%  ->  NOT REACHED by any variant\n"
                  "v4 is the best risk-adjusted result (~2x SPX Sharpe, less than half SPX's drawdown)",
              fontsize=11, pad=20)
    fig.text(0.5, 0.02, "Page 6 of 6", ha="center", fontsize=8, color="gray")
    pdf.savefig(fig)
    plt.close(fig)

print("Saved OTP2.0_v4_investment_thesis.pdf")
