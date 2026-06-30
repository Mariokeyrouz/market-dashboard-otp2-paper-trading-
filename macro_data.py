"""
Macro Dashboard — mock data layer (FIRST PASS / PLACEHOLDER).

================================================================================
ALL VALUES IN THIS MODULE ARE MOCK / PLACEHOLDER — NOT REAL MARKET LEVELS.
They exist so we can validate dashboard layout and classification logic before
wiring a real feed. Nothing here should be read as a current market quote.
================================================================================

This module is the single, contained swap-point for going live later. Each
function returns one logical panel's worth of data. When we wire real data, we
edit ONLY this file: replace the function bodies with FRED / yfinance pulls
(the FRED series id intended for each field is noted in a trailing comment) and
flip MOCK = False. The view (pages/3_Macro_Dashboard.py) and the classification
logic (macro_logic.py) never need to change.

Series mapping for the eventual real-data swap
----------------------------------------------
  10Y nominal yield ....... FRED DGS10
  10Y real yield (TIPS) ... FRED DFII10   (already used in pages/2_Gold_Strategy.py)
  10Y breakeven (BEI) ..... FRED T10YIE   (== DGS10 - DFII10)
  Financial Conditions .... FRED NFCI     (+ve = tighter than average)
  CPI headline / core ..... FRED CPIAUCSL / CPILFESL (YoY)
  HY OAS (credit spread) .. FRED BAMLH0A0HYM2
  Dollar index (DXY) ...... yfinance DX-Y.NYB (already fetched in app.py)
  VIX term structure ...... VIX (^VIX) front vs. VIX3M / futures curve
"""

# Flip-and-replace marker for the real-data swap. While True, the view shows a
# clear "mock data" banner so fake numbers are never mistaken for live quotes.
MOCK = True

# Default lookback window (trading days) used to measure how much each leg moved.
DEFAULT_LOOKBACK_DAYS = 5


# ── Layer 2 — The Hinge (centerpiece) ─────────────────────────────────────────
def layer2_hinge(lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> dict:
    """10Y nominal yield decomposed into real + breakeven legs.

    Identity:  nominal = real + breakeven

    For each leg we return the current ``level`` (in %) and ``chg`` — the change
    over the lookback window (in percentage points). ``*_series`` are short mock
    histories (oldest → newest) used to draw the decomposition chart.

    The mock is deliberately tuned to an "Inflation Scare": nominal is rising and
    the breakeven leg is the dominant mover. Edit these numbers to preview how the
    classification banner reacts (e.g. make ``real.chg`` the larger move to see a
    "Growth/Tightening Shock").
    """
    return {
        "lookback_days": lookback_days,
        "nominal":   {"level": 4.20, "chg": +0.15},   # FRED DGS10
        "real":      {"level": 1.95, "chg": +0.03},   # FRED DFII10
        "breakeven": {"level": 2.25, "chg": +0.12},   # FRED T10YIE
        # Short mock series (oldest → newest). Lengths match; purely illustrative.
        "nominal_series":   [4.05, 4.06, 4.04, 4.09, 4.12, 4.16, 4.20],
        "real_series":      [1.92, 1.93, 1.92, 1.93, 1.94, 1.95, 1.95],
        "breakeven_series": [2.13, 2.13, 2.12, 2.16, 2.18, 2.21, 2.25],
    }


# ── Layer 2 secondary — Financial Conditions Index ────────────────────────────
def financial_conditions() -> dict:
    """Financial Conditions Index — continuous, forward-looking (daily clock).

    Convention (matches FRED NFCI): positive = conditions TIGHTER than average,
    negative = LOOSER than average. ``chg`` is the change over the recent window.
    """
    return {
        "level": -0.15,                # FRED NFCI (mock); -ve = looser than avg
        "chg":   -0.04,                # easing slightly over the window
        "series": [-0.02, -0.05, -0.08, -0.10, -0.11, -0.13, -0.15],
    }


# ── Layer 1 — Regime (slow, backward-looking) ─────────────────────────────────
def layer1_regime(region: str = "intl") -> dict:
    """Hard-macro inputs for the regime badge (monthly clock), per region lens.

    ``region`` ∈ {"intl","us","eu"}. CPI/HICP prints are YoY %. ``cpi_trend`` /
    ``growth`` are coarse stubbed reads feeding macro_logic.classify_regime().
    The real-yield hinge stays US regardless — this only re-frames the *context*.
    """
    table = {
        # International = G3 / world composite
        "intl": {"region_label": "Global (G3)", "price_label": "CPI (G3)",
                 "headline": 3.4, "core": 3.2, "cpi_trend": "sticky", "growth": "slowing",
                 "as_of": "MOCK · world composite"},   # blended OECD/G3 (mock)
        "us":   {"region_label": "United States", "price_label": "CPI",
                 "headline": 3.1, "core": 3.3, "cpi_trend": "sticky", "growth": "slowing",
                 "as_of": "MOCK · last US print"},      # FRED CPIAUCSL / CPILFESL
        "eu":   {"region_label": "Euro Area", "price_label": "HICP",
                 "headline": 2.4, "core": 2.7, "cpi_trend": "cooling", "growth": "slowing",
                 "as_of": "MOCK · last euro print"},    # Eurostat HICP / core
    }
    d = table.get(region, table["intl"])
    return {
        "region_label": d["region_label"],
        "price_label":  d["price_label"],
        "cpi_headline": d["headline"],
        "cpi_core":     d["core"],
        "cpi_trend":    d["cpi_trend"],   # cooling | sticky | rising
        "growth":       d["growth"],      # expanding | slowing | contracting
        "as_of":        d["as_of"],
    }


# ── Layer 3 — Fast confirming / tripwire signals ──────────────────────────────
def layer3_tripwires() -> dict:
    """Faster confirming signals. Directional framing only — NO fabricated
    correlation coefficients or hit-rates are attached to these (by design).

    - hy_oas:   high-yield OAS in %, leading-stress framing for equities.
    - dxy:      dollar index level, the "global liquidity valve".
    - vix_term: front vs. back vol; front < back ⇒ contango (risk-on tilt).
    """
    return {
        "hy_oas":   {"level": 3.20,  "chg": +0.10},          # FRED BAMLH0A0HYM2
        "dxy":      {"level": 104.8, "chg": +0.30},          # yfinance DX-Y.NYB
        "vix_term": {"front": 18.2,  "back": 19.6},          # ^VIX vs VIX3M (mock)
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROUND 2 — expanded macro panels (all MOCK). Each panel feeds the three-layer
# thesis. FRED / yfinance ids for the eventual real-data swap are noted inline.
# ══════════════════════════════════════════════════════════════════════════════

# ── Layer 1 support — Growth Nowcast (region lens) ────────────────────────────
def growth_nowcast(region: str = "intl") -> dict:
    """Forward-ish growth reads that flesh out the regime layer, per region.

    Region-neutral keys (mfg / services / claims) carry display labels so the view
    can render uniformly. ``copper_gold_ratio`` stays global. All MOCK.
      US/intl PMIs ≈ ISM; EU ≈ HCOB/S&P euro PMI. Claims: US ICSA; EU shows the
      unemployment rate instead.
    """
    cg = {  # copper/gold ratio is global — same across regions
        "level": 0.00152,                                    # HG=F / GC=F (mock)
        "series": [0.00161, 0.00159, 0.00157, 0.00156, 0.00154, 0.00153, 0.00152],
    }
    table = {
        "intl": {"surprise_label": "Citi Surprise (G10)", "surprise": -9.0, "pmi_name": "PMI",
                 "mfg": {"level": 49.4, "chg": -0.3}, "services": {"level": 51.8, "chg": -0.4},
                 "claims_label": "Global trade", "claims": {"level": "soft", "trend": "rising", "is_text": True}},
        "us":   {"surprise_label": "Citi Surprise (US)", "surprise": -12.0, "pmi_name": "ISM",
                 "mfg": {"level": 48.7, "chg": -0.4}, "services": {"level": 51.3, "chg": -0.6},
                 "claims_label": "Jobless Claims", "claims": {"level": 233, "unit": "k", "trend": "rising"}},
        "eu":   {"surprise_label": "Citi Surprise (EU)", "surprise": +4.0, "pmi_name": "PMI",
                 "mfg": {"level": 46.1, "chg": +0.5}, "services": {"level": 50.4, "chg": -0.2},
                 "claims_label": "Unemployment", "claims": {"level": 6.4, "unit": "%", "trend": "steady"}},
    }
    d = table.get(region, table["intl"])
    return {**d, "copper_gold_ratio": cg}


# ── Layer 2 support — US Rates & Curve (always US; policy split out) ───────────
def rates_curve_policy() -> dict:
    """US Treasury curve structure behind the real-yield leg. Stays US regardless
    of region (US reals = the global discount rate).

    - slope_2s10s / slope_3m10y: curve slopes in pp; negative = inverted
      (FRED T10Y2Y / T10Y3M).
    - move_index: MOVE — the bond-market's VIX (rate vol). yfinance ^MOVE.
    """
    return {
        "slope_2s10s": {"level": +0.34, "chg": +0.05},       # FRED T10Y2Y (mock)
        "slope_3m10y": {"level": -0.18, "chg": +0.03},       # FRED T10Y3M (mock)
        "move_index":  {"level": 98.0, "chg": +3.5},         # yfinance ^MOVE (mock)
    }


# ── Central-bank policy (region lens) ─────────────────────────────────────────
def central_bank_policy(region: str = "intl") -> dict:
    """The relevant central bank's stance for the selected region. Fed for US &
    International (Fed sets the global anchor); ECB for Europe. All MOCK.
    """
    table = {
        "intl": {"bank": "Fed", "rate_label": "Fed Funds", "low": 4.25, "high": 4.50,
                 "implied_count": 2, "implied_bps": 50, "horizon": "by Dec 2026"},
        "us":   {"bank": "Fed", "rate_label": "Fed Funds", "low": 4.25, "high": 4.50,
                 "implied_count": 2, "implied_bps": 50, "horizon": "by Dec 2026"},
        "eu":   {"bank": "ECB", "rate_label": "Deposit Rate", "low": 2.50, "high": 2.50,
                 "implied_count": 1, "implied_bps": 25, "horizon": "by Dec 2026"},
    }
    return table.get(region, table["intl"])


# ── Credit spreads (region lens) ──────────────────────────────────────────────
def credit_spreads(region: str = "intl") -> dict:
    """High-yield & investment-grade OAS for the region (pp). US: BAMLH0A0HYM2 /
    BAMLC0A0CM; EU: BAMLHE00EHYIOAS / euro IG. All MOCK.
    """
    table = {
        "intl": {"label": "US / global", "hy": {"level": 3.20, "chg": +0.10}, "ig": {"level": 0.92, "chg": +0.03}},
        "us":   {"label": "US",          "hy": {"level": 3.20, "chg": +0.10}, "ig": {"level": 0.92, "chg": +0.03}},
        "eu":   {"label": "Euro",        "hy": {"level": 3.05, "chg": +0.08}, "ig": {"level": 1.05, "chg": +0.04}},
    }
    return table.get(region, table["intl"])


# ── Layer 3 support — Commodities & Inflation Impulse ─────────────────────────
def commodities_impulse() -> dict:
    """The real-economy inflation impulse that drives the breakeven leg.

    Each item: current {level, chg} plus a short series for a sparkline. All MOCK.
    FRED/yfinance: WTI CL=F, Brent BZ=F, gasoline RB=F, copper HG=F, gold GC=F,
    broad commodity index via DBC / CRB.
    """
    return {
        "wti":      {"level": 70.94, "chg": +2.47, "series": [66.1, 67.0, 68.4, 69.1, 69.8, 70.2, 70.94]},
        "brent":    {"level": 74.60, "chg": +2.10, "series": [70.2, 71.0, 72.1, 72.9, 73.5, 74.0, 74.60]},
        "gasoline": {"level": 2.18,  "chg": +1.80, "series": [2.05, 2.07, 2.10, 2.12, 2.14, 2.16, 2.18]},
        "copper":   {"level": 6.175, "chg": +0.55, "series": [5.98, 6.02, 6.05, 6.10, 6.13, 6.15, 6.175]},
        "gold":     {"level": 4038.2, "chg": -0.99, "series": [4080, 4072, 4060, 4055, 4048, 4044, 4038.2]},
        "commodity_index": {"level": 24.6, "chg": +1.15, "series": [23.6, 23.8, 24.0, 24.2, 24.3, 24.5, 24.6]},
    }


# ── Layer 3 support — Liquidity (US/global plumbing) ──────────────────────────
def liquidity_credit() -> dict:
    """US/global liquidity plumbing behind financial conditions (credit spreads now
    live in credit_spreads(region)).

    - net_liquidity: Fed balance sheet − RRP − TGA, in $T (FRED WALCL − RRPONTSYD −
      WTREGEN).
    - bank_reserves: reserve balances in $T (FRED WRESBAL).
    """
    return {
        "net_liquidity": {
            "level": 5.92, "trend": "draining",              # $T (mock)
            "series": [6.18, 6.12, 6.07, 6.02, 5.99, 5.95, 5.92],
        },
        "bank_reserves": {"level": 3.21, "trend": "falling"},  # $T (mock)
    }


# ── Cross-asset / FX views (region lens) ──────────────────────────────────────
def fx_panel(region: str = "intl") -> dict:
    """FX framing per region. Each row: name / level / chg / fmt / good_up (whether
    an up-move is supportive for that region's risk). All MOCK (yfinance crosses).
    """
    def r(name, level, chg, fmt, good_up):
        return {"name": name, "level": level, "chg": chg, "fmt": fmt, "good_up": good_up}
    table = {
        "intl": [r("DXY", 104.80, +0.30, "{:.2f}", False), r("EUR/USD", 1.0720, -0.25, "{:.4f}", True),
                 r("USD/JPY", 157.20, +0.45, "{:.2f}", False), r("GBP/USD", 1.272, -0.18, "{:.3f}", True),
                 r("EM FX", 41.8, -0.40, "{:.1f}", True)],
        "us":   [r("DXY", 104.80, +0.30, "{:.2f}", False), r("EUR/USD", 1.0720, -0.25, "{:.4f}", False),
                 r("USD/JPY", 157.20, +0.45, "{:.2f}", False), r("USD/CNH", 7.265, +0.12, "{:.3f}", False),
                 r("USD/CAD", 1.372, +0.10, "{:.3f}", False)],
        "eu":   [r("EUR/USD", 1.0720, -0.25, "{:.4f}", True), r("EUR/GBP", 0.843, +0.15, "{:.3f}", True),
                 r("EUR/JPY", 168.6, +0.20, "{:.1f}", True), r("EUR/CHF", 0.958, +0.08, "{:.3f}", True),
                 r("DXY", 104.80, +0.30, "{:.2f}", False)],
    }
    return {"rows": table.get(region, table["intl"])}


def cross_asset(region: str = "intl") -> list:
    """One-glance cross-asset positioning band, region-filtered. Each row carries
    multi-timeframe % changes (1D/1W/1M/YTD) and a short spark series. All MOCK.
    (10Y rows are yield changes in pp, not %.)
    """
    def row(name, level, d1, d1w, d1m, ytd, spark):
        return {"name": name, "level": level, "d1": d1, "d1w": d1w,
                "d1m": d1m, "ytd": ytd, "spark": spark}
    us_rows = [
        row("S&P 500",  7433.55, +1.08, +1.9, +3.4, +12.6, [7180, 7240, 7300, 7350, 7390, 7410, 7433]),
        row("Nasdaq",  24210.0,  +1.32, +2.4, +4.1, +16.2, [23200, 23450, 23700, 23900, 24050, 24150, 24210]),
        row("Russell", 3002.39,  -0.26, +0.4, +1.1,  +3.8, [2960, 2975, 2988, 2995, 3008, 3006, 3002]),
        row("Gold",    4038.20,  -0.99, -1.4, +2.6, +18.0, [4080, 4072, 4060, 4055, 4048, 4044, 4038]),
        row("Oil WTI",   70.94,  +2.47, +3.1, -2.2,  -4.5, [66.1, 67.0, 68.4, 69.1, 69.8, 70.2, 70.94]),
        row("DXY",      104.80,  +0.30, +0.6, -0.8,  +1.2, [103.9, 104.1, 104.3, 104.5, 104.6, 104.7, 104.8]),
        row("10Y UST",    4.376, +0.09, +0.12, +0.18, +0.35, [4.05, 4.10, 4.18, 4.26, 4.31, 4.35, 4.376]),
        row("Bitcoin", 92850.0,  +0.85, +4.2, +6.8, +22.4, [86000, 87500, 89000, 90500, 91800, 92400, 92850]),
    ]
    eu_rows = [
        row("Euro Stoxx 50", 5180.0, +0.74, +1.2, +2.1,  +9.4, [4980, 5020, 5060, 5100, 5140, 5165, 5180]),
        row("DAX",        21640.0,  +0.62, +1.0, +2.4, +11.0, [20800, 20950, 21100, 21300, 21500, 21600, 21640]),
        row("CAC 40",      8120.0,  +0.41, +0.7, +1.3,  +5.2, [7900, 7950, 7990, 8040, 8090, 8110, 8120]),
        row("FTSE 100",    8460.0,  +0.33, +0.5, +1.0,  +6.1, [8260, 8300, 8340, 8390, 8430, 8450, 8460]),
        row("Gold (EUR)",  3765.0,  -0.70, -1.1, +2.9, +20.2, [3800, 3792, 3782, 3776, 3772, 3768, 3765]),
        row("Brent",        74.60,  +2.10, +2.8, -1.8,  -3.9, [70.2, 71.0, 72.1, 72.9, 73.5, 74.0, 74.60]),
        row("EUR/USD",      1.0720, -0.25, -0.4, +0.6,  -1.1, [1.082, 1.079, 1.077, 1.075, 1.074, 1.073, 1.072]),
        row("Bund 10Y",     2.380, +0.06, +0.10, +0.14, +0.28, [2.10, 2.16, 2.22, 2.28, 2.33, 2.36, 2.38]),
    ]
    intl_rows = [
        row("MSCI ACWI",    862.0,  +0.71, +1.4, +2.9, +11.8, [820, 828, 836, 844, 852, 858, 862]),
        row("S&P 500",     7433.55, +1.08, +1.9, +3.4, +12.6, [7180, 7240, 7300, 7350, 7390, 7410, 7433]),
        row("Euro Stoxx",  5180.0,  +0.74, +1.2, +2.1,  +9.4, [4980, 5020, 5060, 5100, 5140, 5165, 5180]),
        row("Nikkei",     41850.0,  +0.55, +1.6, +3.0, +10.4, [40200, 40600, 41000, 41400, 41650, 41780, 41850]),
        row("EM (MSCI)",   1142.0,  +0.40, +0.9, +2.2,  +8.7, [1090, 1100, 1112, 1124, 1132, 1138, 1142]),
        row("Gold",       4038.20,  -0.99, -1.4, +2.6, +18.0, [4080, 4072, 4060, 4055, 4048, 4044, 4038]),
        row("Oil (Brent)",  74.60,  +2.10, +2.8, -1.8,  -3.9, [70.2, 71.0, 72.1, 72.9, 73.5, 74.0, 74.60]),
        row("10Y UST",      4.376, +0.09, +0.12, +0.18, +0.35, [4.05, 4.10, 4.18, 4.26, 4.31, 4.35, 4.376]),
    ]
    return {"us": us_rows, "eu": eu_rows, "intl": intl_rows}.get(region, intl_rows)


def gold_real_overlay() -> dict:
    """Gold as a pure real-rate play — gold vs. 10Y real yield.

    Both series are INDEXED to 100 at the window start so they share one scale and
    the (typically inverse) co-movement is visible. The relationship is described
    DIRECTIONALLY only — no fabricated correlation coefficient. All MOCK.
    """
    return {
        "gold_index":  [100.0, 99.8, 99.0, 98.7, 98.1, 97.8, 97.5],   # GC=F indexed
        "real_index":  [100.0, 100.3, 100.8, 101.1, 101.4, 101.6, 101.9],  # DFII10 indexed (inverted move)
        "relationship": "inverse",   # directional only — gold up when real yields fall
        "gold_level":  4038.2,
        "real_level":  1.95,
    }
