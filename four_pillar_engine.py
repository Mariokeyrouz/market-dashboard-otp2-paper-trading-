"""
Four-Pillar Engine — Gold + Sector Momentum (equal-weight) + FMTS (2-factor) + OTP2.0
==========================================================================================
Live daily advancement of the combination validated in
four_pillar_combination_backtest.py (Sharpe 1.139, MaxDD -9.1%, 2009-2026,
NW t=6.73) and four_pillar_band_rebalance_backtest.py (drift-band
rebalancing: ±5% band, 97% fewer trades than calendar rebalancing for
essentially the same Sharpe).

FOUR SLEEVES, 25% target each, EACH REPLICATING EXACTLY WHAT WAS BACKTESTED
-------------------------------------------------------------------------------
  Gold      R-dir+DXY signal + 5% trailing stop on GLD (dxy_gold_stopcheck.py's
            construction, Sharpe 1.165) — NOT the same as the standalone live
            Gold strategy (gold_strategy_engine.py), which uses a simpler
            binary AND-gate regime with no continuous DXY scalar. That
            strategy is validated on its own terms; this sleeve intentionally
            matches what four_pillar_combination_backtest.py actually tested.
  SectorEW  Top-3-of-9 sector ETFs by 12-1 relative momentum vs SPY, held via
            the REAL equal-weight sector ETFs (RSPT, RSPF, RSPG, RSPH, RSPN,
            RSPD, RSPS, RSPU, RSPM — confirmed survivorship-bias-free in
            sector_stockpick_diagnostic.py), monthly rebalance.
  FMTS      Momentum + Low-Vol 2-factor composite ONLY (fmts_backtest.py) —
            NOT the live FMTS's 4-factor composite, which includes untested
            Value/Quality legs (no historical fundamentals pipeline exists).
            Top-18, monthly rebalance, 9% trailing stop.
  OTP2.0    Base engine exactly (paper_trading_engine.py's _step, fixed
            7-stock cohort, DEFENSIVE_OT2_CONFIG) — NOT the AMA variant,
            which otp2_ama_backtest.py showed is statistically inert
            (t=-0.92) relative to base.

TOP-LEVEL REBALANCING — drift-band, not calendar
----------------------------------------------------
Checked daily (more responsive than the backtest's monthly check, which was
a data-granularity artifact, not part of the rule itself). A rebalance back
to 25/25/25/25 fires only when a sleeve's weight drifts beyond `BAND` (5%)
of its target — each sleeve's shares/cash are scaled by the same factor,
preserving its own internal invested/cash split.

State: four_pillar_state.json   Ledger: four_pillar_ledger.csv

This is PAPER-TESTING RESEARCH ONLY. Not a recommendation to trade real
money.

Usage:
  py four_pillar_engine.py
"""

import json
import os
import time

import numpy as np
import pandas as pd
import yfinance as yf

from strategy_deep_test import download_many, download_tbill, build_market_features
from strategy_selection_v2 import DEFENSIVE_OT2_CONFIG
import paper_trading_engine as pte
import fmts_backtest as fb
import momentum_experiments_daily as med
import rrg_data as rd
import sector_momentum_stockpick_backtest as smb
from gold_strategy_engine import _fetch_fred
from event_log import log_event

LEDGER_PATH = "four_pillar_ledger.csv"
STATE_PATH = "four_pillar_state.json"
START_NAV = 10_000.0
SLIPPAGE_RATE = 0.001

OTP2_TICKERS = ["GE", "GS", "GOOGL", "AVGO", "IBM", "JPM", "JNJ"]
OTP2_CFG = DEFENSIVE_OT2_CONFIG

GOLD_STOP_PCT = 0.05
DXY_SMA = 150
TIPS_SMA = 60

EW_TICKERS = {
    "XLK": "RSPT", "XLF": "RSPF", "XLE": "RSPG", "XLV": "RSPH", "XLI": "RSPN",
    "XLY": "RSPD", "XLP": "RSPS", "XLU": "RSPU", "XLB": "RSPM",
}
N_SECTORS = 3
SECTOR_LOOKBACK_M, SECTOR_SKIP_M = 12, 1

FMTS_N_HOLDINGS = 18
FMTS_STOP = 0.09

BAND = 0.05
SLEEVES = ["Gold", "SectorEW", "FMTS", "OTP2.0"]
TARGET_W = 0.25


# ─────────────────────────────────────────────────────────────────────────────
# 1. DATA
# ─────────────────────────────────────────────────────────────────────────────

def load_market_data():
    print("Downloading shared market data (GSPC, VIX, DXY, GLD, RSPx sector ETFs, OTP2.0 cohort)...")
    tickers = ["^GSPC", "^VIX", "GLD"] + OTP2_TICKERS + list(EW_TICKERS.values())
    raw = download_many(tickers)
    gspc, vix = raw["^GSPC"], raw["^VIX"]
    tbill_raw, tbill_src = download_tbill()
    print(f"  T-bill source: {tbill_src}")

    dxy = yf.download("DX-Y.NYB", start="2003-01-01", progress=False, auto_adjust=False)["Close"].squeeze()
    tips = _fetch_fred("DFII10")

    market_df = build_market_features(gspc, vix)
    prices = {t: raw[t]["Close"].squeeze() for t in tickers if t in raw and t not in ("^GSPC", "^VIX")}
    px = pd.DataFrame(prices)
    px.index = pd.to_datetime(px.index).tz_localize(None)

    common = market_df.index.intersection(px.index)
    market_df = market_df.loc[common]
    px = px.loc[common]
    cash_daily = tbill_raw.reindex(common).ffill().bfill() / 252

    dxy = dxy.reindex(common, method="ffill")
    tips = tips.reindex(common, method="ffill")
    tips_sma = tips.rolling(TIPS_SMA, min_periods=TIPS_SMA // 2).mean()
    dxy_sma = dxy.rolling(DXY_SMA, min_periods=DXY_SMA // 2).mean()
    tips_falling = (tips < tips_sma)
    dxy_scalar = pd.Series(np.where(dxy < dxy_sma, 1.0, 0.5), index=dxy.index)

    print(f"Common daily index: {common[0].date()} -> {common[-1].date()} ({len(common)} days)")
    return market_df, px, cash_daily, tips_falling, dxy_scalar


def load_fmts_universe():
    px = med.load_daily()
    spy_d = px["SPY"] if "SPY" in px.columns else None
    stocks_d = px.drop(columns=["SPY"], errors="ignore").dropna(axis=1, how="all")
    return stocks_d, spy_d


def load_sector_data():
    px_sec = rd.load_sector_prices(verbose=False)
    sectors = rd.SECTOR_CORE
    return px_sec[sectors], px_sec[rd.BENCHMARK]


# ─────────────────────────────────────────────────────────────────────────────
# 2. GOLD SLEEVE
# ─────────────────────────────────────────────────────────────────────────────

def gold_seed_state(gld_price):
    return dict(shares={"GLD": 0.0}, entry_prices={}, cash_dollars=0.0, nav=0.0,
                invested=0.0, hwm=None, stop_active=False,
                prev_tips_fall=False, prev_dxy_scalar=0.5, trading_cost=0.0)


def gold_step(state, gld_price, tips_fall_today, dxy_scalar_today, cash_ret_simple, slippage_rate):
    base = (1.0 if state["prev_tips_fall"] else 0.0) * state["prev_dxy_scalar"]
    stop_active = state["stop_active"]
    if stop_active and not tips_fall_today:
        stop_active = False

    shares = state["shares"]
    stock_value = shares.get("GLD", 0.0) * gld_price
    cash = state["cash_dollars"] * (1.0 + cash_ret_simple)
    nav_pre = stock_value + cash

    hwm = state.get("hwm")
    if stop_active or base < 0.01:
        target_inv = 0.0
        hwm = None
    else:
        hwm = gld_price if hwm is None else max(hwm, gld_price)
        if gld_price < hwm * (1 - GOLD_STOP_PCT):
            target_inv = 0.0
            stop_active = True
            hwm = None
        else:
            target_inv = base

    target_stock = target_inv * nav_pre
    traded = abs(target_stock - stock_value)
    cost = traded * slippage_rate
    nav = nav_pre - cost
    target_stock = target_inv * nav
    new_shares = target_stock / gld_price if gld_price > 0 else 0.0
    cash = nav - target_stock

    state.update(shares={"GLD": new_shares}, entry_prices={"GLD": gld_price} if new_shares > 0 else {},
                 cash_dollars=cash, nav=nav, invested=target_inv, hwm=hwm, stop_active=stop_active,
                 prev_tips_fall=bool(tips_fall_today), prev_dxy_scalar=float(dxy_scalar_today),
                 trading_cost=state.get("trading_cost", 0.0) + cost)
    return state


# ─────────────────────────────────────────────────────────────────────────────
# 3. SECTOR-EW SLEEVE
# ─────────────────────────────────────────────────────────────────────────────

def sectorew_seed_state():
    return dict(shares={}, entry_prices={}, cash_dollars=0.0, nav=0.0, trading_cost=0.0)


def sectorew_rebalance(state, top_sectors, px_today, slippage_rate):
    cols = [EW_TICKERS[s] for s in top_sectors if EW_TICKERS.get(s) in px_today]
    stock_value = sum(state["shares"].get(t, 0.0) * px_today.get(t, 0.0) for t in state["shares"])
    cash = state["cash_dollars"]
    nav = stock_value + cash
    target_stock = nav
    cost = abs(target_stock - stock_value) * slippage_rate
    nav_after = nav - cost
    target_stock = nav_after
    w = 1.0 / len(cols) if cols else 0.0
    entry_prices = {t: px_today[t] * (1 + slippage_rate) for t in cols}
    shares = {t: (target_stock * w) / entry_prices[t] for t in cols} if cols else {}
    cash_dollars = nav_after - sum(shares.get(t, 0.0) * px_today.get(t, 0.0) for t in shares)
    state.update(shares=shares, entry_prices=entry_prices, cash_dollars=cash_dollars, nav=nav_after,
                 trading_cost=state.get("trading_cost", 0.0) + cost)
    return state


def sectorew_step(state, px_today, cash_ret_simple):
    stock_value = sum(state["shares"].get(t, 0.0) * px_today.get(t, 0.0) for t in state["shares"])
    cash = state["cash_dollars"] * (1.0 + cash_ret_simple)
    state["nav"] = stock_value + cash
    state["cash_dollars"] = cash
    return state


# ─────────────────────────────────────────────────────────────────────────────
# 4. TOP-LEVEL SLEEVE VALUE / REBALANCE
# ─────────────────────────────────────────────────────────────────────────────

def sleeve_nav(name, sub):
    return float(sub.get("nav", 0.0))


def rescale_sleeve(sub, factor):
    """Scale every DOLLAR amount in a sleeve's state by `factor`, preserving
    its own internal invested/cash split. peak_nav (FMTS's trailing-stop
    high-water mark, in dollars) must scale too, or the next drawdown-from-
    peak check would compare a rescaled nav against a stale peak and misfire.
    hwm (Gold's) is a PRICE level, not a dollar amount — never scaled."""
    if "shares" in sub:
        sub["shares"] = {t: q * factor for t, q in sub["shares"].items()}
    if "cash_dollars" in sub:
        sub["cash_dollars"] = sub["cash_dollars"] * factor
    if "invested_dollars" in sub:
        sub["invested_dollars"] = sub["invested_dollars"] * factor
    if "peak_nav" in sub and sub["peak_nav"] is not None:
        sub["peak_nav"] = sub["peak_nav"] * factor
    sub["nav"] = sub.get("nav", 0.0) * factor
    return sub


# ─────────────────────────────────────────────────────────────────────────────
# 5. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    market_df, px, cash_daily, tips_falling, dxy_scalar = load_market_data()
    idx = market_df.index

    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            state = json.load(f)
        last_date = pd.Timestamp(state["last_date"])
        last_pos = idx.searchsorted(last_date, side="right") - 1
        if last_pos >= len(idx) - 1:
            print("No new trading days since last update. Ledger unchanged.")
            print(f"Runtime: {time.time()-t0:.1f}s")
            return
        start_pos = last_pos + 1
        seeding = False
    else:
        start_pos = len(idx) - 1
        seeding = True
        print("No existing state — seeding at the latest available trading day.")

    # ── sector momentum panel (for SectorEW monthly rebalance decisions) ──────
    sec_d, spy_sec_d = load_sector_data()
    sec_m = sec_d.resample("ME").last()
    spy_sec_m = spy_sec_d.resample("ME").last()
    sec_mom_m = smb.momentum_signal(sec_m, spy_sec_m, SECTOR_LOOKBACK_M, SECTOR_SKIP_M)

    fmts_stocks_d, fmts_spy_d = load_fmts_universe()

    def latest_top_sectors(as_of_date):
        avail = sec_mom_m.index[sec_mom_m.index <= as_of_date]
        if len(avail) == 0:
            return []
        row = sec_mom_m.loc[avail[-1]].dropna()
        return list(row.nlargest(N_SECTORS).index)

    def latest_fmts_composite(as_of_date):
        composite, _ = fb.compute_composite_weekly(fmts_stocks_d, fmts_spy_d)
        avail = composite.index[composite.index <= as_of_date]
        if len(avail) == 0:
            return pd.Series(dtype=float)
        return composite.loc[avail[-1]].dropna()

    # ── seed ────────────────────────────────────────────────────────────────
    if seeding:
        d0 = idx[start_pos]
        px0 = px.loc[d0].dropna().to_dict()

        gold = gold_seed_state(px0.get("GLD"))
        gold["cash_dollars"] = START_NAV / 4      # Gold seeds flat (invested=0.0) — cash is correct
        gold["nav"] = START_NAV / 4

        sectorew = sectorew_seed_state()
        sectorew["cash_dollars"] = START_NAV / 4  # fund BEFORE rebalance, or target_stock computes off a $0 base
        sectorew["nav"] = START_NAV / 4
        top_sec = latest_top_sectors(d0)
        sectorew = sectorew_rebalance(sectorew, top_sec, px0, SLIPPAGE_RATE)

        comp = latest_fmts_composite(d0)
        top_fmts = comp.nlargest(FMTS_N_HOLDINGS)
        fmts_holdings = (top_fmts / top_fmts.sum()).to_dict() if len(top_fmts) else {}
        fmts_px0 = fmts_stocks_d.loc[fmts_stocks_d.index <= d0].iloc[-1].dropna().to_dict()
        entry_prices = {t: fmts_px0[t] * (1 + SLIPPAGE_RATE) for t in fmts_holdings if t in fmts_px0}
        fmts_shares = {t: (START_NAV / 4 * w) / entry_prices[t] for t, w in fmts_holdings.items() if t in entry_prices}
        fmts = dict(nav=START_NAV / 4, peak_nav=START_NAV / 4, invested=1.0, stopped_out=False,
                    shares=fmts_shares, entry_prices=entry_prices,
                    cash_dollars=(START_NAV / 4) - sum(fmts_shares.get(t, 0) * fmts_px0.get(t, 0) for t in fmts_shares),
                    trading_cost=0.0)

        otp2_inv0 = min(0.95, OTP2_CFG["vol_target"] / market_df["rvol20"].iloc[start_pos])
        otp2_entry = {t: px0[t] * (1 + SLIPPAGE_RATE) for t in OTP2_TICKERS if t in px0}
        otp2_invd = (START_NAV / 4) * otp2_inv0
        otp2_shares = {t: (otp2_invd / len(OTP2_TICKERS)) / otp2_entry[t] for t in otp2_entry}
        otp2 = dict(invested=otp2_inv0, cooldown=0, consec_vix_fall=0, consec_rvol_fall=0,
                    invested_dollars=otp2_invd, cash_dollars=(START_NAV / 4) - otp2_invd,
                    nav=START_NAV / 4, trading_cost=0.0, shares=otp2_shares, entry_prices=otp2_entry)

        sleeves = {"Gold": gold, "SectorEW": sectorew, "FMTS": fmts, "OTP2.0": otp2}
        total_nav = sum(sleeve_nav(n, s) for n, s in sleeves.items())

        state = dict(last_date=str(d0.date()), nav=total_nav, invested=1.0, invested_dollars=total_nav,
                     n_rebalances=0, trading_cost=0.0,
                     last_fmts_month=d0.strftime("%Y-%m"), last_sectorew_month=d0.strftime("%Y-%m"),
                     sleeves=sleeves)

        w_str = " / ".join(f"{n} {100*sleeve_nav(n,s)/total_nav:.0f}%" for n, s in sleeves.items())
        row0 = {"date": str(d0.date()), "nav": total_nav, "daily_log_ret": 0.0, "invested_pct": 100.0,
                "holdings": w_str, "rebalanced": True}
        pd.DataFrame([row0]).to_csv(LEDGER_PATH, index=False)
        with open(STATE_PATH, "w") as f:
            json.dump(state, f, indent=2)
        log_event("FourPillar", "seed", f"Seeded at ${total_nav:,.0f} - {w_str}", date=str(d0.date()))
        print(f"Seeded Four-Pillar at {d0.date()}: {w_str}")
        print(f"Runtime: {time.time()-t0:.1f}s")
        return

    # ── advance ─────────────────────────────────────────────────────────────
    sleeves = state["sleeves"]
    new_rows = []
    for i in range(start_pos, len(idx)):
        d = idx[i]
        prev_d = idx[i - 1]
        px_today = px.loc[d].dropna().to_dict()
        cash_ret = float(cash_daily.iloc[i])
        rebalanced_today = False

        # Gold: daily
        sleeves["Gold"] = gold_step(sleeves["Gold"], px_today.get("GLD", np.nan),
                                     bool(tips_falling.iloc[i - 1]), float(dxy_scalar.iloc[i - 1]),
                                     cash_ret, SLIPPAGE_RATE)

        # SectorEW: monthly rebalance, daily mark-to-market
        month_key = d.strftime("%Y-%m")
        if month_key != state.get("last_sectorew_month"):
            top_sec = latest_top_sectors(d)
            sleeves["SectorEW"] = sectorew_rebalance(sleeves["SectorEW"], top_sec, px_today, SLIPPAGE_RATE)
            state["last_sectorew_month"] = month_key
            log_event("FourPillar", "rebalance", f"SectorEW rotated to {', '.join(top_sec)}", date=str(d.date()))
        sleeves["SectorEW"] = sectorew_step(sleeves["SectorEW"], px_today, cash_ret)

        # FMTS: monthly rebalance, daily mark-to-market + trailing stop
        if month_key != state.get("last_fmts_month"):
            comp = latest_fmts_composite(d)
            top_fmts = comp.nlargest(FMTS_N_HOLDINGS)
            new_holdings = (top_fmts / top_fmts.sum()).to_dict() if len(top_fmts) else {}
            fmts_px_today = fmts_stocks_d.loc[fmts_stocks_d.index <= d].iloc[-1].dropna().to_dict()
            sleeves["FMTS"] = fb.monthly_rebalance(sleeves["FMTS"], new_holdings, fmts_px_today, SLIPPAGE_RATE)
            state["last_fmts_month"] = month_key
            log_event("FourPillar", "rebalance", f"FMTS rotated to {len(new_holdings)} names", date=str(d.date()))
        fmts_px_today = fmts_stocks_d.loc[fmts_stocks_d.index <= d].iloc[-1].dropna().to_dict()
        rvol20 = float(market_df["rvol20"].iloc[i])
        rvol_sma60 = float(market_df["rvol20"].rolling(60).mean().iloc[i])
        sleeves["FMTS"] = fb.daily_step(sleeves["FMTS"], fmts_px_today, rvol20, rvol_sma60, cash_ret,
                                         True, FMTS_STOP, SLIPPAGE_RATE)

        # OTP2.0: daily, exact live-engine logic
        row, prev = market_df.iloc[i], market_df.iloc[i - 1]
        blended = np.mean([np.log(px.loc[d, t] / px.loc[prev_d, t]) for t in OTP2_TICKERS
                            if t in px.columns and pd.notna(px.loc[d, t]) and pd.notna(px.loc[prev_d, t])])
        px_otp2_today = {t: float(px_today[t]) for t in OTP2_TICKERS if t in px_today}
        sleeves["OTP2.0"] = pte._step(row, prev, sleeves["OTP2.0"], OTP2_CFG, blended, cash_ret,
                                       px_otp2_today, cash_ret, d.date().isoformat(), strategy="FourPillar")

        # ── top-level drift-band rebalance ──────────────────────────────────
        total = sum(sleeve_nav(n, s) for n, s in sleeves.items())
        if total > 0:
            drift = max(abs(sleeve_nav(n, s) / total - TARGET_W) for n, s in sleeves.items())
            if drift > BAND:
                for n in sleeves:
                    cur = sleeve_nav(n, sleeves[n])
                    tgt = TARGET_W * total
                    if cur > 0:
                        rescale_sleeve(sleeves[n], tgt / cur)
                total = sum(sleeve_nav(n, s) for n, s in sleeves.items())
                state["n_rebalances"] = state.get("n_rebalances", 0) + 1
                rebalanced_today = True
                w_str_ev = " / ".join(f"{n} {100*sleeve_nav(n,s)/total:.0f}%" for n, s in sleeves.items())
                log_event("FourPillar", "rebalance", f"Band breach ({100*drift:.1f}% drift) - reset to {w_str_ev}",
                          date=str(d.date()))

        prev_nav = state["nav"]
        state["nav"] = total
        state["invested"] = 1.0
        state["invested_dollars"] = total
        daily_log_ret = np.log(total / prev_nav) if prev_nav > 0 else 0.0
        w_str = " / ".join(f"{n} {100*sleeve_nav(n,s)/total:.0f}%" for n, s in sleeves.items()) if total > 0 else ""
        new_rows.append({"date": str(d.date()), "nav": total, "daily_log_ret": daily_log_ret,
                          "invested_pct": 100.0, "holdings": w_str, "rebalanced": rebalanced_today})
        state["last_date"] = str(d.date())

    state["sleeves"] = sleeves
    existing = pd.read_csv(LEDGER_PATH)
    updated = pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True)
    updated.to_csv(LEDGER_PATH, index=False)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

    print(f"Appended {len(new_rows)} day(s). NAV={state['nav']:.2f}  Date={state['last_date']}  "
          f"Rebalances this run: {sum(1 for r in new_rows if r['rebalanced'])}")
    print(f"Runtime: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
