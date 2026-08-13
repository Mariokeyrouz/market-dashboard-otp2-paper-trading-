/**
 * Classification palette. `macro_logic.py`'s classifiers use their own hex
 * palette (`COL_STAG = "#b5642d"` etc.) matched to the Streamlit app's static
 * theme. This app is dark/light theme-aware via CSS custom properties
 * (`derive.ts`'s GREEN/RED/AMBER use the same `var(--green)` etc. tokens
 * already), so these map each Python color to the *matching* token instead
 * of copying the literal hex — same visual intent, correct on both themes.
 */
export const COL_INFLATION = "var(--gold)"; // inflation-scare leg
export const COL_GROWTH = "var(--red)"; // growth/tightening shock
export const COL_NEUTRAL = "var(--muted)"; // mixed / no clear signal
export const COL_RISK_ON = "var(--green)";
export const COL_RISK_OFF = "var(--red)";
export const COL_STAG = "var(--amber)"; // stagflation
