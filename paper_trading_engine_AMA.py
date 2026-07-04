"""
Paper Trading Engine — OTP2.0 AMA (AlphaMind Adjusted)
=======================================================
Identical to paper_trading_engine.py with two additions recommended by AlphaMind:

  1. VIX Term Structure Filter (^VIX3M / ^VIX ratio, 3-day MA)
     Reload is only permitted when the term structure is normal (ratio >= 1.0),
     i.e. longer-dated vol > short-dated vol. Prevents reloading during acute
     stress periods like the July 2022 false recovery.

  2. Minimum Dwell Time (20 days post-trim)
     After any trim, a 20-day dwell timer starts. Reload is blocked until both
     the existing cooldown AND the dwell have elapsed. The two run in parallel —
     dwell starts from the trim date, not the cooldown expiry. This prevents
     thrashing in oscillating regimes (e.g. the Feb and Jul 2022 whipsaws).

All other logic is identical to the original engine.

State files: paper_state_AMA.json / paper_ledger_AMA.csv
"""

import json
import os
import time
import numpy as np
import pandas as pd

from strategy_deep_test import download, download_tbill, build_market_features
from strategy_selection_v2 import DEFENSIVE_OT2_CONFIG

LIVE_TICKERS    = ["GE", "GS", "GOOGL", "AVGO", "IBM", "JPM", "JNJ"]
CFG             = DEFENSIVE_OT2_CONFIG
LEDGER_PATH     = "paper_ledger_AMA.csv"
STATE_PATH      = "paper_state_AMA.json"
START_NAV       = 10_000.0
SLIPPAGE_FEE_RATE = 0.001

# ── AMA additions ──────────────────────────────────────────────────────────────
DWELL_DAYS      = 20    # minimum calendar days from trim before reload allowed
VIX3M_SMOOTH    = 3     # days for rolling MA on VIX3M/VIX ratio


def build_market_features_AMA(gspc, vix, vix3m):
    """
    Extend build_market_features() with VIX term structure columns.
    vix3m: raw yfinance history DataFrame for ^VIX3M.
    """
    df = build_market_features(gspc, vix)

    vix3m_close = vix3m["Close"].squeeze()
    # Strip timezone if present
    if hasattr(vix3m_close.index, "tz") and vix3m_close.index.tz is not None:
        vix3m_close.index = vix3m_close.index.tz_localize(None)

    vix3m_aligned = vix3m_close.reindex(df.index).ffill()
    df["vix3m"] = vix3m_aligned
    # Ratio > 1.0 = normal (long vol > short vol); < 1.0 = inverted (stress)
    df["vix3m_vix_ratio"]     = df["vix3m"] / df["vix"]
    df["vix3m_vix_ratio_ma3"] = df["vix3m_vix_ratio"].rolling(VIX3M_SMOOTH).mean()
    return df


def _step(row, prev, state, cfg, lr, cash_ret, px_today, cash_ret_simple, today):
    """
    One-day OTP2.0 AMA state advance.

    Identical to paper_trading_engine._step() except:
      - Records trim_date when a trim fires
      - Adds dwell_ok gate (20 days since trim) to reload conditions
      - Adds term_ok gate (VIX3M/VIX ratio MA >= 1.0) to reload conditions
    """
    c = cfg
    inv             = state["invested"]
    cooldown        = state["cooldown"]
    consec_vix_fall = state["consec_vix_fall"]
    consec_rvol_fall= state["consec_rvol_fall"]

    rvol       = max(row["rvol20"],  1e-6)
    rvol_long  = max(row["rvol252"], 1e-6)
    vol_target_inv = min(0.95, c["vol_target"] / rvol)
    vol_scale  = min(2.5, rvol / rvol_long)

    above_sma  = row["close"] > row["sma200"]
    pos_mom    = row["momentum"] > 0
    if not above_sma and not pos_mom:
        trend_scale = 1.5
    elif above_sma and pos_mom:
        trend_scale = 0.7
    else:
        trend_scale = 1.0

    bs = row["breadth_score"]
    vix_l2_thresh = c["vix_l2"]
    if bs <= -2:
        vix_l1_thresh   = c["vix_l1"] - 2
        vix_l2_thresh   = c["vix_l2"] - 2
        breadth_trim_mul = 1.4
    elif bs >= 2:
        vix_l1_thresh   = c["vix_l1"] + 3
        breadth_trim_mul = 0.6
    else:
        vix_l1_thresh   = c["vix_l1"]
        breadth_trim_mul = 1.0

    vix_above_ma  = row["vix"] > row["vix_ma5"]
    vix_l1_signal = row["vix"] > vix_l1_thresh and vix_above_ma
    vix_l2_signal = row["vix"] > vix_l2_thresh and vix_above_ma

    trim = 0.0
    if cooldown == 0:
        scale = vol_scale * trend_scale * breadth_trim_mul
        if vix_l2_signal:
            trim = c["trim_l2_base"] * scale
        elif vix_l1_signal:
            trim = c["trim_l1_base"] * scale

    if trim > 0:
        inv = max(c["floor"], inv - trim)
        cooldown = c["cooldown_days"]
        # ── AMA: record trim date for dwell timer ─────────────────────────────
        state["trim_date"] = str(today.date())

    consec_vix_fall  = consec_vix_fall  + 1 if row["vix"]   < prev["vix"]   else 0
    consec_rvol_fall = consec_rvol_fall + 1 if row["rvol20"] < prev["rvol20"] else 0

    above_sma50   = row["close"] > row["sma50"]
    speed_needed  = c["reload_min_days"] if above_sma50 else c["reload_min_days"] + 2
    vix_ma20_ok   = row["vix"] <= row["vix_ma20"] * 1.02
    above_sma200  = row["close"] > row["sma200"]

    # ── AMA Gate 1: dwell time ────────────────────────────────────────────────
    dwell_ok = True
    trim_date_str = state.get("trim_date")
    if trim_date_str:
        days_since_trim = (today - pd.Timestamp(trim_date_str)).days
        dwell_ok = days_since_trim >= DWELL_DAYS

    # ── AMA Gate 2: VIX term structure ────────────────────────────────────────
    ratio_ma3 = row.get("vix3m_vix_ratio_ma3") if hasattr(row, "get") else (
        row["vix3m_vix_ratio_ma3"] if "vix3m_vix_ratio_ma3" in row.index else np.nan
    )
    ratio_ma3 = float(ratio_ma3) if ratio_ma3 is not None else np.nan
    # If NaN (insufficient early data), don't block — fall back to permissive
    term_ok = np.isnan(ratio_ma3) or (ratio_ma3 >= 1.0)

    base_signal = (
        consec_vix_fall  >= speed_needed and
        consec_rvol_fall >= speed_needed and
        vix_ma20_ok and
        above_sma200 and
        inv < 0.90 and
        cooldown == 0 and
        dwell_ok and       # AMA addition
        term_ok            # AMA addition
    )

    if base_signal:
        inv = min(0.95, inv + c["reload_size"])
        # Clear dwell timer on successful reload
        state["trim_date"] = None

    if trim == 0 and not base_signal:
        if abs(inv - vol_target_inv) > 0.03:
            inv = 0.6 * inv + 0.4 * vol_target_inv
        inv = max(c["floor"], inv)

    if cooldown > 0:
        cooldown -= 1

    # ── Per-stock bookkeeping (identical to original) ─────────────────────────
    shares       = state["shares"]
    entry_prices = state["entry_prices"]

    stock_value_pre = sum(shares[t] * px_today[t] for t in shares)
    cash_dollars    = state["cash_dollars"] * (1.0 + cash_ret_simple)
    total_pre       = stock_value_pre + cash_dollars

    target_stock  = inv * total_pre
    traded_dollars = abs(target_stock - stock_value_pre)
    cost          = traded_dollars * SLIPPAGE_FEE_RATE
    total         = total_pre - cost
    target_stock  = inv * total

    if stock_value_pre > 1e-9:
        factor = target_stock / stock_value_pre
    else:
        factor = 0.0

    for t in shares:
        old_sh = shares[t]
        new_sh = old_sh * factor
        if new_sh > old_sh:
            bought = new_sh - old_sh
            entry_prices[t] = (old_sh * entry_prices[t] + bought * px_today[t]) / new_sh
        shares[t] = new_sh

    cash_dollars = total - target_stock

    state["invested"]        = inv
    state["cooldown"]        = cooldown
    state["consec_vix_fall"] = consec_vix_fall
    state["consec_rvol_fall"]= consec_rvol_fall
    state["shares"]          = shares
    state["entry_prices"]    = entry_prices
    state["invested_dollars"]= target_stock
    state["cash_dollars"]    = cash_dollars
    state["nav"]             = total
    state["trading_cost"]    = state.get("trading_cost", 0.0) + cost
    return state


def main():
    t0 = time.time()

    print("Downloading market + timing data (AMA)...")
    gspc  = download("^GSPC")
    vix   = download("^VIX")
    vix3m = download("^VIX3M")
    tbill_raw, tbill_src = download_tbill()
    print(f"  T-bill source: {tbill_src}")

    print(f"Downloading Live cohort stocks: {', '.join(LIVE_TICKERS)}")
    closes = {}
    for tkr in LIVE_TICKERS:
        df = download(tkr)
        closes[tkr] = df["Close"].squeeze()

    market_df = build_market_features_AMA(gspc, vix, vix3m)

    prices = pd.DataFrame({t: closes[t] for t in LIVE_TICKERS})
    logret = np.log(prices / prices.shift(1))

    common_index = market_df.index
    for tkr in LIVE_TICKERS:
        common_index = common_index.intersection(logret[tkr].dropna().index)
    market_df = market_df.loc[common_index]
    logret    = logret.loc[common_index]
    prices    = prices.loc[common_index]

    blended    = logret.mean(axis=1)
    cash_daily = tbill_raw.reindex(common_index).ffill().bfill() / 252

    print(f"Common index: {common_index[0].date()} to {common_index[-1].date()} "
          f"({len(common_index):,} trading days)")

    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            state = json.load(f)

        # Per-stock v2 migration (same as original)
        if not state.get("per_stock_v2"):
            lp = state.get("last_prices", {})
            sh = state.get("shares", {})
            stock_val = sum(sh[t] * lp[t] for t in sh) if (sh and lp) else 0.0
            target    = state.get("invested_dollars", stock_val)
            if stock_val > 1e-9:
                f_rebase = target / stock_val
                for t in sh:
                    sh[t] = sh[t] * f_rebase
                state["shares"] = sh
            state["per_stock_v2"] = True
            with open(STATE_PATH, "w") as f:
                json.dump(state, f, indent=2)

        last_date = pd.Timestamp(state["last_date"])

    else:
        seed_pos  = len(common_index) - 1
        seed_date = common_index[seed_pos]
        inv0      = min(0.95, CFG["vol_target"] / market_df["rvol20"].iloc[seed_pos])
        seed_cost = START_NAV * inv0 * SLIPPAGE_FEE_RATE
        nav0      = START_NAV - seed_cost
        invested_dollars0  = nav0 * inv0
        per_ticker_dollars = invested_dollars0 / len(LIVE_TICKERS)
        entry_prices = {t: float(prices[t].iloc[seed_pos]) * (1 + SLIPPAGE_FEE_RATE) for t in LIVE_TICKERS}
        shares       = {t: per_ticker_dollars / entry_prices[t] for t in LIVE_TICKERS}

        state = dict(
            invested          = inv0,
            cooldown          = 0,
            consec_vix_fall   = 0,
            consec_rvol_fall  = 0,
            invested_dollars  = invested_dollars0,
            cash_dollars      = nav0 * (1 - inv0),
            nav               = nav0,
            trading_cost      = seed_cost,
            last_date         = str(seed_date.date()),
            entry_prices      = entry_prices,
            shares            = shares,
            last_prices       = entry_prices.copy(),
            per_stock_v2      = True,
            # AMA additions
            trim_date         = None,
        )
        rows = [{
            "date":           seed_date.date().isoformat(),
            "nav":            nav0,
            "invested_pct":   inv0 * 100,
            "daily_log_ret":  0.0,
            "regime":         "Defensive-AMA (CAPE frothy, 38.0)",
            "holdings":       ", ".join(LIVE_TICKERS),
            "stopped_dwell":  False,
            "stopped_term":   False,
        }]
        pd.DataFrame(rows).to_csv(LEDGER_PATH, index=False)
        with open(STATE_PATH, "w") as f:
            json.dump(state, f, indent=2)
        print(f"Seeded AMA ledger at {seed_date.date()} "
              f"(NAV={nav0:.2f}, invested={inv0*100:.1f}%, cost={seed_cost:.2f})")
        print(f"\nRuntime: {time.time()-t0:.1f}s")
        return

    last_pos = common_index.get_indexer([last_date])[0]
    if last_pos < 0 or last_pos >= len(common_index) - 1:
        print("No new trading days since last update. Ledger unchanged.")
        print(f"\nRuntime: {time.time()-t0:.1f}s")
        return

    new_rows = []
    for i in range(last_pos + 1, len(common_index)):
        row, prev  = market_df.iloc[i], market_df.iloc[i - 1]
        date       = common_index[i]
        prev_nav   = state["nav"]
        px_today   = {t: float(prices[t].iloc[i]) for t in LIVE_TICKERS}

        # Capture AMA gate states before step for ledger
        trim_date_str = state.get("trim_date")
        dwell_blocked = False
        if trim_date_str:
            days_since = (date - pd.Timestamp(trim_date_str)).days
            dwell_blocked = days_since < DWELL_DAYS
        ratio_ma3 = float(row.get("vix3m_vix_ratio_ma3", np.nan)) if hasattr(row, "get") else np.nan
        term_blocked = not (np.isnan(ratio_ma3) or ratio_ma3 >= 1.0)

        state = _step(row, prev, state, CFG, blended.iloc[i],
                      cash_daily.iloc[i], px_today, float(cash_daily.iloc[i]),
                      today=date)

        daily_log_ret = np.log(state["nav"] / prev_nav)
        new_rows.append({
            "date":          date.date().isoformat(),
            "nav":           state["nav"],
            "invested_pct":  state["invested"] * 100,
            "daily_log_ret": daily_log_ret,
            "regime":        "Defensive-AMA (CAPE frothy, 38.0)",
            "holdings":      ", ".join(LIVE_TICKERS),
            "stopped_dwell": dwell_blocked,
            "stopped_term":  term_blocked,
        })
        state["last_date"] = str(date.date())

    state["last_prices"] = {t: float(prices[t].iloc[-1]) for t in LIVE_TICKERS}

    existing = pd.read_csv(LEDGER_PATH)
    updated  = pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True)
    updated.to_csv(LEDGER_PATH, index=False)

    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

    dwell_str = f" [DWELL ACTIVE since {state.get('trim_date')}]" if state.get("trim_date") else ""
    print(f"Appended {len(new_rows)} day(s). NAV={state['nav']:.3f}, "
          f"invested={state['invested']*100:.1f}%{dwell_str}, date={state['last_date']}")
    print(f"\nRuntime: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
