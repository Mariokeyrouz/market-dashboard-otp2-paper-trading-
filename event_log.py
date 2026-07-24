"""
Event Log — persistent activity trail for the strategy suite
============================================================
An append-only record (events.jsonl) of what each strategy has DONE — seeds,
rebalances, stop triggers/re-entries, risk-on/off flips, and big trims — read by
the Activity Log page. Two ways events land here:

  * backfill_from_ledgers()  — reconstructs the timeline from ledger history
    (source="backfill"). Idempotent; re-run by the daily job to stay current.
  * log_event(...)           — engines append richer LIVE events (source="engine"),
    e.g. with realized P&L and the tickers traded. Preserved across backfills.

Historical realized P&L can't be recovered from the ledgers (they store NAV, not
per-trade fills), so backfilled events carry no realized_pnl — that comes only
from engine-logged events going forward.
"""

import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(REPO, "events.jsonl")

# (display name, ledger file, icon) — the whole system, Gold included.
STRATS = [
    ("OTP2.0",     "paper_ledger.csv",      "📊"),
    ("OTP2.0 AMA", "paper_ledger_AMA.csv",  "🧠"),
    ("FMTS",       "factor_ledger.csv",     "🎯"),
    ("FMTS AMA",   "factor_ledger_AMA.csv", "🔬"),
    ("Gold",       "gold_ledger.csv",       "🥇"),
    ("Momentum",   "momentum_ledger.csv",   "🚀"),
]


def log_event(strategy, etype, detail, date=None, realized_pnl=None,
              tickers=None, source="engine"):
    """Append one structured event to events.jsonl (used by engines for live,
    rich events — including realized P&L)."""
    rec = {"date": date or datetime.now().strftime("%Y-%m-%d"),
           "strategy": strategy, "type": etype, "detail": detail, "source": source}
    if realized_pnl is not None:
        rec["realized_pnl"] = round(float(realized_pnl), 2)
    if tickers:
        rec["tickers"] = list(tickers)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_events():
    if not os.path.exists(LOG_PATH):
        return []
    out = []
    with open(LOG_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    return out


def _derive_events(name, ledger_path):
    """Reconstruct action events from one ledger's history."""
    if not os.path.exists(ledger_path):
        return []
    led = pd.read_csv(ledger_path, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    if len(led) == 0:
        return []
    d = lambda i: str(led["date"].iloc[i].date())
    ev = [(d(0), name, "seed", f"Seeded at ${led['nav'].iloc[0]:,.0f}")]
    cols = led.columns
    if "holdings" in cols:
        prev = None
        for i in range(len(led)):
            h = led["holdings"].iloc[i]
            if prev is not None and isinstance(h, str) and isinstance(prev, str) and h != prev:
                ev.append((d(i), name, "rebalance", "Rebalanced holdings"))
            prev = h
    if "stopped_out" in cols:
        v = led["stopped_out"].astype(str).str.lower().isin(["true", "1"]).values
        for i in range(1, len(v)):
            if v[i] and not v[i-1]:
                ev.append((d(i), name, "stop", "Trailing stop -> scaled to 50%"))
            elif not v[i] and v[i-1]:
                ev.append((d(i), name, "reentry", "Re-entered after stop"))
    if "risk_on" in cols:
        v = led["risk_on"].astype(str).str.lower().isin(["true", "1"]).values
        for i in range(1, len(v)):
            if not v[i] and v[i-1]:
                ev.append((d(i), name, "risk-off", "Trend gate -> risk-off (cash)"))
            elif v[i] and not v[i-1]:
                ev.append((d(i), name, "risk-on", "Trend gate -> risk-on"))
    if "invested_pct" in cols:
        iv = pd.to_numeric(led["invested_pct"], errors="coerce").values
        for i in range(1, len(iv)):
            if np.isfinite(iv[i]) and np.isfinite(iv[i-1]):
                delta = iv[i] - iv[i-1]
                if delta <= -8:
                    ev.append((d(i), name, "trim", f"Trimmed to {iv[i]:.0f}% invested"))
                elif delta >= 8:
                    ev.append((d(i), name, "reload", f"Reloaded to {iv[i]:.0f}% invested"))
    return ev


def backfill_from_ledgers():
    """Regenerate the derived (source='backfill') events from current ledgers,
    preserving any source='engine' events. Idempotent — safe to re-run daily."""
    kept = [e for e in load_events() if e.get("source") != "backfill"]
    # A live engine event (with realized P&L) takes precedence — don't re-derive
    # a ledger version of the same (strategy, date, type).
    engine_keys = {(e.get("strategy"), e.get("date"), e.get("type")) for e in kept}
    derived = []
    for name, ledger, _ in STRATS:
        for date, strat, etype, detail in _derive_events(name, os.path.join(REPO, ledger)):
            if (strat, date, etype) in engine_keys:
                continue
            derived.append({"date": date, "strategy": strat, "type": etype,
                            "detail": detail, "source": "backfill"})
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        for e in kept + derived:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return len(derived)


if __name__ == "__main__":
    n = backfill_from_ledgers()
    print(f"events.jsonl rebuilt: {n} derived events + preserved live events")
