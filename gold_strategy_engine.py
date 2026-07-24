"""
Gold Strategy Engine  —  TIPS direction × DXY × 5% trailing stop
=================================================================
Advances the paper-trading simulation of the gold timing strategy
validated in Phases 1-5 of backtesting (Sharpe 1.165, Sortino 1.075,
MaxDD -9.78% over 2003-2026).

Instrument : GLD ETF (SPDR Gold Shares)
Signals    : TIPS 10Y real yield falling (< 60-day SMA)  AND
             DXY below its 150-day SMA
Stop       : 5% trailing stop on high-water mark while in position

Run daily after US market close (same scheduled task as OTP2.0 engine).
State persisted in gold_state.json; ledger appended to gold_ledger.csv.
"""

import json
import os
import time

import numpy as np
import pandas as pd
import yfinance as yf

from event_log import log_event

LEDGER_PATH    = "gold_ledger.csv"
STATE_PATH     = "gold_state.json"
START_NAV      = 10000.0
SLIPPAGE_FEE   = 0.001          # 10 bps round-trip cost on each trade
STOP_PCT       = 0.05           # 5% trailing stop from HWM
TIPS_SMA_WIN   = 60             # TIPS rolling window (trading days)
DXY_SMA_WIN    = 150            # DXY rolling window (trading days)

# ---------------------------------------------------------------------------
# DATA
# ---------------------------------------------------------------------------

def _fetch_yf(ticker, start="2003-01-01"):
    df = yf.download(ticker, start=start, progress=False, auto_adjust=False)
    return df["Close"].squeeze().dropna()


def _fetch_fred(series):
    try:
        import pandas_datareader.data as web
        from datetime import datetime, timedelta
        end   = datetime.today()
        start = end - timedelta(days=365 * 5)
        df = web.DataReader(series, "fred", start, end)
        return df.iloc[:, 0].dropna()
    except Exception as e:
        print(f"  [warn] FRED {series} failed: {e}")
        return pd.Series(dtype=float)


# ---------------------------------------------------------------------------
# SIGNAL
# ---------------------------------------------------------------------------

def compute_signals(gld, dxy, tips, tbill):
    """
    Returns a DataFrame aligned to GLD trading days with columns:
      tips_val, tips_sma, tips_falling, dxy_val, dxy_sma, dxy_weak,
      regime_on, gld_log_ret, cash_daily
    All series lag-1 safe: signal on row i is computed from close prices
    up to and including row i; it governs the position on row i+1.
    """
    tips_ffill  = tips.reindex(gld.index, method="ffill")
    dxy_reindex = dxy.reindex(gld.index, method="ffill")
    tbill_ff    = tbill.reindex(gld.index, method="ffill").bfill()

    tips_sma    = tips_ffill.rolling(TIPS_SMA_WIN, min_periods=TIPS_SMA_WIN // 2).mean()
    dxy_sma     = dxy_reindex.rolling(DXY_SMA_WIN, min_periods=DXY_SMA_WIN // 2).mean()

    tips_falling = (tips_ffill < tips_sma).astype(int)
    dxy_weak     = (dxy_reindex < dxy_sma).astype(int)
    regime_on    = (tips_falling & dxy_weak).astype(int)

    gld_log_ret = np.log(gld / gld.shift(1))
    cash_daily  = np.log(1 + tbill_ff / 100) / 252.0

    return pd.DataFrame({
        "gld":          gld,
        "gld_log_ret":  gld_log_ret,
        "tips_val":     tips_ffill,
        "tips_sma":     tips_sma,
        "tips_falling": tips_falling,
        "dxy_val":      dxy_reindex,
        "dxy_sma":      dxy_sma,
        "dxy_weak":     dxy_weak,
        "regime_on":    regime_on,
        "cash_daily":   cash_daily,
    }).dropna(subset=["gld_log_ret"])


# ---------------------------------------------------------------------------
# DAILY STEP
# ---------------------------------------------------------------------------

def _step(row, state):
    """
    Advance state by one trading day.
    row    : Series from the signals DataFrame (already on day t)
    state  : dict (mutated in place, returned)

    Position decision for day t uses signals from day t-1 (enforced by
    the caller iterating from last_pos+1 and reading regime_on[i-1]).
    This function receives regime_on already shifted — caller passes
    prev_regime for the position decision.
    """
    gld_price  = row["gld"]
    log_ret    = row["gld_log_ret"]
    cash_ret   = row["cash_daily"]

    in_pos     = state["in_position"]
    stop_act   = state["stop_active"]
    hwm        = state.get("hwm") or np.nan
    stop_fired = False

    if stop_act:
        # Remain in cash; wait for regime to reset (turn OFF) then clear stop
        if not row["prev_regime_on"]:      # regime signal is now OFF — stop cleared
            state["stop_active"] = False
        # Earn cash return
        state["cash_dollars"] *= np.exp(cash_ret)
        state["nav"] = state["cash_dollars"]

    elif not in_pos:
        # Out of position — earn cash; enter if regime_on (from prev day)
        state["cash_dollars"] *= np.exp(cash_ret)

        if row["prev_regime_on"]:
            # Enter GLD: buy at today's price with slippage
            entry_price = gld_price * (1 + SLIPPAGE_FEE)
            cost        = state["cash_dollars"] * SLIPPAGE_FEE
            state["cash_dollars"] -= cost
            state["trading_cost"] = state.get("trading_cost", 0.0) + cost
            shares = state["cash_dollars"] / entry_price
            state["gld_shares"]   = shares
            state["entry_price"]  = entry_price
            state["entry_date"]   = str(row.name.date())
            state["cash_dollars"] = 0.0
            state["in_position"]  = True
            state["hwm"]          = gld_price
            hwm = gld_price
            in_pos = True
            print(f"  -> ENTERED GLD @ {entry_price:.2f}  ({shares:.4f} shares)")
            log_event("Gold", "entry", f"Entered GLD @ ${entry_price:.2f}",
                      date=str(row.name.date()), tickers=["GLD"])

        state["nav"] = state["cash_dollars"] + state.get("gld_shares", 0.0) * gld_price

    else:
        # In position — update HWM, check trailing stop
        hwm = max(hwm, gld_price)
        state["hwm"] = hwm

        if gld_price < hwm * (1 - STOP_PCT):
            # Stop triggered — sell GLD
            _sh = state["gld_shares"]; _ep = state.get("entry_price") or gld_price
            proceeds    = state["gld_shares"] * gld_price * (1 - SLIPPAGE_FEE)
            cost        = state["gld_shares"] * gld_price * SLIPPAGE_FEE
            state["trading_cost"] = state.get("trading_cost", 0.0) + cost
            state["cash_dollars"] = proceeds
            state["gld_shares"]   = 0.0
            state["in_position"]  = False
            state["stop_active"]  = True
            state["hwm"]          = None
            state["entry_price"]  = None
            state["entry_date"]   = None
            stop_fired = True
            print(f"  -> STOP FIRED @ {gld_price:.2f}  (HWM was {hwm:.2f}, "
                  f"drop {(gld_price/hwm-1)*100:.2f}%)")
            log_event("Gold", "stop", f"5% trailing stop @ ${gld_price:.2f}",
                      date=str(row.name.date()), realized_pnl=proceeds - _sh * _ep, tickers=["GLD"])
        elif not row["prev_regime_on"]:
            # Regime turned OFF — exit cleanly
            _sh = state["gld_shares"]; _ep = state.get("entry_price") or gld_price
            proceeds    = state["gld_shares"] * gld_price * (1 - SLIPPAGE_FEE)
            cost        = state["gld_shares"] * gld_price * SLIPPAGE_FEE
            state["trading_cost"] = state.get("trading_cost", 0.0) + cost
            state["cash_dollars"] = proceeds
            state["gld_shares"]   = 0.0
            state["in_position"]  = False
            state["hwm"]          = None
            state["entry_price"]  = None
            state["entry_date"]   = None
            print(f"  -> EXITED GLD (regime off) @ {gld_price:.2f}")
            log_event("Gold", "exit", f"Signal off — exited GLD @ ${gld_price:.2f}",
                      date=str(row.name.date()), realized_pnl=proceeds - _sh * _ep, tickers=["GLD"])

        state["nav"] = state["cash_dollars"] + state.get("gld_shares", 0.0) * gld_price

    state["last_gld_price"]      = float(gld_price)
    state["signal_tips_falling"] = bool(row["tips_falling"])
    state["signal_dxy_weak"]     = bool(row["dxy_weak"])
    state["signal_regime_on"]    = bool(row["regime_on"])

    return state, stop_fired


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    t0 = time.time()

    print("Downloading GLD...")
    gld = _fetch_yf("GLD")
    print(f"  GLD: {len(gld)} rows  {gld.index.min().date()} -> {gld.index.max().date()}")

    print("Downloading DXY...")
    dxy = _fetch_yf("DX-Y.NYB")

    print("Fetching TIPS 10Y real yield (FRED DFII10)...")
    tips = _fetch_fred("DFII10")
    if tips.empty:
        print("  FRED unavailable — cannot compute TIPS signal. Aborting.")
        return

    print("Fetching T-bill 3M (FRED DGS3MO)...")
    tbill = _fetch_fred("DGS3MO")
    if tbill.empty:
        tbill = pd.Series(4.3, index=gld.index)   # fallback: approx current rate
        print("  Using fallback T-bill rate 4.3%")

    df = compute_signals(gld, dxy, tips, tbill)
    # Add prev_regime_on for step function (position decision uses prior day's signal)
    df["prev_regime_on"] = df["regime_on"].shift(1).fillna(0).astype(int)

    print(f"Aligned: {df.index.min().date()} -> {df.index.max().date()}  "
          f"({len(df)} trading days)")

    # ── Seed or load state ──────────────────────────────────────────────────
    if not os.path.exists(STATE_PATH):
        seed_idx  = len(df) - 1
        seed_date = df.index[seed_idx]
        seed_row  = df.iloc[seed_idx]

        in_pos = bool(seed_row["prev_regime_on"])   # use yesterday's signal on seed day
        if in_pos:
            entry_price = float(seed_row["gld"]) * (1 + SLIPPAGE_FEE)
            cost        = START_NAV * SLIPPAGE_FEE
            nav0        = START_NAV - cost
            shares      = nav0 / entry_price
            state = dict(
                in_position=True, stop_active=False,
                hwm=float(seed_row["gld"]),
                gld_shares=shares, entry_price=entry_price,
                entry_date=str(seed_date.date()),
                cash_dollars=0.0, nav=nav0,
                trading_cost=cost,
                last_date=str(seed_date.date()),
                last_gld_price=float(seed_row["gld"]),
                signal_tips_falling=bool(seed_row["tips_falling"]),
                signal_dxy_weak=bool(seed_row["dxy_weak"]),
                signal_regime_on=bool(seed_row["regime_on"]),
            )
            print(f"Seeded IN GLD @ {entry_price:.2f}  ({shares:.4f} sh)  "
                  f"NAV={nav0:.2f}")
        else:
            state = dict(
                in_position=False, stop_active=False,
                hwm=None, gld_shares=0.0,
                entry_price=None, entry_date=None,
                cash_dollars=START_NAV, nav=START_NAV,
                trading_cost=0.0,
                last_date=str(seed_date.date()),
                last_gld_price=float(seed_row["gld"]),
                signal_tips_falling=bool(seed_row["tips_falling"]),
                signal_dxy_weak=bool(seed_row["dxy_weak"]),
                signal_regime_on=bool(seed_row["regime_on"]),
            )
            print(f"Seeded IN CASH  NAV={START_NAV:.2f}  "
                  f"(regime OFF — TIPS falling={bool(seed_row['tips_falling'])}, "
                  f"DXY weak={bool(seed_row['dxy_weak'])})")

        first_row = {
            "date": str(seed_date.date()),
            "nav": state["nav"],
            "in_position": state["in_position"],
            "gld_price": float(seed_row["gld"]),
            "daily_log_ret": 0.0,
            "signal": "ON" if state["in_position"] else "OFF",
            "stop_fired": False,
            "trading_cost_cumul": state["trading_cost"],
        }
        pd.DataFrame([first_row]).to_csv(LEDGER_PATH, index=False)
        with open(STATE_PATH, "w") as f:
            json.dump(state, f, indent=2)
        print(f"Runtime: {time.time()-t0:.1f}s")
        return

    # ── Advance from last date ──────────────────────────────────────────────
    with open(STATE_PATH) as f:
        state = json.load(f)

    last_date = pd.Timestamp(state["last_date"])
    last_pos  = df.index.get_indexer([last_date])[0]

    if last_pos < 0 or last_pos >= len(df) - 1:
        print("No new trading days since last update. Ledger unchanged.")
        print(f"Runtime: {time.time()-t0:.1f}s")
        return

    new_rows = []
    for i in range(last_pos + 1, len(df)):
        row      = df.iloc[i]
        prev_nav = state["nav"]

        state, stop_fired = _step(row, state)
        daily_log_ret = np.log(state["nav"] / prev_nav) if prev_nav > 0 else 0.0

        sig_label = "ON" if state["signal_regime_on"] else (
            "STOP" if state["stop_active"] else "OFF"
        )
        new_rows.append({
            "date":              str(df.index[i].date()),
            "nav":               state["nav"],
            "in_position":       state["in_position"],
            "gld_price":         float(row["gld"]),
            "daily_log_ret":     daily_log_ret,
            "signal":            sig_label,
            "stop_fired":        stop_fired,
            "trading_cost_cumul": state.get("trading_cost", 0.0),
        })
        state["last_date"] = str(df.index[i].date())

    existing = pd.read_csv(LEDGER_PATH)
    updated  = pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True)
    updated.to_csv(LEDGER_PATH, index=False)

    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

    pos_str = "GLD" if state["in_position"] else ("STOP-WAIT" if state["stop_active"] else "CASH")
    print(f"Appended {len(new_rows)} day(s). NAV={state['nav']:.2f}  "
          f"Position={pos_str}  Date={state['last_date']}")
    print(f"Runtime: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
