"""
Sector-Gated Long/Short Backtest — top-down rule gate, not a ranking
======================================================================
Top-down: rank sectors (Leading/Improving = winning, Weakening/Lagging =
declining) via the RRG feature panel, then within winning sectors find stocks
whose OWN relative-strength geometry confirms leadership (LONG candidates),
and within declining sectors find stocks confirming deterioration (SHORT
candidates). A name only enters the book while its rule holds; if no rule
fires anywhere, the book is FLAT. All-long, all-short, mixed, and flat are all
valid weekly states — this is a GATE, not an always-invested ranking.

WHY THIS IS NOT JUST RRG AGAIN
-------------------------------
Two long/short attempts already failed in this repo:
  - cross_sectional_momentum_backtest.py: plain 12-1 momentum quintile spread,
    beta-neutral. Sharpe -0.59. Short leg optimistically biased by the
    survivorship-biased universe's delisting gap (see that script's docstring).
  - rrg_validate.py: top-down sector->stock relative rotation ranked by a
    walk-forward-fit linear score. 1/9 pre-registered criteria passed
    (rrg_calibration.json: sizing_multiplier=0). OOS IR 0.03 vs in-sample 0.60;
    the RRG factor block added nothing over plain 12-1 relative momentum.

This script reuses RRG's FEATURE ENGINEERING (rrg_validate.build_panel(), which
wraps rrg_core.compute_features() — quadrant, distance, delta_distance,
straightness) but explicitly does NOT reuse rrg_calibration.json, the fitted
linear score (rrg_analysis.score_from_weights()), or Kelly sizing (already
shown to be the wrong tool for this book type — see rrg_analysis.py's own
commentary, Kelly wealth fractions routinely exceed 100%). Instead it applies
simple, fixed, pre-registered discrete rules directly to the measured features,
and — critically — is judged against a NO-GATE comparison arm (same sector/
stock selection, always invested) that isolates whether the gate itself adds
value. That horse race is the one genuinely new claim versus the already-
failed RRG ranking.

SURVIVORSHIP BIAS
-----------------
The sector layer (rd.SECTOR_ETFS) is clean — all 11 SPDRs still trade. The
stock layer (rd.load_stock_panel()) is today's S&P 500 membership backfilled:
a name that was deep in the Lagging quadrant and later delisted is absent from
EVERY historical date in this panel, not just from its removal date forward.
That is worse than standard survivorship bias and it optimistically biases the
SHORT leg specifically (see cross_sectional_momentum_backtest.py's docstring
for the identical reasoning). Sector classification here is trustworthy;
stock-level short-leg profitability is an upper bound.

COSTS (restated, not imported, per repo convention)
----------------------------------------------------
  Commission + slippage : 10 bps one-way on turnover
  Stress cost            : 20 bps one-way, explicit robustness arm
  Short-leg borrow       : 30 bps/year, accrued weekly on short notional

Outputs: sector_ls_results.csv, sector_ls_surface.csv,
         sector_ls_exposure_log.csv, sector_ls_curve.csv,
         sector_ls_trade_log.csv

This is PAPER-TESTING RESEARCH ONLY. Not a recommendation to trade real
money; nothing here is wired into the live paper-trading engines.

Usage:
  py sector_ls_backtest.py
"""

import sys
import time
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")   # Windows console is cp1252

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

import rrg_core as rc
import rrg_data as rd
import rrg_stats as rs
import rrg_validate as rv

STRAIGHTNESS_NULL = 0.769        # frozen simulated-null value, see rrg_null.py / rrg_analysis.py
FWD_HORIZON = "1M"               # 4-week forward excess, for accuracy reporting

RFR = 0.03
COST_BPS = 10.0
COST_BPS_STRESS = 20.0
BORROW_BPS_ANNUAL = 30.0
PERIODS_PER_YEAR = 52.0

# Sweep grid (report the surface, never the best cell)
STR_MULTS = (0.8, 1.0, 1.2)
TERCILE_MINS = (1, 2, 3)
MIN_LEG_NAMES_GRID = (1, 3, 5)

BASE = dict(str_mult=1.0, tercile_min=2, min_leg_names=3)


# ─────────────────────────────────────────────────────────────────────────────
# 1. DATA / PANELS
# ─────────────────────────────────────────────────────────────────────────────

def load_sector_panel():
    px_all = rd.load_sector_prices(verbose=False)
    sectors = [s for s in rd.SECTOR_ETFS if s in px_all.columns]
    dly = px_all[sectors + [rd.BENCHMARK]].dropna(how="all")
    wk = rc.to_weekly(dly)
    panel = rv.build_panel(wk[sectors], wk[rd.BENCHMARK], rc.WEEKLY, rv.HORIZONS_W, 52, 4, "sectors")
    return px_all, sectors, panel


def sector_states(panel):
    """Per-week boolean DataFrames (index=weeks, columns=sector ETFs)."""
    q = panel["feats"]["quadrant"]
    idx, cols = panel["index"], panel["columns"]
    qdf = pd.DataFrame(q, index=idx, columns=cols)
    winning = qdf.isin([0.0, 3.0])     # Leading or Improving
    declining = qdf.isin([1.0, 2.0])   # Weakening or Lagging
    return winning, declining


def build_stock_panels(px_all, sectors, verbose=True):
    """One rv.build_panel() per sector, constituents vs their own sector ETF —
    same construction as rrg_analysis.py's loop, but for ALL sectors (both
    winning and declining), not just the top-3."""
    smap = rd.load_sector_map(verbose=False)
    stock_px = rd.load_stock_panel(verbose=False)
    panels, ticker_to_etf = {}, {}
    for etf in sectors:
        names = rd.stocks_in_sector(smap, etf, stock_px.columns)
        if len(names) < 8:
            if verbose:
                print(f"  {etf}: only {len(names)} constituents — skipped")
            continue
        cols = [c for c in names if c in stock_px.columns]
        sub_d = stock_px[cols].join(px_all[[etf]], how="inner").dropna(how="all")
        if etf not in sub_d.columns:
            continue
        sub_w = rc.to_weekly(sub_d)
        sub_w = sub_w[sub_w[etf].notna()]
        keep = [c for c in sub_w.columns
                if c == etf or sub_w[c].notna().sum() >= 0.5 * len(sub_w)]
        sub_w = sub_w[keep]
        if len(sub_w) < 300:
            if verbose:
                print(f"  {etf}: insufficient weekly history — skipped")
            continue
        tick = [c for c in sub_w.columns if c != etf]
        if not tick:
            continue
        pan = rv.build_panel(sub_w[tick], sub_w[etf], rc.WEEKLY, rv.HORIZONS_W, 52, 4, etf)
        panels[etf] = pan
        for t in tick:
            ticker_to_etf[t] = etf
        if verbose:
            print(f"  {etf}: {len(tick)} constituents, {len(sub_w)} weeks")
    return panels, ticker_to_etf


def sector_distance_edges(panels):
    """Design-sample (<=2013-12-31) distance terciles, pooled across every
    stock in the sector — identical logic to rrg_analysis.historical_buckets."""
    edges = {}
    for etf, pan in panels.items():
        mask = rv.slice_mask(pan["index"], end=rv.DESIGN_END)
        d = pan["feats"]["distance"][mask]
        d = d[np.isfinite(d)]
        edges[etf] = np.quantile(d, [0, 1 / 3, 2 / 3, 1.0]) if d.size >= 200 else None
    return edges


# ─────────────────────────────────────────────────────────────────────────────
# 2. SIGNAL
# ─────────────────────────────────────────────────────────────────────────────

def compute_signals(panels, edges, sector_win, sector_dec, str_mult, tercile_min, gate=True):
    """
    Boolean LONG/SHORT frames per stock, sector-gated.

    LONG  = sector WINNING  & (Leading, or Improving with delta_distance>0)
            [& straightness > str_mult*NULL & distance tercile >= tercile_min if gate]
    SHORT = sector DECLINING & (Lagging, or Weakening with delta_distance<0)
            [& straightness > str_mult*NULL & distance tercile >= tercile_min if gate]

    `gate=False` drops the straightness/tercile filter entirely (the no-gate
    comparison arm) — same base rule, always invested whenever a candidate
    exists.
    """
    long_frames, short_frames = [], []
    long_hits, short_hits = [], []   # pooled fwd-excess for triggered names, accuracy check
    thresh = str_mult * STRAIGHTNESS_NULL

    for etf, pan in panels.items():
        q = pan["feats"]["quadrant"]
        dd = pan["feats"]["delta_distance"]
        st = pan["feats"]["straightness"]
        dist = pan["feats"]["distance"]
        fwd = pan["fwd"][FWD_HORIZON]
        idx, cols = pan["index"], pan["columns"]

        base_long = (q == 0) | ((q == 3) & (dd > 0))
        base_short = (q == 2) | ((q == 1) & (dd < 0))

        if gate:
            e = edges.get(etf)
            if e is None:
                terc = np.full(dist.shape, np.nan)
            else:
                terc = np.digitize(dist, [e[1], e[2]]) + 1.0
                terc = np.where(np.isfinite(dist), terc, np.nan)
            qual = (st > thresh) & (terc >= tercile_min)
        else:
            qual = np.ones_like(q, dtype=bool)

        long_cond = base_long & qual
        short_cond = base_short & qual

        win_g = sector_win[etf].reindex(idx).fillna(False).to_numpy()[:, None]
        dec_g = sector_dec[etf].reindex(idx).fillna(False).to_numpy()[:, None]
        long_cond = long_cond & win_g
        short_cond = short_cond & dec_g

        long_frames.append(pd.DataFrame(long_cond, index=idx, columns=cols))
        short_frames.append(pd.DataFrame(short_cond, index=idx, columns=cols))

        lf = fwd[long_cond]
        sf = fwd[short_cond]
        long_hits.append(lf[np.isfinite(lf)])
        short_hits.append(sf[np.isfinite(sf)])

    long_all = pd.concat(long_frames, axis=1).fillna(False).astype(bool)
    short_all = pd.concat(short_frames, axis=1).fillna(False).astype(bool)
    long_fwd = np.concatenate(long_hits) if long_hits else np.array([])
    short_fwd = np.concatenate(short_hits) if short_hits else np.array([])
    return long_all, short_all, long_fwd, short_fwd


# ─────────────────────────────────────────────────────────────────────────────
# 3. PORTFOLIO CONSTRUCTION
# ─────────────────────────────────────────────────────────────────────────────

def run_backtest(long_all, short_all, sector_win, sector_dec, ret_w,
                  min_leg_names, cost_bps, borrow_bps_annual):
    """Weekly gate, fully re-evaluated every period — no fixed holding period,
    no dwell timer. A name is only in the book while its rule holds THAT week."""
    long_g = long_all.reindex(ret_w.index).fillna(False)
    short_g = short_all.reindex(ret_w.index).fillna(False)
    win_g = sector_win.reindex(ret_w.index).fillna(False)
    dec_g = sector_dec.reindex(ret_w.index).fillna(False)
    dates = ret_w.index

    eq_ls, eq_long, eq_short = 100.0, 100.0, 100.0
    curve_ls, curve_long, curve_short = {}, {}, {}
    w_long, w_short = pd.Series(dtype=float), pd.Series(dtype=float)
    borrow_w = borrow_bps_annual / 1e4 / PERIODS_PER_YEAR
    log = []

    for i in range(len(dates) - 1):
        t, t1 = dates[i], dates[i + 1]
        raw_longs = list(long_g.columns[long_g.loc[t].to_numpy()])
        raw_shorts = list(short_g.columns[short_g.loc[t].to_numpy()])
        longs = raw_longs if len(raw_longs) >= min_leg_names else []
        shorts = raw_shorts if len(raw_shorts) >= min_leg_names else []

        tgt_l = pd.Series(1.0 / len(longs), index=longs) if longs else pd.Series(dtype=float)
        tgt_s = pd.Series(1.0 / len(shorts), index=shorts) if shorts else pd.Series(dtype=float)

        if len(tgt_l) and len(tgt_s):
            long_frac, short_frac, state = 0.5, 0.5, "mixed"
        elif len(tgt_l):
            long_frac, short_frac, state = 1.0, 0.0, "long_only"
        elif len(tgt_s):
            long_frac, short_frac, state = 0.0, 1.0, "short_only"
        else:
            long_frac, short_frac, state = 0.0, 0.0, "flat"

        all_l = w_long.index.union(tgt_l.index)
        turn_l = float((tgt_l.reindex(all_l).fillna(0.0) - w_long.reindex(all_l).fillna(0.0)).abs().sum())
        all_s = w_short.index.union(tgt_s.index)
        turn_s = float((tgt_s.reindex(all_s).fillna(0.0) - w_short.reindex(all_s).fillna(0.0)).abs().sum())
        eq_long *= (1.0 - turn_l * cost_bps / 1e4)
        eq_short *= (1.0 - turn_s * cost_bps / 1e4)
        w_long, w_short = tgt_l, tgt_s

        r_long = float((w_long * ret_w.loc[t1].reindex(w_long.index).fillna(0.0)).sum()) if len(w_long) else 0.0
        r_short = float((w_short * ret_w.loc[t1].reindex(w_short.index).fillna(0.0)).sum()) if len(w_short) else 0.0

        # eq_short: informational only — raw (long-only) return of the short
        # CANDIDATES, to show what they did. eq_ls is the actual traded book,
        # where the short leg's P&L is -r_short.
        eq_long *= (1.0 + r_long)
        eq_short *= (1.0 + r_short - borrow_w)
        eq_ls *= (1.0 + long_frac * r_long - short_frac * r_short - short_frac * borrow_w)

        curve_long[t1], curve_short[t1], curve_ls[t1] = eq_long, eq_short, eq_ls
        log.append({
            "date": t, "n_sectors_winning": int(win_g.loc[t].sum()),
            "n_sectors_declining": int(dec_g.loc[t].sum()),
            "n_long_candidates": len(raw_longs), "n_short_candidates": len(raw_shorts),
            "n_long_used": len(longs), "n_short_used": len(shorts),
            "long_frac": long_frac, "short_frac": short_frac,
            "gross": long_frac + short_frac, "state": state,
            "turnover_long": turn_l, "turnover_short": turn_s,
            "longs": ",".join(longs), "shorts": ",".join(shorts),
        })

    return (pd.Series(curve_ls).sort_index(), pd.Series(curve_long).sort_index(),
            pd.Series(curve_short).sort_index(), pd.DataFrame(log))


def buy_hold(series, index):
    s = series.reindex(index).dropna()
    return 100.0 * s / s.iloc[0]


# ─────────────────────────────────────────────────────────────────────────────
# 4. STATS / REPORTING
# ─────────────────────────────────────────────────────────────────────────────

def metrics(curve, label, rfr=RFR):
    curve = curve.dropna()
    if len(curve) < 52:
        return {"label": label, "cagr_pct": np.nan, "vol_pct": np.nan, "sharpe": np.nan,
                "sortino": np.nan, "max_dd_pct": np.nan, "final": np.nan}
    n = len(curve)
    cagr = (curve.iloc[-1] / curve.iloc[0]) ** (PERIODS_PER_YEAR / n) - 1
    r = curve.pct_change().dropna()
    vol = r.std() * np.sqrt(PERIODS_PER_YEAR)
    sharpe = (r.mean() - rfr / PERIODS_PER_YEAR) / r.std() * np.sqrt(PERIODS_PER_YEAR) if r.std() > 0 else 0.0
    neg = r[r < 0]
    dd_std = neg.std() * np.sqrt(PERIODS_PER_YEAR) if len(neg) > 1 else 0.0
    sortino = (cagr - rfr) / dd_std if dd_std > 0 else 0.0
    roll = curve.cummax()
    dd = (curve - roll) / roll
    return {"label": label, "cagr_pct": cagr * 100, "vol_pct": vol * 100, "sharpe": sharpe,
            "sortino": sortino, "max_dd_pct": dd.min() * 100, "final": curve.iloc[-1]}


def fmt(v, d=2, suffix=""):
    return "n/a" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:.{d}f}{suffix}"


def table(rows, headers, widths):
    if HAS_TABULATE:
        print(tabulate(rows, headers=headers, tablefmt="simple"))
        return
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line); print("-" * len(line))
    for row in rows:
        print("  ".join(str(v).ljust(widths[i]) for i, v in enumerate(row)))


def banner(title, ch="="):
    print("\n" + ch * 100)
    print(title)
    print(ch * 100)


# ─────────────────────────────────────────────────────────────────────────────
# 5. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    banner("SECTOR-GATED LONG/SHORT BACKTEST — top-down rule gate (flat is a valid state)")
    print("Reuses rrg_validate.build_panel() feature engineering; does NOT reuse")
    print("rrg_calibration.json, the fitted linear score, or Kelly sizing.")
    print("PAPER-TESTING RESEARCH ONLY. Prior L/S attempts here both failed:")
    print("  cross_sectional_momentum_backtest.py: Sharpe -0.59")
    print("  RRG (rrg_validate.py): 1/9 pre-registered criteria, sizing_multiplier=0")

    print("\nLoading sector panel (11 SPDR sector ETFs vs SPY)...", flush=True)
    px_all, sectors, sec_panel = load_sector_panel()
    sector_win, sector_dec = sector_states(sec_panel)
    print(f"Sector panel: {len(sec_panel['index'])} weeks x {len(sectors)} sectors "
          f"({sec_panel['index'][0].date()} -> {sec_panel['index'][-1].date()})")

    print("\nBuilding per-sector stock panels (constituents vs their own sector ETF)...", flush=True)
    panels, ticker_to_etf = build_stock_panels(px_all, sectors)
    if not panels:
        raise RuntimeError("No sector produced a usable constituent panel.")
    edges = sector_distance_edges(panels)

    print("\nBuilding weekly return matrix for the full stock universe...", flush=True)
    stock_px = rd.load_stock_panel(verbose=False)
    universe = [t for t in ticker_to_etf if t in stock_px.columns]
    px_w = rc.to_weekly(stock_px[universe])
    ret_w = px_w.pct_change()
    spy_w = rc.to_weekly(px_all[[rd.BENCHMARK]])[rd.BENCHMARK]

    print(f"Weekly universe: {len(universe)} names, {len(ret_w)} weeks "
          f"({ret_w.index[0].date()} -> {ret_w.index[-1].date()})")

    # ── base config ─────────────────────────────────────────────────────────
    banner(f"BASE CONFIG — str_mult={BASE['str_mult']} (thresh {BASE['str_mult']*STRAIGHTNESS_NULL:.3f}), "
           f"tercile>={BASE['tercile_min']}, min_leg_names={BASE['min_leg_names']}")
    long_all, short_all, long_fwd, short_fwd = compute_signals(
        panels, edges, sector_win, sector_dec, BASE["str_mult"], BASE["tercile_min"], gate=True)
    ls, long_c, short_c, log = run_backtest(
        long_all, short_all, sector_win, sector_dec, ret_w,
        BASE["min_leg_names"], COST_BPS, BORROW_BPS_ANNUAL)
    spy_curve = buy_hold(spy_w, ls.index)

    # no-gate comparison arm: same base rule (quadrant + sector), no straightness/tercile filter
    long_ng, short_ng, _, _ = compute_signals(
        panels, edges, sector_win, sector_dec, BASE["str_mult"], BASE["tercile_min"], gate=False)
    ls_ng, _, _, _ = run_backtest(long_ng, short_ng, sector_win, sector_dec, ret_w, 1, COST_BPS, BORROW_BPS_ANNUAL)

    results = [metrics(ls, "L/S book (gated)"), metrics(long_c, "Long candidates (raw, informational)"),
               metrics(short_c, "Short candidates (raw, informational)"),
               metrics(ls_ng, "L/S book (NO-GATE comparison arm)"), metrics(spy_curve, "SPY buy & hold")]
    table([[r["label"], fmt(r["cagr_pct"], 2, "%"), fmt(r["vol_pct"], 2, "%"), fmt(r["sharpe"], 3),
            fmt(r["sortino"], 3), fmt(r["max_dd_pct"], 1, "%"), f"${r['final']:.0f}"] for r in results],
          ["Arm", "CAGR", "Vol", "Sharpe", "Sortino", "MaxDD", "Final $100"],
          [38, 8, 8, 8, 8, 8, 11])

    # ── exposure state ──────────────────────────────────────────────────────
    banner("EXPOSURE STATE — % of weeks in each (descriptive, not pass/fail)")
    state_pct = log["state"].value_counts(normalize=True).reindex(
        ["flat", "long_only", "short_only", "mixed"]).fillna(0.0) * 100
    for s, p in state_pct.items():
        print(f"  {s:<12s} {p:5.1f}%")
    avg_turn_l, avg_turn_s = log["turnover_long"].mean(), log["turnover_short"].mean()
    print(f"\n  Avg weekly turnover — long leg: {avg_turn_l:.2f}   short leg: {avg_turn_s:.2f}")
    print(f"  Avg candidates/week — long: {log['n_long_candidates'].mean():.1f}   "
          f"short: {log['n_short_candidates'].mean():.1f}")

    # ── accuracy vs measured baseline ───────────────────────────────────────
    banner("ACCURACY — hit rate vs each stock panel's OWN measured baseline (never 50%)")
    all_fwd = np.concatenate([pan["fwd"][FWD_HORIZON].ravel() for pan in panels.values()])
    baseline_up = rs.hit_rate(all_fwd)
    baseline_down = float(np.mean(all_fwd[np.isfinite(all_fwd)] < 0))
    long_hit = rs.hit_rate(long_fwd)
    short_hit = float(np.mean(short_fwd < 0)) if short_fwd.size else np.nan
    print(f"  Baseline (unconditional, pooled): P(fwd>0)={100*baseline_up:.2f}%  "
          f"P(fwd<0)={100*baseline_down:.2f}%")
    print(f"  LONG leg  (n={long_fwd.size}): hit rate (fwd>0) = {fmt(100*long_hit,2,'%')}  "
          f"edge {fmt(100*(long_hit-baseline_up),2,'pp')}")
    print(f"  SHORT leg (n={short_fwd.size}): hit rate (fwd<0) = {fmt(100*short_hit,2,'%')}  "
          f"edge {fmt(100*(short_hit-baseline_down),2,'pp')}")

    # ── walk-forward (holdout) ──────────────────────────────────────────────
    banner(f"WALK-FORWARD — holdout >= {rv.HOLDOUT_START}")
    hold = ls[ls.index >= pd.Timestamp(rv.HOLDOUT_START)]
    hold_norm = 100.0 * hold / hold.iloc[0] if len(hold) else hold
    spy_hold = spy_curve[spy_curve.index >= pd.Timestamp(rv.HOLDOUT_START)]
    spy_hold_norm = 100.0 * spy_hold / spy_hold.iloc[0] if len(spy_hold) else spy_hold
    oos_m = metrics(hold_norm, f"OOS L/S (holdout, n={len(hold)})")
    oos_spy_m = metrics(spy_hold_norm, "OOS SPY")
    table([[r["label"], fmt(r["cagr_pct"], 2, "%"), fmt(r["sharpe"], 3), fmt(r["max_dd_pct"], 1, "%")]
           for r in [oos_m, oos_spy_m]], ["Period", "CAGR", "Sharpe", "MaxDD"], [30, 8, 8, 8])

    # ── significance ─────────────────────────────────────────────────────────
    ls_ret = ls.pct_change().dropna().values
    _, t_nw, n_obs = rs.newey_west_t(ls_ret, lag=2)
    t_naive = rs.naive_t(ls_ret)
    print(f"\nWeeks: {len(ls_ret)}   Naive t (n={n_obs}): {fmt(t_naive,2)}   "
          f"Newey-West (lag=2, sanity check): {fmt(t_nw,2)}")
    print("(Weekly rebalance already samples one non-overlapping observation per period.)")

    stress_ls, _, _, _ = run_backtest(long_all, short_all, sector_win, sector_dec, ret_w,
                                       BASE["min_leg_names"], COST_BPS_STRESS, BORROW_BPS_ANNUAL)
    stress_cagr = metrics(stress_ls, "")["cagr_pct"]
    base_m = results[0]
    print(f"\nCost stress ({COST_BPS_STRESS:.0f}bps one-way): CAGR {fmt(stress_cagr,2,'%')} "
          f"(base {fmt(base_m['cagr_pct'],2,'%')})")

    # ── parameter surface ───────────────────────────────────────────────────
    banner(f"PARAMETER SURFACE ({len(STR_MULTS)*len(TERCILE_MINS)*len(MIN_LEG_NAMES_GRID)} cells) "
           "— median / sign agreement, never the best cell")
    surf_rows = []
    for sm in STR_MULTS:
        for tm in TERCILE_MINS:
            l_all, s_all, _, _ = compute_signals(panels, edges, sector_win, sector_dec, sm, tm, gate=True)
            for mln in MIN_LEG_NAMES_GRID:
                ls_c, _, _, _ = run_backtest(l_all, s_all, sector_win, sector_dec, ret_w, mln,
                                              COST_BPS, BORROW_BPS_ANNUAL)
                m = metrics(ls_c, "")
                r = ls_c.pct_change().dropna().values
                _, t_cell, _ = rs.newey_west_t(r, lag=2)
                surf_rows.append({"str_mult": sm, "tercile_min": tm, "min_leg_names": mln,
                                   "cagr_pct": m["cagr_pct"], "sharpe": m["sharpe"], "t_nw": t_cell})
    surf = pd.DataFrame(surf_rows)
    surf.to_csv("sector_ls_surface.csv", index=False)
    sc = surf["cagr_pct"].dropna()
    tc = surf["t_nw"].dropna()
    print(f"CAGR%  — median {fmt(sc.median(),2)}  min {fmt(sc.min(),2)}  max {fmt(sc.max(),2)}  "
          f"sign+ {(sc>0).mean()*100:.0f}% of {len(sc)} cells")
    print(f"t_nw   — median {fmt(tc.median(),2)}  sign agreement {max((tc>0).mean(),(tc<0).mean())*100:.0f}%")

    # ── pre-registered criteria ─────────────────────────────────────────────
    banner("PRE-REGISTERED CRITERIA (written before reading results; 1,2,3 mandatory; >=5/8 optional to pass)")
    checks = [
        (1, True, "Net-of-cost CAGR > 0 (base config, full sample)",
         base_m["cagr_pct"] > 0, f"{base_m['cagr_pct']:+.2f}%"),
        (2, True, "Survives 20bps stress cost (still net positive CAGR)",
         stress_cagr > 0, f"{stress_cagr:+.2f}%"),
        (3, True, f"Walk-forward holdout (>={rv.HOLDOUT_START}) still net positive CAGR",
         oos_m["cagr_pct"] > 0, f"{oos_m['cagr_pct']:+.2f}%"),
        (4, False, "Long-leg hit rate beats its own measured baseline",
         np.isfinite(long_hit) and long_hit > baseline_up, f"{fmt(100*long_hit,1)}% vs {100*baseline_up:.1f}%"),
        (5, False, "Short-leg hit rate beats its own measured baseline",
         np.isfinite(short_hit) and short_hit > baseline_down, f"{fmt(100*short_hit,1)}% vs {100*baseline_down:.1f}%"),
        (6, False, "Newey-West t on weekly L/S returns >= 3",
         np.isfinite(t_nw) and abs(t_nw) >= 3, f"t={fmt(t_nw,2)}"),
        (7, False, "Parameter-surface median t > 0 and sign agreement >= 70%",
         tc.median() > 0 and max((tc>0).mean(),(tc<0).mean()) >= 0.70,
         f"median t={fmt(tc.median(),2)}, agree={max((tc>0).mean(),(tc<0).mean())*100:.0f}%"),
        (8, False, "Beats the NO-GATE comparison arm (isolates the gate's value)",
         base_m["cagr_pct"] > results[3]["cagr_pct"] if np.isfinite(results[3]["cagr_pct"]) else False,
         f"gated {fmt(base_m['cagr_pct'],2)}% vs no-gate {fmt(results[3]['cagr_pct'],2)}%"),
    ]
    rows = [[str(n), "YES" if mand else "", "PASS" if ok else "FAIL", desc[:58], det[:38]]
            for n, mand, desc, ok, det in checks]
    table(rows, ["#", "Mand", "Result", "Criterion", "Detail"], [3, 5, 7, 58, 38])

    passed = sum(1 for _, _, _, ok, _ in checks if ok)
    mand_ok = all(ok for _, mand, _, ok, _ in checks if mand)
    verdict = "PASS" if (passed >= 5 and mand_ok) else "FAIL"
    print()
    print(f"SCORE: {passed}/8 criteria passed. Mandatory (1,2,3): {'all passed' if mand_ok else 'NOT all passed'}.")
    print(f"VERDICT: {verdict}" + (
        " — survived its own pre-registered bar; still only PAPER-testing evidence, not a live-trading"
        " recommendation, and the short-leg delisting-gap caveat above still applies." if verdict == "PASS"
        else " — report the null and stop. This does not mean a sector-gated L/S approach never works, only"
             " that this specific rule specification did not clear its own bar over this sample."))
    print("=" * 100)

    # ── outputs ──────────────────────────────────────────────────────────────
    pd.DataFrame(results).to_csv("sector_ls_results.csv", index=False)
    log.to_csv("sector_ls_exposure_log.csv", index=False)
    log[["date", "state", "longs", "shorts"]].to_csv("sector_ls_trade_log.csv", index=False)
    curves = pd.DataFrame({"ls": ls, "long_candidates": long_c, "short_candidates": short_c,
                            "spy": spy_curve, "no_gate": ls_ng.reindex(ls.index)})
    curves.to_csv("sector_ls_curve.csv")
    print(f"\nWrote sector_ls_results.csv, sector_ls_surface.csv, sector_ls_exposure_log.csv, "
          f"sector_ls_trade_log.csv, sector_ls_curve.csv")
    print(f"Runtime: {time.time() - t0:.0f}s")
    print("\nPAPER-TESTING RESEARCH ONLY. Not a recommendation to trade real money.")


if __name__ == "__main__":
    main()
