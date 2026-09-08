/** Credit ETFs for the Terminal dashboard's Fixed Income panel, split into government and corporate tables. */
export const GOVT_CREDIT_ETFS: { name: string; ticker: string }[] = [
  { name: "1-3Y Treasury", ticker: "SHY" },
  { name: "7-10Y Treasury", ticker: "IEF" },
  { name: "20+Y Treasury", ticker: "TLT" },
  { name: "US Treasury (broad)", ticker: "GOVT" },
];

export const CORP_CREDIT_ETFS: { name: string; ticker: string }[] = [
  { name: "Inv-Grade Corp", ticker: "LQD" },
  { name: "Interm. Corp", ticker: "VCIT" },
  { name: "High Yield Corp", ticker: "HYG" },
  { name: "High Yield Bond", ticker: "JNK" },
];
