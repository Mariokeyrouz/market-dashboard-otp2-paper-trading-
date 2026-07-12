/** Region lens for the whole dashboard. */
export type Region = "US" | "EU" | "CN" | "JP" | "GL";

export const REGIONS: Region[] = ["US", "EU", "CN", "JP", "GL"];

export const REGION_LABELS: Record<Region, string> = {
  US: "United States",
  EU: "Euro Area",
  CN: "China",
  JP: "Japan",
  GL: "Global (agg)",
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

export interface CbMeeting {
  name: string;
  days: number;
  date: string;
  action: string;
  prob: number;
  move: string;
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
  tripwires: TripwireRaw[];
  cross: [string, number, number, number, number][];
  cb: CbMeeting;
  releases: [string, string, string][];
  positioning: [string, number][];
}

/** Extra per-region dataset (mirrors the design handoff's EXTRA map). */
export interface ExtraData {
  labor: [string, string, string][];
  fx: [string, number, number][];
  commods: [string, string, number][];
  esi: number;
  esiTrend: number[];
  surprises: [string, number][];
}

export type RegionData = CoreData & ExtraData;
