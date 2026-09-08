/**
 * Vanguard style-box ETFs for the Terminal dashboard's US Equity Factors 3x3
 * heatmap (size x style) — one coherent ETF family rather than mixing
 * providers across cells.
 */
export const STYLE_FACTOR_ETFS: { name: string; ticker: string; size: "Large" | "Mid" | "Small"; style: "Value" | "Blend" | "Growth" }[] = [
  { name: "Large Value", ticker: "VTV", size: "Large", style: "Value" },
  { name: "Large Blend", ticker: "VV", size: "Large", style: "Blend" },
  { name: "Large Growth", ticker: "VUG", size: "Large", style: "Growth" },
  { name: "Mid Value", ticker: "VOE", size: "Mid", style: "Value" },
  { name: "Mid Blend", ticker: "VO", size: "Mid", style: "Blend" },
  { name: "Mid Growth", ticker: "VOT", size: "Mid", style: "Growth" },
  { name: "Small Value", ticker: "VBR", size: "Small", style: "Value" },
  { name: "Small Blend", ticker: "VB", size: "Small", style: "Blend" },
  { name: "Small Growth", ticker: "VBK", size: "Small", style: "Growth" },
];
