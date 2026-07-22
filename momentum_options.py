"""
Momentum + Options Convexity — Long-Call Overlay (Strategy #2, prototype)
========================================================================
The aggressive, low-win-rate / high-reward layer requested: instead of holding
the top momentum names outright, express each pick as a LONG CALL. Payoff is
convex — most calls expire worthless (low win rate), but the winners run
uncapped when a name trends. The signal is the SAME validated momentum screen;
options only change the *expression*.

*** MODELING WARNING — READ THIS ***
There is no free historical options data (yfinance serves only current chains),
so option prices here are MODELED with Black-Scholes using an implied-vol
ASSUMPTION (proxied from trailing realized vol × an IV premium). Real results
depend on the vol surface, skew, bid/ask, and early assignment — none captured
here. This is a payoff-shape study, NOT a tradeable backtest. Treat every
number as illustrative of the convexity profile, not as achievable P&L.

Mechanics (kept deliberately simple):
  * Monthly, risk-on only (SPY > 10mo SMA), take the top-N momentum names.
  * Split an options BUDGET (fraction of NAV) equally across them; the rest
    sits in T-bill. Each sleeve buys an ATM/OTM call, tenor 2 months.
  * Hold 1 month, revalue via Black-Scholes with 1 month left, book P&L, roll.
  * Max loss per sleeve = its premium (defined risk). Upside = uncapped.

Compares long-call overlay vs holding the momentum stocks outright vs SPY, and
sweeps moneyness x IV-premium so the assumption-sensitivity is visible.

Usage:
  py momentum_options.py
"""

import math
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

import momentum_stocks as ms

RFR = 0.03
TENOR_YEARS = 2 / 12         # 2-month options
HOLD_MONTHS = 1              # roll monthly
N_NAMES = 20
LOOKBACKS = (6, 12)
SKIP = 1
TREND_SMA_MONTHS = 10
OPTIONS_BUDGET = 0.20        # fraction of NAV spent on premium each month (bleed cap)


def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_call(S, K, T, r, sigma):
    """Black-Scholes European call price. Falls back to intrinsic at expiry/zero-vol."""
    if T <= 0 or sigma <= 0 or S <= 0:
        return max(S - K, 0.0)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)


def realized_vol_monthly(prices_m):
    """Annualized vol per name from trailing 12-month returns (crude IV proxy)."""
    return prices_m.pct_change().rolling(12).std() * math.sqrt(12)


def blended_rank(prices_m, at):
    r6 = prices_m.shift(SKIP) / prices_m.shift(6 + SKIP) - 1.0
    r12 = prices_m.shift(SKIP) / prices_m.shift(12 + SKIP) - 1.0
    rk = ((r6.loc[at].rank(pct=True) + r12.loc[at].rank(pct=True)) / 2)
    return rk[r6.loc[at].notna() & r12.loc[at].notna()]


def simulate(prices_m, spy_m, vol, moneyness=0.0, iv_premium=1.0,
             budget=OPTIONS_BUDGET, cash_stat=None):
    """
    Long-call overlay equity curve. `moneyness` = OTM fraction (0 = ATM, 0.05 =
    5% OTM). Returns (curve base 100, trade stats dict).
    """
    months = prices_m.index
    spy_sma = spy_m.rolling(TREND_SMA_MONTHS).mean()
    cash_m = (1.0 + RFR) ** (1 / 12) - 1.0

    equity = 100.0
    curve = pd.Series(index=months, dtype=float)
    wins = losses = 0
    win_ret, loss_ret = [], []

    first = 12 + SKIP
    for i in range(first, len(months) - 1):
        t, t1 = months[i], months[i + 1]
        if spy_m.loc[t] <= spy_sma.loc[t]:           # risk-off -> all cash
            equity *= (1.0 + cash_m)
            curve.loc[t1] = equity
            continue

        rk = blended_rank(prices_m, t).sort_values(ascending=False).head(N_NAMES)
        names = [n for n in rk.index if not np.isnan(vol.loc[t, n]) and vol.loc[t, n] > 0
                 and not np.isnan(prices_m.loc[t, n]) and not np.isnan(prices_m.loc[t1, n])]
        if not names:
            equity *= (1.0 + cash_m)
            curve.loc[t1] = equity
            continue

        budget_dollars = equity * budget
        cash_dollars = equity * (1.0 - budget)
        per_name = budget_dollars / len(names)
        payoff_total = 0.0

        for n in names:
            S0 = float(prices_m.loc[t, n])
            S1 = float(prices_m.loc[t1, n])
            K = S0 * (1.0 + moneyness)
            sigma = float(vol.loc[t, n]) * iv_premium
            prem = bs_call(S0, K, TENOR_YEARS, RFR, sigma)
            if prem <= 0:
                payoff_total += per_name          # degenerate; hold as cash
                continue
            contracts = per_name / prem           # $ invested / premium per unit
            val1 = bs_call(S1, K, TENOR_YEARS - HOLD_MONTHS / 12, RFR, sigma)
            sleeve_value = contracts * val1
            payoff_total += sleeve_value
            r = sleeve_value / per_name - 1.0
            (win_ret if r > 0 else loss_ret).append(r)
            if r > 0:
                wins += 1
            else:
                losses += 1

        equity = payoff_total + cash_dollars * (1.0 + cash_m)
        curve.loc[t1] = equity

    n_trades = wins + losses
    stats = {
        "win_rate": wins / n_trades * 100 if n_trades else float("nan"),
        "avg_win": np.mean(win_ret) * 100 if win_ret else float("nan"),
        "avg_loss": np.mean(loss_ret) * 100 if loss_ret else float("nan"),
        "payoff_ratio": (np.mean(win_ret) / abs(np.mean(loss_ret)))
                        if win_ret and loss_ret else float("nan"),
        "n_trades": n_trades,
    }
    return curve.dropna(), stats


def main():
    prices = ms.load_prices_cached()
    spy_m = prices[ms.BENCHMARK]
    stock_px = prices.drop(columns=[ms.BENCHMARK])
    stock_px = stock_px.loc[:, stock_px.notna().sum() >= 26]
    vol = realized_vol_monthly(stock_px)

    print("!" * 78)
    print("MODELED options (Black-Scholes + IV proxy). NOT a tradeable backtest —")
    print("a convexity payoff-shape study. See header warning.")
    print("!" * 78)

    # Baselines: momentum stocks outright + SPY, over the same options window.
    stock_curve, _ = ms.backtest(stock_px, spy_m, top_n=N_NAMES, lookback=12, skip=1,
                                 trend_filter=True, cost_bps=20.0)
    base_curve, base_stats = simulate(stock_px, spy_m, vol, moneyness=0.0, iv_premium=1.0)
    spy = ms.bh(prices, ms.BENCHMARK, base_curve.index)
    stock_curve = stock_curve.reindex(base_curve.index).dropna()

    print("\n" + "=" * 84)
    print(f"BASE OVERLAY — ATM calls, IV=realized vol, {int(OPTIONS_BUDGET*100)}% premium budget/mo")
    print("=" * 84)
    ms.print_metrics([
        ms.metrics(base_curve, "Momentum LONG CALLS (ATM)"),
        ms.metrics(stock_curve, "Momentum stocks (outright)"),
        ms.metrics(spy, "SPY buy & hold"),
    ])
    print(f"\n  Convexity profile:  win rate {base_stats['win_rate']:.0f}%  "
          f"avg win {base_stats['avg_win']:+.0f}%  avg loss {base_stats['avg_loss']:+.0f}%  "
          f"payoff {base_stats['payoff_ratio']:.2f}x  ({base_stats['n_trades']} sleeves)")

    # Assumption sensitivity: moneyness x IV premium — CAGR (win-rate%).
    print("\n" + "=" * 84)
    print("ASSUMPTION SENSITIVITY — each cell = CAGR% (win-rate%)")
    print("  moneyness (OTM) down rows; IV premium across cols")
    print("=" * 84)
    moneyness_levels = [0.0, 0.05, 0.10]
    iv_levels = [0.90, 1.00, 1.15]
    try:
        from tabulate import tabulate
        has_tab = True
    except ImportError:
        has_tab = False
    grid = []
    for mny in moneyness_levels:
        row = [f"{int(mny*100)}% OTM"]
        for iv in iv_levels:
            c, s = simulate(stock_px, spy_m, vol, moneyness=mny, iv_premium=iv)
            m = ms.metrics(c, "")
            row.append(f"{m['cagr_pct']:.0f} ({s['win_rate']:.0f}%)")
        grid.append(row)
    hdr = ["moneyness \\ IV"] + [f"IV×{iv}" for iv in iv_levels]
    print(tabulate(grid, headers=hdr, tablefmt="simple") if has_tab
          else "\n".join("  ".join(map(str, r)) for r in [hdr] + grid))

    print("\nReading it: higher IV premium (options priced above realized vol) and")
    print("more OTM strikes lower the win rate and raise variance — the classic")
    print("low-win/high-reward tilt. Whether it BEATS holding the stock depends")
    print("entirely on the vol assumption, which real market IV controls, not us.")


if __name__ == "__main__":
    main()
