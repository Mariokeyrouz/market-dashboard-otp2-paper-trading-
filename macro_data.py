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
