/**
 * Region lens for the whole dashboard. Narrowed to US-only for now — EU/CN/JP/GL
 * had no free live data source good enough to ship without falling back to
 * mock, and the instruction here is no mock data, reachable or not. Re-widen
 * this union (and REGIONS/REGION_LABELS below) when a region gets a real
 * live source in build-macro-data.ts.
 */
export type Region = "US";

export const REGIONS: Region[] = ["US"];

export const REGION_LABELS: Record<Region, string> = {
  US: "United States",
};

export interface RegimeSeg {
  label: string;
  color: string;
  w: number;
}

export interface TripwireRaw {
  label: string;
  tag: string;
  val: string;
  chg: number | null;
  unit?: string;
  state: string;
  note: string;
  tone: string;
}

export interface PlaybookRow {
  side: string;
  asset: string;
  note: string;
  color: string;
}

/**
 * `action`/`prob`/`move` (a market-implied rate-path guess) were dropped —
 * no free live source exists for that (CME FedWatch-style data is paid).
 * `CbCountdown` now shows the actual live Fed Funds target range
 * (`CoreData.policy`) alongside the meeting countdown instead.
 */
export interface CbMeeting {
  name: string;
  days: number;
  date: string;
}

/** Core per-region dataset (mirrors the design handoff's DATA map). */
export interface CoreData {
  exchange: string;
  regimeLabel: string;
  regimeColor: string;
  regimeDays: number;
  regimeSince: string;
  history: RegimeSeg[];
  inflation: string;
  inflationSub: string;
  growth: number;
  growthSub: string;
  policy: string;
  policySub: string;
  cond: number;
  condSub: string;
  hingeDef: string;
  nom: number[];
  real: number[];
  be: number[];
  dNom: number;
  dReal: number;
  dBe: number;
  classLabel: string;
  classDesc: string;
  classTags: string[];
  classMover: string;
  oilName: string;
  oilVal: string;
  oilChg: number;
  oilSpark: number[];
  playbook: PlaybookRow[];
  curve: [string, number][];
  curveDate: string;
  curvePrev: [string, number][];
  curvePrevDate: string;
  tripwires: TripwireRaw[];
  cross: [string, number, number, number, number][];
  cb: CbMeeting;
  releases: [string, string, string][];
}

/**
 * Extra per-region dataset (mirrors the design handoff's EXTRA map).
 * `esi`/`esiTrend`/`surprises` (a Citi/Bloomberg-style Economic Surprise
 * Index) were dropped — no free live equivalent exists.
 */
export interface ExtraData {
  labor: [string, string, string][];
  fx: [string, number, number][];
  commods: [string, string, number][];
}

export type RegionData = CoreData & ExtraData;
