/**
 * Aggregates every live-data bucket into one CoreData+ExtraData (US region),
 * the same shape `getRegionData("US")` (the mock) has always returned — so
 * `deriveAllFrom` and every macro element component need no changes.
 *
 * Same three-layer design as `build-equity-data.ts`: each bucket is fetched
 * independently via `Promise.allSettled`, a failed bucket falls back to the
 * matching slice of the mock, and `meta.stale` records which buckets fell
 * back so `page.tsx` can show an honest status badge.
 */
import { classifyHinge, classMoverLabel } from "./classify/hinge";
import { computeRegimeHistory } from "./classify/regime-history";
import { curveState, volCurveState } from "./classify/tripwires";
import { fetchFredSeries, indexNearYearStartFred, type FredObservation } from "./providers/fred";
import { fetchYahooChart, indexNearYearStart } from "./providers/yahoo-chart";
import { fetchYahooSparkBatch } from "./providers/yahoo-spark-batch";
import { fetchTreasuryCurve, MACRO_TENORS } from "./providers/treasury-curve";
import { getRegionData } from "./mock";
import { ISM_MANUFACTURING_PMI, latestIsmPair } from "./reference/ism-history";
import { nextFomcMeeting } from "./reference/fomc-dates";
import { buildReleasesList } from "./reference/macro-calendar";
import { playbookFor } from "./reference/playbook-by-classification";
import type { CoreData, ExtraData } from "./types";

export type MacroStaleBucket =
  | "hinge" | "cpi" | "fedFunds" | "fci" | "curve" | "tripwires" | "oil" | "cross" | "commods" | "fx" | "labor";

export interface MacroFetchMeta {
  fetchedAt: string;
  stale: Record<MacroStaleBucket, boolean>;
  degraded: boolean;
}

type BucketResult<T> = { ok: true; value: T } | { ok: false };

async function settle<T>(fn: () => Promise<T>): Promise<BucketResult<T>> {
  try {
    return { ok: true, value: await fn() };
  } catch {
    return { ok: false };
  }
}

const pct = (a: number, b: number) => ((a - b) / b) * 100;

// ---------- hinge (10Y nominal/real/breakeven + classification + playbook) ----------
async function fetchHingeBucket(): Promise<Pick<CoreData, "nom" | "real" | "be" | "dNom" | "dReal" | "dBe" | "classLabel" | "classDesc" | "classTags" | "classMover" | "playbook">> {
  const LOOKBACK = 5; // business days, matches macro_data.py's DEFAULT_LOOKBACK_DAYS
  // ~3 months of daily points — 10 (≈2 weeks) read as three nearly-flat
  // lines with almost no texture; this gives the chart something to show.
  const DISPLAY_POINTS = 60;
  const [nomObs, realObs, beObs] = await Promise.all([
    fetchFredSeries("DGS10", 0.5, 3600),
    fetchFredSeries("DFII10", 0.5, 3600),
    fetchFredSeries("T10YIE", 0.5, 3600),
  ]);
  const n = Math.min(nomObs.length, realObs.length, beObs.length);
  if (n < LOOKBACK + 1) throw new Error("hinge: insufficient history");
  const nom = nomObs.slice(-n).map((o) => o.value).slice(-DISPLAY_POINTS);
  const real = realObs.slice(-n).map((o) => o.value).slice(-DISPLAY_POINTS);
  const be = beObs.slice(-n).map((o) => o.value).slice(-DISPLAY_POINTS);
  const dNom = nomObs[nomObs.length - 1].value - nomObs[nomObs.length - 1 - LOOKBACK].value;
  const dReal = realObs[realObs.length - 1].value - realObs[realObs.length - 1 - LOOKBACK].value;
  const dBe = beObs[beObs.length - 1].value - beObs[beObs.length - 1 - LOOKBACK].value;

  const cls = classifyHinge({ nominalChg: dNom, realChg: dReal, breakevenChg: dBe });
  return {
    nom, real, be, dNom, dReal, dBe,
    classLabel: cls.label, classDesc: cls.note, classTags: cls.tags, classMover: classMoverLabel(cls.dominant),
    playbook: playbookFor(cls.label),
  };
}

// ---------- CPI + regime classification (share the same underlying series) ----------
async function fetchCpiBucket(): Promise<Pick<CoreData, "inflation" | "inflationSub" | "regimeLabel" | "regimeColor" | "regimeDays" | "regimeSince" | "history">> {
  const [headlineObs, coreObs] = await Promise.all([
    fetchFredSeries("CPIAUCSL", 3, 21600),
    fetchFredSeries("CPILFESL", 3, 21600),
  ]);
  if (headlineObs.length < 13 || coreObs.length < 13) throw new Error("cpi: insufficient history");
  const yoy = (obs: FredObservation[]) => (obs[obs.length - 1].value / obs[obs.length - 13].value - 1) * 100;
  const headlineYoy = yoy(headlineObs);
  const coreYoy = yoy(coreObs);

  const regime = computeRegimeHistory(headlineObs, ISM_MANUFACTURING_PMI, new Date());

  return {
    inflation: headlineYoy.toFixed(1) + "%",
    inflationSub: `core ${coreYoy.toFixed(1)}% · ${regime.label === "Stagflation" ? "sticky" : "trending"}`,
    regimeLabel: regime.label, regimeColor: regime.color,
    regimeDays: regime.regimeDays, regimeSince: regime.regimeSince, history: regime.history,
  };
}

// ---------- Fed Funds target range ----------
async function fetchFedFundsBucket(): Promise<Pick<CoreData, "policy" | "policySub">> {
  const [lowObs, highObs] = await Promise.all([
    fetchFredSeries("DFEDTARL", 0.5, 21600),
    fetchFredSeries("DFEDTARU", 0.5, 21600),
  ]);
  const low = lowObs[lowObs.length - 1].value;
  const high = highObs[highObs.length - 1].value;
  return { policy: `${low.toFixed(2)}–${high.toFixed(2)}%`, policySub: "Fed Funds · effective target range" };
}

// ---------- Financial Conditions Index ----------
async function fetchFciBucket(): Promise<Pick<CoreData, "cond" | "condSub">> {
  const obs = await fetchFredSeries("NFCI", 0.5, 21600);
  const cond = obs[obs.length - 1].value;
  return { cond, condSub: cond >= 0 ? "FCI · tighter than avg" : "FCI · looser than avg" };
}

// ---------- yield curve ----------
async function fetchCurveBucket(): Promise<Pick<CoreData, "curve">> {
  return { curve: await fetchTreasuryCurve(MACRO_TENORS) };
}

// ---------- tripwires ----------
async function fetchTripwiresBucket(): Promise<Pick<CoreData, "tripwires">> {
  const [hyObs, vix, vix3m, dxy, t10y2yObs] = await Promise.all([
    fetchFredSeries("BAMLH0A0HYM2", 0.2, 3600),
    fetchYahooChart("^VIX", "5d", "1d", 180),
    fetchYahooChart("^VIX3M", "5d", "1d", 180),
    fetchYahooChart("DX-Y.NYB", "5d", "1d", 180),
    fetchFredSeries("T10Y2Y", 0.2, 3600),
  ]);
  const hy = hyObs[hyObs.length - 1].value;
  const hyChg = hy - hyObs[hyObs.length - 2].value;
  const vol = volCurveState(vix.regularMarketPrice, vix3m.regularMarketPrice);
  const dxyChg = pct(dxy.regularMarketPrice, dxy.previousClose);
  const slope = t10y2yObs[t10y2yObs.length - 1].value;
  const slopeChg = slope - t10y2yObs[t10y2yObs.length - 2].value;
  const curve = curveState(slope);

  return {
    tripwires: [
      { label: "Credit · HY OAS", tag: "Leading tell for equity stress", val: hy.toFixed(2) + "%", chg: hyChg, unit: " pp", state: "", note: "Widening = rising stress.", tone: hyChg >= 0 ? "var(--amber)" : "var(--green)" },
      { label: "Equity Vol · VIX", tag: "Risk-on / risk-off tripwire", val: vix.regularMarketPrice.toFixed(1), chg: null, state: vol.label, note: vol.note, tone: vol.color },
      { label: "Dollar · DXY", tag: "Global liquidity valve", val: dxy.regularMarketPrice.toFixed(1), chg: dxyChg, state: "", note: "Stronger USD tightens conditions abroad.", tone: dxyChg >= 0 ? "var(--amber)" : "var(--green)" },
      { label: "Curve · 2s10s", tag: "Late-cycle / recession watch", val: (slope >= 0 ? "+" : "") + slope.toFixed(2), chg: slopeChg, state: curve.label, note: curve.note, tone: curve.color },
    ],
  };
}

// ---------- oil (hinge impulse) ----------
async function fetchOilBucket(): Promise<Pick<CoreData, "oilName" | "oilVal" | "oilChg" | "oilSpark">> {
  const wti = await fetchYahooChart("CL=F", "1mo", "1d", 180);
  const chg = pct(wti.regularMarketPrice, wti.previousClose);
  return {
    oilName: "Oil · WTI", oilVal: wti.regularMarketPrice.toFixed(2), oilChg: chg,
    oilSpark: wti.closes.slice(-7),
  };
}

// ---------- cross-asset heatmap ----------
const CROSS_YAHOO: [string, string][] = [
  ["^GSPC", "S&P 500"], ["^NDX", "Nasdaq 100"], ["LQD", "IG Credit"], ["HYG", "HY Credit"],
  ["DX-Y.NYB", "USD (DXY)"], ["GC=F", "Gold"], ["BZ=F", "Brent"], ["HG=F", "Copper"],
];

function chartChanges(closes: number[], timestamps: number[]) {
  // Yahoo occasionally returns a near-empty series for a thin cross (e.g. USDCNH=X
  // returned exactly 1 point during testing, despite range=1y) — fail loudly
  // here so the bucket falls back, rather than silently computing NaN.
  if (closes.length < 25) throw new Error(`chartChanges: too few points (${closes.length})`);
  const last = closes.length - 1;
  const d1 = pct(closes[last], closes[last - 1]);
  const d1w = pct(closes[last], closes[Math.max(0, last - 5)]);
  const d1m = pct(closes[last], closes[Math.max(0, last - 21)]);
  const ytdIdx = indexNearYearStart(timestamps, new Date(timestamps[last] * 1000).getUTCFullYear());
  const ytd = pct(closes[last], closes[ytdIdx]);
  return [d1, d1w, d1m, ytd] as [number, number, number, number];
}

async function fetchCrossBucket(): Promise<Pick<CoreData, "cross">> {
  const [yahooResults, ust10y] = await Promise.all([
    Promise.all(CROSS_YAHOO.map(([symbol]) => fetchYahooChart(symbol, "1y", "1d", 180))),
    fetchFredSeries("DGS10", 1.2, 3600),
  ]);
  const cross: CoreData["cross"] = yahooResults.map((s, i) => {
    const [d1, d1w, d1m, ytd] = chartChanges(s.closes, s.timestamps);
    return [CROSS_YAHOO[i][1], d1, d1w, d1m, ytd];
  });
  const ustLast = ust10y.length - 1;
  const ustYtdIdx = indexNearYearStartFred(ust10y, new Date().getFullYear());
  const ustLevel = ust10y[ustLast].value;
  cross.push([
    "UST 10Y",
    ustLevel - ust10y[ustLast - 1].value,
    ustLevel - ust10y[Math.max(0, ustLast - 5)].value,
    ustLevel - ust10y[Math.max(0, ustLast - 21)].value,
    ustLevel - ust10y[ustYtdIdx].value,
  ]);
  return { cross };
}

// ---------- commodities (same 5 tickers as the equity dashboard) ----------
const COMMOD_TICKERS: [string, string][] = [
  ["CL=F", "WTI Crude"], ["BZ=F", "Brent"], ["GC=F", "Gold"], ["HG=F", "Copper"], ["NG=F", "Nat Gas"],
];

async function fetchCommodsBucket(): Promise<Pick<ExtraData, "commods">> {
  const { quotes, failedChunks, totalChunks } = await fetchYahooSparkBatch(COMMOD_TICKERS.map(([sym]) => sym));
  if (failedChunks === totalChunks) throw new Error("commods: batch fetch failed");
  const commods: ExtraData["commods"] = COMMOD_TICKERS.map(([symbol, name]) => {
    const q = quotes.get(symbol);
    if (!q) throw new Error(`commods: missing ${symbol}`);
    const chgPct = pct(q.price, q.previousClose);
    return [name, q.price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }), chgPct];
  });
  return { commods };
}

// ---------- FX ----------
// USDCNH=X (offshore yuan) returned only 1 data point from Yahoo's chart
// endpoint during testing, despite range=1y — CNY=X (onshore) has full
// history, so that's what's fetched; labeled accurately as USD/CNY rather
// than claiming the offshore rate.
const FX_PAIRS: [string, string][] = [
  ["EURUSD=X", "EUR/USD"], ["JPY=X", "USD/JPY"], ["GBPUSD=X", "GBP/USD"],
  ["CNY=X", "USD/CNY"], ["CHF=X", "USD/CHF"], ["AUDUSD=X", "AUD/USD"],
];

async function fetchFxBucket(): Promise<Pick<ExtraData, "fx">> {
  const series = await Promise.all(FX_PAIRS.map(([symbol]) => fetchYahooChart(symbol, "1y", "1d", 180)));
  const fx: ExtraData["fx"] = series.map((s, i) => {
    if (s.closes.length < 25) throw new Error(`fx: too few points for ${FX_PAIRS[i][1]} (${s.closes.length})`);
    const last = s.closes.length - 1;
    const d1 = pct(s.closes[last], s.closes[last - 1]);
    const ytdIdx = indexNearYearStart(s.timestamps, new Date(s.timestamps[last] * 1000).getUTCFullYear());
    const ytd = pct(s.closes[last], s.closes[ytdIdx]);
    return [FX_PAIRS[i][1], d1, ytd];
  });
  return { fx };
}

// ---------- labor market ----------
async function fetchLaborBucket(): Promise<Pick<ExtraData, "labor">> {
  const [payems, unrate, ahe, icsa, civpart, jtsjol] = await Promise.all([
    fetchFredSeries("PAYEMS", 0.5, 21600),
    fetchFredSeries("UNRATE", 0.5, 21600),
    fetchFredSeries("CES0500000003", 2, 21600),
    fetchFredSeries("ICSA", 0.3, 21600),
    fetchFredSeries("CIVPART", 0.5, 21600),
    fetchFredSeries("JTSJOL", 0.5, 21600),
  ]);
  const diff = (obs: FredObservation[], back = 1) => obs[obs.length - 1].value - obs[obs.length - 1 - back].value;
  const fmtK = (v: number) => (v >= 0 ? "+" : "") + Math.round(v) + "k";

  const payemsDiffNow = diff(payems);
  const payemsDiffPrior = diff(payems, 2) - diff(payems); // prior month's own MoM diff
  const aheYoy = (i: number): number => {
    const cur = ahe.length - 1 - i;
    const prior = cur - 12;
    return prior >= 0 ? (ahe[cur].value / ahe[prior].value - 1) * 100 : NaN;
  };
  const aheYoyNow = aheYoy(0);
  const aheYoyPriorRaw = aheYoy(1);
  const aheYoyPrior = Number.isFinite(aheYoyPriorRaw) ? aheYoyPriorRaw : aheYoyNow;
  if (!Number.isFinite(aheYoyNow)) throw new Error("labor: insufficient AHE history for YoY");

  const icsaLast = icsa[icsa.length - 1].value;
  const icsaDiff = icsaLast - icsa[icsa.length - 2].value;

  const jtsjolLast = jtsjol[jtsjol.length - 1].value;
  const jtsjolDiff = jtsjolLast - jtsjol[jtsjol.length - 2].value;

  const civpartDiff = diff(civpart);

  const labor: ExtraData["labor"] = [
    ["Nonfarm Payrolls", fmtK(payemsDiffNow), `prev ${fmtK(payemsDiffPrior)}`],
    ["Unemployment", unrate[unrate.length - 1].value.toFixed(1) + "%", (diff(unrate) >= 0 ? "+" : "") + diff(unrate).toFixed(1) + " m/m"],
    ["Avg Hourly Earn", aheYoyNow.toFixed(1) + "% y/y", (aheYoyNow - aheYoyPrior >= 0 ? "+" : "") + (aheYoyNow - aheYoyPrior).toFixed(1) + " pp"],
    ["Jobless Claims", Math.round(icsaLast / 1000) + "k", (icsaDiff >= 0 ? "+" : "") + Math.round(icsaDiff / 1000) + "k w/w"],
    ["Participation", civpart[civpart.length - 1].value.toFixed(1) + "%", Math.abs(civpartDiff) < 0.05 ? "flat" : (civpartDiff >= 0 ? "+" : "") + civpartDiff.toFixed(1)],
    ["JOLTS Openings", (jtsjolLast / 1000).toFixed(2) + "M", (jtsjolDiff >= 0 ? "+" : "") + (jtsjolDiff / 1000).toFixed(2) + "M"],
  ];
  return { labor };
}

export async function buildMacroData(): Promise<{ data: CoreData & ExtraData; meta: MacroFetchMeta }> {
  const mock = getRegionData("US");
  const now = new Date();

  const [hinge, cpi, fedFunds, fci, curve, tripwires, oil, cross, commods, fx, labor] = await Promise.all([
    settle(fetchHingeBucket),
    settle(fetchCpiBucket),
    settle(fetchFedFundsBucket),
    settle(fetchFciBucket),
    settle(fetchCurveBucket),
    settle(fetchTripwiresBucket),
    settle(fetchOilBucket),
    settle(fetchCrossBucket),
    settle(fetchCommodsBucket),
    settle(fetchFxBucket),
    settle(fetchLaborBucket),
  ]);

  const stale: Record<MacroStaleBucket, boolean> = {
    hinge: !hinge.ok, cpi: !cpi.ok, fedFunds: !fedFunds.ok, fci: !fci.ok, curve: !curve.ok,
    tripwires: !tripwires.ok, oil: !oil.ok, cross: !cross.ok, commods: !commods.ok, fx: !fx.ok, labor: !labor.ok,
  };

  const cb: CoreData["cb"] = (() => {
    const next = nextFomcMeeting(now);
    return next
      ? { name: "FOMC · Federal Reserve", days: next.daysFromNow, date: next.date }
      : mock.cb;
  })();

  const data: CoreData & ExtraData = {
    exchange: mock.exchange,
    hingeDef: mock.hingeDef,
    ...(hinge.ok ? hinge.value : { nom: mock.nom, real: mock.real, be: mock.be, dNom: mock.dNom, dReal: mock.dReal, dBe: mock.dBe, classLabel: mock.classLabel, classDesc: mock.classDesc, classTags: mock.classTags, classMover: mock.classMover, playbook: mock.playbook }),
    ...(cpi.ok ? cpi.value : { inflation: mock.inflation, inflationSub: mock.inflationSub, regimeLabel: mock.regimeLabel, regimeColor: mock.regimeColor, regimeDays: mock.regimeDays, regimeSince: mock.regimeSince, history: mock.history }),
    growth: latestIsmPair().latest,
    growthSub: "ISM mfg · last published print",
    ...(fedFunds.ok ? fedFunds.value : { policy: mock.policy, policySub: mock.policySub }),
    ...(fci.ok ? fci.value : { cond: mock.cond, condSub: mock.condSub }),
    ...(curve.ok ? curve.value : { curve: mock.curve }),
    ...(tripwires.ok ? tripwires.value : { tripwires: mock.tripwires }),
    ...(oil.ok ? oil.value : { oilName: mock.oilName, oilVal: mock.oilVal, oilChg: mock.oilChg, oilSpark: mock.oilSpark }),
    ...(cross.ok ? cross.value : { cross: mock.cross }),
    cb,
    releases: buildReleasesList(now, 5),
    ...(commods.ok ? commods.value : { commods: mock.commods }),
    ...(fx.ok ? fx.value : { fx: mock.fx }),
    ...(labor.ok ? labor.value : { labor: mock.labor }),
  };

  return {
    data,
    meta: {
      fetchedAt: now.toISOString(),
      stale,
      degraded: Object.values(stale).every(Boolean),
    },
  };
}
