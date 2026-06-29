"""
Macro Dashboard — classification logic (FIRST PASS).

Pure, opinionated rule logic kept deliberately separate from the view and the
data layer:
  - No Streamlit / HTML imports here — this module is import-safe and unit-testable.
  - The view (pages/3_Macro_Dashboard.py) stays "dumb": every classifier returns a
    small dict {label, color, tags, note, ...} that the view just renders.

IMPORTANT — these rules are OPINIONATED and STYLE-DEPENDENT. The Layer-2 hierarchy
below is calibrated to a macro-positional, stagflation-leaning book. It is a lens,
not objective fact. Thresholds are v1 placeholders meant to be refined in review;
they are centralized as named constants so tuning is a one-line change.
"""

# ── Tunable v1 constants (refine in review) ───────────────────────────────────

# Minimum nominal-yield move (pp) over the lookback to count as "rising".
NOMINAL_RISE_EPS = 0.02

# If the two legs' absolute moves are within this band (pp) of each other, we
# don't crown a dominant mover — we call it Mixed/Neutral instead.
LEG_DOMINANCE_EPS = 0.02

# Palette mirrors app.py's accent colors so the view stays on-theme.
COL_INFLATION = "#c08a2d"   # gold — inflation-scare leg
COL_GROWTH    = "#c14a32"   # red  — growth/tightening shock
COL_NEUTRAL   = "#6b7a8a"   # slate — mixed / no clear signal
COL_RISK_ON   = "#2f8f5b"   # green
COL_RISK_OFF  = "#c14a32"   # red
COL_STAG      = "#b5642d"   # burnt orange — stagflation


# ── Layer 2 — The Hinge classifier (centerpiece) ──────────────────────────────
def classify_hinge(hinge: dict, lookback_days: int | None = None) -> dict:
    """Classify *why* the 10Y nominal yield is moving.

    Rule (v1):
      * nominal rising AND breakeven leg is the dominant mover -> "Inflation Scare"
        (implications: duration-negative, gold-positive, risk-ambiguous)
      * nominal rising AND real leg is the dominant mover -> "Growth/Tightening Shock"
        (implications: negative for long-duration assets broadly — equities,
         credit, growth factor — simultaneously)
      * otherwise (nominal not clearly rising, or legs too close to call)
        -> "Mixed/Neutral"

    "Dominant mover" (v1) = whichever leg moved more in ABSOLUTE terms over the
    lookback window, provided the gap exceeds LEG_DOMINANCE_EPS.

    Returns a dict the view renders directly:
        {label, color, tags, note, dominant, nominal_dir, legs}
    """
    nominal_chg   = hinge["nominal"]["chg"]
    real_chg      = hinge["real"]["chg"]
    breakeven_chg = hinge["breakeven"]["chg"]
    lb = lookback_days if lookback_days is not None else hinge.get("lookback_days")

    nominal_rising = nominal_chg > NOMINAL_RISE_EPS
    real_abs = abs(real_chg)
    be_abs   = abs(breakeven_chg)
    gap = abs(be_abs - real_abs)

    legs = {
        "real":      {"chg": real_chg,      "abs": real_abs},
        "breakeven": {"chg": breakeven_chg, "abs": be_abs},
    }
    base = {
        "nominal_dir": "rising" if nominal_rising else ("falling" if nominal_chg < -NOMINAL_RISE_EPS else "flat"),
        "lookback_days": lb,
        "legs": legs,
    }

    # Not a clear up-move in nominal, or the two legs are too close to separate.
    if not nominal_rising or gap <= LEG_DOMINANCE_EPS:
        reason = ("nominal not clearly rising" if not nominal_rising
                  else "real and breakeven moved by similar amounts")
        return {
            **base,
            "label": "Mixed / Neutral",
            "color": COL_NEUTRAL,
            "dominant": None,
            "tags": ["no dominant leg"],
            "note": f"No clean read — {reason}.",
        }

    if be_abs > real_abs:
        return {
            **base,
            "label": "Inflation Scare",
            "color": COL_INFLATION,
            "dominant": "breakeven",
            "tags": ["duration-negative", "gold-positive", "risk-ambiguous"],
            "note": "Nominal up, led by the breakeven (inflation-expectations) leg.",
        }

    return {
        **base,
        "label": "Growth / Tightening Shock",
        "color": COL_GROWTH,
        "dominant": "real",
        "tags": ["equities-negative", "credit-negative", "growth-factor-negative"],
        "note": "Nominal up, led by the real-yield (growth/policy-tightening) leg.",
    }


# ── Layer 1 — Regime classifier (slow, rule-based stub) ───────────────────────
def classify_regime(layer1: dict) -> dict:
    """Coarse rule-based regime badge from CPI trend + growth direction.

    v1 stub — thresholds/labels are PLACEHOLDER and to be refined in review.

        inflation sticky/rising + growth slowing/contracting -> Stagflation
        inflation cooling        + growth expanding/slowing   -> Soft Landing
        inflation cooling        + growth contracting          -> Disinflation
        otherwise                                              -> Mixed / Transitional
    """
    cpi_trend = layer1.get("cpi_trend", "sticky")   # cooling | sticky | rising
    growth    = layer1.get("growth", "slowing")     # expanding | slowing | contracting

    hot_inflation  = cpi_trend in ("sticky", "rising")
    weak_growth    = growth in ("slowing", "contracting")

    if hot_inflation and weak_growth:
        label, color, note = "Stagflation", COL_STAG, "Sticky/rising inflation alongside slowing growth."
    elif cpi_trend == "cooling" and growth in ("expanding", "slowing"):
        label, color, note = "Soft Landing", COL_RISK_ON, "Inflation cooling while growth holds up."
    elif cpi_trend == "cooling" and growth == "contracting":
        label, color, note = "Disinflation", COL_NEUTRAL, "Inflation cooling as growth rolls over."
    else:
        label, color, note = "Mixed / Transitional", COL_NEUTRAL, "No clean regime read on current inputs."

    return {
        "label": label,
        "color": color,
        "note": note,
        "cpi_headline": layer1.get("cpi_headline"),
        "cpi_core": layer1.get("cpi_core"),
        "as_of": layer1.get("as_of"),
    }


# ── Layer 3 — Vol term-structure flag ─────────────────────────────────────────
def vol_curve_state(front: float, back: float) -> dict:
    """Contango vs. backwardation flag for the vol term structure.

    front < back -> Contango (typical, risk-on tilt)
    front > back -> Backwardation (stress / risk-off tripwire)

    Directional framing only — no hit-rate or correlation number is asserted.
    """
    if front is None or back is None:
        return {"label": "—", "color": COL_NEUTRAL, "note": "No data.", "spread": None}

    spread = back - front
    if spread > 0:
        return {
            "label": "Contango",
            "color": COL_RISK_ON,
            "note": "Front below back month — calm / risk-on tilt.",
            "spread": spread,
        }
    if spread < 0:
        return {
            "label": "Backwardation",
            "color": COL_RISK_OFF,
            "note": "Front above back month — stress / risk-off tripwire.",
            "spread": spread,
        }
    return {"label": "Flat", "color": COL_NEUTRAL, "note": "Curve roughly flat.", "spread": 0.0}
