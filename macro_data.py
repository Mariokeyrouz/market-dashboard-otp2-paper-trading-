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
def layer1_regime() -> dict:
    """Hard-macro inputs for the regime badge (monthly clock).

    CPI prints are YoY %. ``cpi_trend`` / ``growth`` are coarse stubbed reads that
    feed the rule-based regime classifier in macro_logic.classify_regime().
    """
    return {
        "cpi_headline": 3.1,           # FRED CPIAUCSL YoY (mock)
        "cpi_core":     3.3,           # FRED CPILFESL YoY (mock)
        "cpi_trend":    "sticky",      # one of: cooling | sticky | rising
        "growth":       "slowing",     # one of: expanding | slowing | contracting
        "as_of":        "MOCK · last print TBD",
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

# ── Layer 1 support — Growth Nowcast ──────────────────────────────────────────
def growth_nowcast() -> dict:
    """Forward-ish growth reads that flesh out the regime layer.

    - citi_surprise: Citi Economic Surprise Index — data vs. expectations
      (positive = beating). No clean free FRED series; proxy/vendor later.
    - ism_mfg / ism_services: ISM PMIs; <50 = contraction.
    - jobless_claims: initial claims (thousands) + trend (FRED ICSA).
    - copper_gold_ratio: growth-vs-fear gauge (yfinance HG=F / GC=F); series for trend.
    """
    return {
        "citi_surprise": -12.0,                              # vendor (mock); -ve = data missing
        "ism_mfg":      {"level": 48.7, "chg": -0.4},        # ISM mfg (mock)
        "ism_services": {"level": 51.3, "chg": -0.6},        # ISM services (mock)
        "jobless_claims": {"level": 233, "trend": "rising"},  # FRED ICSA, thousands (mock)
        "copper_gold_ratio": {
            "level": 0.00152,                                # HG=F / GC=F (mock)
            "series": [0.00161, 0.00159, 0.00157, 0.00156, 0.00154, 0.00153, 0.00152],
        },
    }


# ── Layer 2 support — Rates, Curve & Policy ───────────────────────────────────
def rates_curve_policy() -> dict:
    """The policy/rates dimension behind the real-yield leg.

    - slope_2s10s / slope_3m10y: curve slopes in pp; negative = inverted (FRED
      T10Y2Y / T10Y3M).
    - fed_funds: current target range (low/high) in %.
    - implied_cuts: market-implied easing — count and bps over a horizon
      (Fed funds futures later; mock now).
    - move_index: MOVE — the bond-market's VIX (rate vol). yfinance ^MOVE.
    """
    return {
        "slope_2s10s": {"level": +0.34, "chg": +0.05},       # FRED T10Y2Y (mock)
        "slope_3m10y": {"level": -0.18, "chg": +0.03},       # FRED T10Y3M (mock)
        "fed_funds":   {"low": 4.25, "high": 4.50},          # current target range
        "implied_cuts": {"count": 2, "bps": 50, "horizon": "by Dec 2026"},  # futures (mock)
        "move_index":  {"level": 98.0, "chg": +3.5},         # yfinance ^MOVE (mock)
    }


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


# ── Layer 3 support — Liquidity & Credit ──────────────────────────────────────
def liquidity_credit() -> dict:
    """The plumbing behind financial conditions.

    - hy_oas / ig_oas: high-yield & investment-grade OAS in pp (FRED BAMLH0A0HYM2 /
      BAMLC0A0CM).
    - net_liquidity: Fed balance sheet − RRP − TGA, in $T, with trend + series
      (FRED WALCL − RRPONTSYD − WTREGEN).
    - bank_reserves: reserve balances in $T (FRED WRESBAL).
    """
    return {
        "hy_oas":  {"level": 3.20, "chg": +0.10},            # FRED BAMLH0A0HYM2 (mock)
        "ig_oas":  {"level": 0.92, "chg": +0.03},            # FRED BAMLC0A0CM (mock)
        "net_liquidity": {
            "level": 5.92, "trend": "draining",              # $T (mock)
            "series": [6.18, 6.12, 6.07, 6.02, 5.99, 5.95, 5.92],
        },
        "bank_reserves": {"level": 3.21, "trend": "falling"},  # $T (mock)
    }


# ── Cross-asset / FX views ────────────────────────────────────────────────────
def fx_panel() -> dict:
    """Global liquidity / carry lens for a macro book. All MOCK.
    yfinance: DX-Y.NYB, JPY=X, EURUSD=X, CNH=X; EM FX via vendor / ETF proxy.
    """
    return {
        "dxy":     {"level": 104.8,  "chg": +0.30},
        "usdjpy":  {"level": 157.20, "chg": +0.45},
        "eurusd":  {"level": 1.0720, "chg": -0.25},
        "usdcnh":  {"level": 7.265,  "chg": +0.12},
        "em_fx":   {"level": 41.8,   "chg": -0.40},          # MSCI EM FX proxy (mock)
    }


def cross_asset() -> list:
    """One-glance cross-asset positioning band. Each row carries multi-timeframe
    % changes (1D/1W/1M/YTD) and a short spark series. All MOCK.
    yfinance: ^GSPC, ^IXIC, ^RUT, GC=F, CL=F, DX-Y.NYB, ^TNX, BTC-USD.
    """
    def row(name, level, d1, d1w, d1m, ytd, spark):
        return {"name": name, "level": level, "d1": d1, "d1w": d1w,
                "d1m": d1m, "ytd": ytd, "spark": spark}
    return [
        row("S&P 500",  7433.55, +1.08, +1.9, +3.4, +12.6, [7180, 7240, 7300, 7350, 7390, 7410, 7433]),
        row("Nasdaq",  24210.0,  +1.32, +2.4, +4.1, +16.2, [23200, 23450, 23700, 23900, 24050, 24150, 24210]),
        row("Russell", 3002.39,  -0.26, +0.4, +1.1,  +3.8, [2960, 2975, 2988, 2995, 3008, 3006, 3002]),
        row("Gold",    4038.20,  -0.99, -1.4, +2.6,  +18.0, [4080, 4072, 4060, 4055, 4048, 4044, 4038]),
        row("Oil WTI",   70.94,  +2.47, +3.1, -2.2,  -4.5, [66.1, 67.0, 68.4, 69.1, 69.8, 70.2, 70.94]),
        row("DXY",      104.80,  +0.30, +0.6, -0.8,  +1.2, [103.9, 104.1, 104.3, 104.5, 104.6, 104.7, 104.8]),
        row("10Y UST",    4.376, +0.09, +0.12, +0.18, +0.35, [4.05, 4.10, 4.18, 4.26, 4.31, 4.35, 4.376]),
        row("Bitcoin", 92850.0,  +0.85, +4.2, +6.8, +22.4, [86000, 87500, 89000, 90500, 91800, 92400, 92850]),
    ]


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
