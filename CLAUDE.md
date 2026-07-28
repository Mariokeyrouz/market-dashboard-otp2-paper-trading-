# Market Dashboard — working notes

Two apps in one repo. **Read the environment traps before writing code** — several
are non-obvious and have broken the live deploy before.

## The two apps

| | Streamlit (internal research tool) | Next.js (the product) |
|---|---|---|
| Location | repo root + `pages/` | `web/` |
| Entry | `app.py` | `web/src/app/` |
| Deployed | https://otp2-dashboard.streamlit.app | Vercel |
| Deploy trigger | push to `main` (auto) | push to `main` (auto) |
| Deps | root `requirements.txt` | `web/package.json` |

GitHub: `Mariokeyrouz/market-dashboard-otp2-paper-trading-`, branch `main`.
**Both hosts auto-deploy on push, so a push is a production release.**

## Environment traps (learned the hard way)

- **`app.py` must keep its name.** Streamlit Community Cloud has no setting to change
  the "Main file path" after deploy — renaming it broke the live app and had to be
  reverted. Verify a setting exists before renaming any entry point.
- **`statsmodels` and `matplotlib` are broken here.** statsmodels 0.13.5 dies against
  pandas 3 (`statsmodels.api` raises on import); matplotlib was compiled against
  NumPy 1.x and fails the ABI check. Use **plotly** (the repo standard) and numpy.
- **`scipy` is NOT in `requirements.txt`.** It works locally by transitive install, so
  it will pass every local test and then fail on Streamlit Cloud. Anything a `pages/`
  file imports — directly or transitively — must be in `requirements.txt`.
- **Python 3.11, pandas 3.0.3, numpy 2.3.3.** `tabulate` is not installed.
- **Windows console is cp1252** — emoji/`Δ` in `print()` raise `UnicodeEncodeError`.
  Add `sys.stdout.reconfigure(encoding="utf-8")` in scripts that print them.
- **Bash tool + backticks**: backticks inside a double-quoted `git commit -m "..."`
  trigger command substitution and silently eat text. Use a `<<'MSG'` heredoc.

## Streamlit conventions

- Sidebar order comes from the numeric filename prefix (`pages/7_RRG.py`). The entry
  file's sidebar label is its filename ("app").
- `st.plotly_chart(fig, width='stretch')` — `use_container_width` is deprecated in 1.58.
- `st.dataframe` defaults to a **10-row viewport**; pass an explicit `height` to show
  more (`38 header + 35*rows + 10 padding`).
- Custom HTML boxes **must set `color:` explicitly** — a dark background without it
  inherits the theme's dark text and renders invisible.
- Live prices: NaN-harden every fetch. A NaN close is still a float and passes an
  `is not None` check, then poisons every downstream total. Pattern:
  `close = h["Close"].dropna()`, then fall back price → `last_prices` → cost basis.

## Paper-trading system

Six strategies, each with `*_ledger.csv` + `*_state.json`, advanced by
`run_daily_update.py` (Windows Task Scheduler, ~6 PM). `ENGINES` in that file is the
registry; `TRACKED_GLOBS` controls what gets auto-committed.

Adding a strategy means touching four registries:
1. `run_daily_update.py` → `ENGINES`
2. `event_log.py` → `STRATS`
3. `pages/9_Portfolio_Analytics.py` → `PORTFOLIOS`
4. a page in `pages/`

**RRG is registered in 2–4 but deliberately NOT in `ENGINES`** — see below.

## Research standards

This code may eventually trade real money, so validation is not decoration:

- Judge everything against **SPY**, and against a **measured** baseline — never assume
  a 50% hit rate (excess returns vs a cap-weighted index are right-skewed with a
  negative median; the real baseline is ~49%).
- `momentum_daily_prices.csv` is **today's** S&P 500 backfilled → survivorship bias.
  Sector ETFs are clean. Say which one a result rests on.
- Overlapping forward returns inflate naive t-stats (3.7× at 21d, 6.5× at 63d). Use
  Newey-West, or test a portfolio whose returns don't overlap.
- With a parameter sweep, `E[max|t|] ≈ 3` under the pure null — **|t| < 3 is noise**.
  Report the parameter surface (median, sign agreement), never the best cell.
- **A null result is a valid deliverable.** Two signals have now failed here: the RRG
  filter in `combined_backtest.py` (Sharpe 0.639 → 0.573) and the full RRG framework
  (1/9 pre-registered criteria; walk-forward $1 → $0.98). Report that plainly rather
  than searching for a specification that looks better.

## Not financial advice

Paper trading only. Never place real orders or move money. No personalized investment
advice — the user is not a client and I am not a licensed advisor.
