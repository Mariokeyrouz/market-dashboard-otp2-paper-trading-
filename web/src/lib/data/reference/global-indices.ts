/**
 * Foreign equity index tickers for the Terminal dashboard's Global Markets
 * panel, grouped Developed/Emerging (Koyfin's own "Broad" sub-group is
 * dropped deliberately — no reliable broad-market ticker exists without an
 * arbitrary ETF-proxy label, and this project doesn't fabricate a bucket
 * label it can't back with a real symbol).
 */
export const GLOBAL_INDICES: { name: string; ticker: string; group: "Developed" | "Emerging" }[] = [
  { name: "Nikkei 225", ticker: "^N225", group: "Developed" },
  { name: "DAX", ticker: "^GDAXI", group: "Developed" },
  { name: "CAC 40", ticker: "^FCHI", group: "Developed" },
  { name: "FTSE 100", ticker: "^FTSE", group: "Developed" },
  { name: "ASX 200", ticker: "^AXJO", group: "Developed" },
  { name: "KOSPI", ticker: "^KS11", group: "Developed" },
  { name: "Hang Seng", ticker: "^HSI", group: "Emerging" },
  { name: "SENSEX", ticker: "^BSESN", group: "Emerging" },
  { name: "South Africa 40", ticker: "EZA", group: "Emerging" },
  { name: "IPC Mexico", ticker: "^MXX", group: "Emerging" },
  { name: "Bovespa", ticker: "^BVSP", group: "Emerging" },
];
