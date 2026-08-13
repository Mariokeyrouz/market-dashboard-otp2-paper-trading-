/**
 * The Regime Playbook tile translates a hinge classification into position
 * tilts — inherently editorial/opinionated content (this repo's own
 * `derive.ts`/footer already labels the whole dashboard "opinionated,
 * style-dependent classification"). What's live is *which* classification
 * applies (from `classifyHinge()`, fed by real yields); the playbook text
 * for each possible classification is a small static lookup, keyed off the
 * exact label strings `classifyHinge` returns.
 */
import type { PlaybookRow } from "../types";

export const PLAYBOOK_BY_CLASSIFICATION: Record<string, PlaybookRow[]> = {
  "Inflation Scare": [
    { side: "SHORT", asset: "Long-duration USTs", note: "BE-led selloff", color: "var(--red)" },
    { side: "LONG", asset: "Gold / TIPS", note: "real-rate hedge", color: "var(--green)" },
    { side: "LONG", asset: "Energy / commods", note: "impulse tailwind", color: "var(--green)" },
    { side: "FADE", asset: "Long-duration tech", note: "rate-sensitive", color: "var(--amber)" },
  ],
  "Growth / Tightening Shock": [
    { side: "SHORT", asset: "Cyclical equities", note: "growth-shock led", color: "var(--red)" },
    { side: "SHORT", asset: "Credit (IG & HY)", note: "tightening-sensitive", color: "var(--red)" },
    { side: "LONG", asset: "Defensives", note: "real-yield led selloff", color: "var(--green)" },
    { side: "FADE", asset: "Long-duration growth", note: "discount-rate hit twice", color: "var(--amber)" },
  ],
  "Mixed / Neutral": [
    { side: "NEUTRAL", asset: "Duration", note: "no dominant leg", color: "var(--amber)" },
    { side: "WATCH", asset: "Breakeven vs. real split", note: "wait for separation", color: "var(--amber)" },
    { side: "NEUTRAL", asset: "Credit beta", note: "no clean read", color: "var(--amber)" },
  ],
};

export function playbookFor(classificationLabel: string): PlaybookRow[] {
  return PLAYBOOK_BY_CLASSIFICATION[classificationLabel] ?? PLAYBOOK_BY_CLASSIFICATION["Mixed / Neutral"];
}
