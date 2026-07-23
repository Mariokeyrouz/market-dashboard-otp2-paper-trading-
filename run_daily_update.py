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
  2. Auto-rotates the monthly strategies at each month-turn, so they rebalance
     on their own with no separate task (within a month this is skipped, so the
     daily run stays fast; --monthly forces it):
       - Momentum: re-runs its fast (cached-price) screener when a newly
         completed month makes its selection stale.
       - FMTS / FMTS AMA: re-run their factor screeners once per calendar month
         (only when they have not screened yet this month). These are slow
         (~500 fundamentals fetches each), so they fire at most once a month.
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


def _needs_monthly_rescreen(selection_file, threshold):
    """True if `selection_file` is missing or its `as_of` sorts before
    `threshold` (both ISO strings, so a plain `<` works). Fires each monthly
    screener exactly once per rotation."""
    path = os.path.join(REPO, selection_file)
    if not os.path.exists(path):
        return True
    try:
        with open(path) as f:
            asof = json.load(f).get("as_of", "")
    except Exception:
        return True
    return asof < threshold


def main():
    monthly = "--monthly" in sys.argv
    do_commit = "--no-commit" not in sys.argv
    do_push = do_commit and "--no-push" not in sys.argv

    ok, failed = [], []
    this_month = date.today().strftime("%Y-%m-01")   # first day of the current month

    # ── Auto-rotate the monthly strategies at month-turn ─────────────────────
    # Momentum: fast (cached prices). Re-screen when a newly completed month
    # makes its selection stale; delete the cache first so the fresh screen
    # includes the new month's close (a <18h cache could still be pre-month-end).
    if monthly or _needs_monthly_rescreen("momentum_selection.json", _latest_completed_month()):
        cache = os.path.join(REPO, "momentum_stocks_prices.csv")
        if os.path.exists(cache):
            os.remove(cache)
        print("Momentum: month-turn/forced — re-screening with fresh prices to rotate.")
        (ok if run("momentum_screener.py") else failed).append("momentum_screener.py")
    else:
        print(f"Momentum: current for {_latest_completed_month()[:7]} — no re-screen.")

    # FMTS / FMTS AMA: slow factor screeners (~500 fundamentals each). Fire once
    # per calendar month — only when they have not screened yet this month.
    for scr, sel in [("factor_screener.py", "factor_selection.json"),
                     ("factor_screener_AMA.py", "factor_selection_AMA.json")]:
        if monthly or _needs_monthly_rescreen(sel, this_month):
            print(f"FMTS: monthly re-screen — {scr} (slow; ~once a month).")
            (ok if run(scr, timeout=2400) else failed).append(scr)
        else:
            print(f"FMTS: {sel} current for {date.today().strftime('%Y-%m')} — no re-screen.")

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
