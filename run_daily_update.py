"""
Daily Paper-Trading Update — orchestrator
=========================================
Single entry point that advances EVERY paper-trading ledger, then commits and
pushes. Replaces the ad-hoc per-engine process that let 3 of 4 ledgers go stale
(each engine was being run by hand; miss one and it freezes).

What it does:
  1. Runs each strategy engine in its own subprocess (one crash can't stop the
     rest). Every engine is idempotent — it prints "No new trading days" and
     exits cleanly if already current, so daily/hourly reruns are safe.
  2. Auto-rotates the monthly momentum strategy: at each month-turn — when a
     newly completed month makes its selection stale — it re-runs the fast
     momentum screener with fresh prices, so the strategy rebalances on its own
     with no separate task. Within a month this is skipped, so the daily run
     stays fast. (--monthly forces it. factor_screener stays on the user's
     separate cadence — it fetches fundamentals for ~500 names and is slow.)
  3. If any tracked ledger/state/selection file changed, commits with the
     existing "Daily paper-trading update: <date>" message and pushes to main.

Schedule this once (Windows Task Scheduler, daily on weekday evenings):
    py run_daily_update.py
The monthly momentum rebalance now happens automatically inside that daily run —
no separate task needed. Use --monthly to force a re-screen; --no-push to
advance + commit locally without pushing.
"""

import json
import os
import subprocess
import sys
import time
from datetime import date, timedelta

REPO = os.path.dirname(os.path.abspath(__file__))

# Order matters only for readability; engines are independent.
ENGINES = [
    "paper_trading_engine.py",         # OTP2.0
    "paper_trading_engine_AMA.py",     # OTP2.0 AMA
    "factor_strategy_engine.py",       # FMTS
    "factor_strategy_engine_AMA.py",   # FMTS AMA
    "gold_strategy_engine.py",         # Gold timer
    "momentum_strategy_engine.py",     # Momentum (new)
]

# Fast screeners safe to run on a monthly rebalance pass. factor_screener.py is
# intentionally excluded — it fetches fundamentals for ~500 names (very slow) and
# stays on the user's separate cadence.
MONTHLY_SCREENERS = [
    "momentum_screener.py",
]

# Files the update touches — used to detect whether a commit is warranted.
TRACKED_GLOBS = ["*_ledger*.csv", "*_state*.json", "*_selection*.json",
                 "paper_*.csv", "paper_*.json", "gold_*.csv", "gold_*.json"]


def run(script, timeout=1200):
    print(f"\n{'='*70}\n>> {script}\n{'='*70}", flush=True)
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, script], cwd=REPO, timeout=timeout,
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        print(r.stdout[-2000:] if r.stdout else "(no stdout)")
        if r.returncode != 0:
            print(f"  [WARN] {script} exited {r.returncode}\n{(r.stderr or '')[-1500:]}")
            return False
        print(f"  [OK] {script} ({time.time()-t0:.0f}s)")
        return True
    except subprocess.TimeoutExpired:
        print(f"  [WARN] {script} timed out after {timeout}s")
        return False
    except Exception as e:
        print(f"  [WARN] {script} failed: {e}")
        return False


def git(*args):
    r = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def _latest_completed_month():
    """First-of-month label (YYYY-MM-DD) of the most recently COMPLETED month —
    exactly what momentum_screener screens as-of (it drops the partial current
    month). E.g. any day in July -> '2026-06-01'."""
    first_this = date.today().replace(day=1)
    return (first_this - timedelta(days=1)).replace(day=1).isoformat()


def _momentum_needs_rescreen():
    """True if momentum_selection.json is missing or older than the latest
    completed month — i.e. a new month turned and the strategy should rotate.
    ISO date strings compare correctly, so a plain `<` is enough."""
    path = os.path.join(REPO, "momentum_selection.json")
    if not os.path.exists(path):
        return True
    try:
        with open(path) as f:
            asof = json.load(f).get("as_of", "")
    except Exception:
        return True
    return asof < _latest_completed_month()


def main():
    monthly = "--monthly" in sys.argv
    do_commit = "--no-commit" not in sys.argv
    do_push = do_commit and "--no-push" not in sys.argv

    ok, failed = [], []

    # Auto-rotate the monthly momentum strategy. Re-screen only when a newly
    # completed month makes the current selection stale (or --monthly forces
    # it); within a month this is a no-op, so the daily run stays fast. Delete
    # the price cache first so the fresh screen includes the new month's close
    # (a <18h cache could still be pre-month-end and screen the old month).
    if monthly or _momentum_needs_rescreen():
        cache = os.path.join(REPO, "momentum_stocks_prices.csv")
        if os.path.exists(cache):
            os.remove(cache)
        print("Momentum: month-turn/forced — re-screening with fresh prices to rotate.")
        for s in MONTHLY_SCREENERS:
            (ok if run(s) else failed).append(s)
    else:
        print(f"Momentum: selection already current for {_latest_completed_month()[:7]} — no re-screen.")

    for e in ENGINES:
        (ok if run(e) else failed).append(e)

    # ── Commit + push if anything changed ────────────────────────────────────
    _, status = git("status", "--porcelain", *TRACKED_GLOBS)
    if not do_commit:
        print(f"\n--no-commit: skipping git. Changed ledger files:\n{status or '(none)'}")
    elif not status:
        print("\nNo ledger changes — nothing to commit.")
    else:
        git("add", *TRACKED_GLOBS)
        msg = f"Daily paper-trading update: {date.today().isoformat()}"
        code, out = git("commit", "-m", msg)
        print(f"\ncommit: {out.splitlines()[0] if out else code}")
        if do_push:
            code, out = git("push", "origin", "main")
            print(f"push: {'ok' if code == 0 else out}")
        else:
            print("push: skipped (--no-push)")

    print(f"\nSummary — advanced: {len(ok)}  failed: {len(failed)}"
          + (f"  ({', '.join(failed)})" if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
