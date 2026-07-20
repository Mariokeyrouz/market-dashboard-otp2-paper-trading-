"use client";

import { THEME_LABELS, useDashStore, type Theme } from "@/lib/store";
import { MONO } from "../ui";

const THEMES: Theme[] = ["dark", "light"];

/**
 * Shared Black/White control. Expanded: a two-segment switch. Collapsed
 * (rail only): a single icon button that flips dark↔light — used by both
 * the left rail and the narrow-mode header so the two never diverge.
 */
export default function ThemeToggle({ collapsed = false }: { collapsed?: boolean }) {
  const theme = useDashStore((s) => s.theme);
  const setTheme = useDashStore((s) => s.setTheme);

  if (collapsed) {
    const next: Theme = theme === "dark" ? "light" : "dark";
    return (
      <button
        onClick={() => setTheme(next)}
        aria-label={`Switch to ${THEME_LABELS[next]} theme`}
        title={`Switch to ${THEME_LABELS[next]} theme`}
        style={{
          display: "flex", alignItems: "center", justifyContent: "center",
          width: "100%", cursor: "pointer", fontSize: 14,
          color: "var(--gold)", background: "transparent",
          border: "1px solid var(--control-border)", borderRadius: 7,
          padding: "6px 0",
        }}
      >
        ◐
      </button>
    );
  }

  return (
    <div
      role="group"
      aria-label="Theme"
      style={{ display: "flex", gap: 4 }}
    >
      {THEMES.map((t) => {
        const active = t === theme;
        return (
          <button
            key={t}
            onClick={() => setTheme(t)}
            aria-current={active}
            style={{
              flex: 1, textAlign: "center", cursor: "pointer",
              fontFamily: MONO, fontSize: 11, fontWeight: 700,
              color: active ? "var(--gold)" : "var(--body)",
              background: active ? "color-mix(in srgb, var(--gold) 13%, transparent)" : "transparent",
              border: `1px solid ${active ? "color-mix(in srgb, var(--gold) 45%, transparent)" : "var(--control-border)"}`,
              borderRadius: 7, padding: "6px 0",
            }}
          >
            {THEME_LABELS[t]}
          </button>
        );
      })}
    </div>
  );
}
