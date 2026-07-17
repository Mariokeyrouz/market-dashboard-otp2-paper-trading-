"use client";

import { useEffect, useState } from "react";
import { REGIONS, REGION_LABELS, type Region } from "@/lib/data/types";
import { THEME_LABELS, useDashStore, type Theme } from "@/lib/store";
import { useDerived } from "../DataContext";
import { MONO, SERIF } from "../ui";
import ElementLibrary from "./ElementLibrary";

function useClock() {
  const [clock, setClock] = useState("--:--:--");
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setClock(now.toLocaleTimeString("en-US", { hour12: false }));
      const h = now.getHours();
      const day = now.getDay();
      setOpen(day >= 1 && day <= 5 && h >= 9 && h < 16);
    };
    tick();
    const iv = setInterval(tick, 1000);
    return () => clearInterval(iv);
  }, []);
  return { clock, open };
}

const selectStyle: React.CSSProperties = {
  fontFamily: "var(--font-plex-sans), sans-serif",
  fontSize: 13,
  fontWeight: 600,
  color: "var(--ink)",
  background: "var(--tile)",
  border: "1px solid var(--control-border)",
  borderRadius: 7,
  padding: "6px 30px 6px 12px",
  lineHeight: 1,
};

const btnStyle = (accent: string): React.CSSProperties => ({
  fontFamily: "var(--font-plex-sans), sans-serif",
  fontSize: 12.5,
  fontWeight: 600,
  color: accent,
  background: "var(--tile)",
  border: `1px solid ${accent}`,
  borderRadius: 7,
  padding: "7px 14px",
  cursor: "pointer",
});

/**
 * `showControls` is false once the left rail is on screen: the rail owns the
 * POV switcher and the customize actions, and duplicating them here would give
 * the same state two places to be changed from. Theme stays — it's a
 * preference, not navigation.
 */
export default function Header({ showControls = true }: { showControls?: boolean }) {
  const v = useDerived();
  const { clock, open } = useClock();
  const region = useDashStore((s) => s.region);
  const setRegion = useDashStore((s) => s.setRegion);
  const theme = useDashStore((s) => s.theme);
  const setTheme = useDashStore((s) => s.setTheme);
  const edit = useDashStore((s) => s.editMode);
  const setEditMode = useDashStore((s) => s.setEditMode);
  const resetLayout = useDashStore((s) => s.resetLayout);
  const mktColor = open ? "var(--green)" : "var(--red)";

  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 24, marginBottom: 7 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div
            style={{
              width: 40, height: 40, borderRadius: 9, background: "var(--ink)", color: "var(--canvas)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontFamily: SERIF, fontSize: 24, fontWeight: 600,
            }}
          >
            M
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ fontFamily: SERIF, fontSize: 22, fontWeight: 600, letterSpacing: "-.01em", lineHeight: 1 }}>
                Macro Signal Dashboard
              </div>
              <span
                style={{
                  fontFamily: MONO, fontSize: 11, padding: "3px 7px",
                  border: "1px solid var(--control-border)", borderRadius: 5, color: "var(--muted)",
                }}
              >
                OTP2.0
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 6 }}>
              {showControls && (
                <>
                  <span style={{ fontSize: 10, letterSpacing: ".14em", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>
                    Region
                  </span>
                  <div style={{ position: "relative" }}>
                    <select
                      className="mws-select"
                      value={region}
                      onChange={(e) => setRegion(e.target.value as Region)}
                      style={selectStyle}
                    >
                      {REGIONS.map((r) => (
                        <option key={r} value={r}>
                          {REGION_LABELS[r]}
                        </option>
                      ))}
                    </select>
                    <span style={{ position: "absolute", right: 11, top: "50%", transform: "translateY(-50%)", pointerEvents: "none", color: "var(--muted)", fontSize: 9 }}>
                      ▼
                    </span>
                  </div>
                </>
              )}
              <span style={{ fontSize: 10, letterSpacing: ".14em", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>
                Theme
              </span>
              <div style={{ position: "relative" }}>
                <select
                  className="mws-select"
                  value={theme}
                  onChange={(e) => setTheme(e.target.value as Theme)}
                  style={selectStyle}
                >
                  {(Object.keys(THEME_LABELS) as Theme[]).map((t) => (
                    <option key={t} value={t}>
                      {THEME_LABELS[t]}
                    </option>
                  ))}
                </select>
                <span style={{ position: "absolute", right: 11, top: "50%", transform: "translateY(-50%)", pointerEvents: "none", color: "var(--muted)", fontSize: 9 }}>
                  ▼
                </span>
              </div>
            </div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {showControls &&
            (edit ? (
              <>
                <button style={btnStyle("var(--muted)")} onClick={resetLayout}>
                  Reset layout
                </button>
                <button style={{ ...btnStyle("var(--green)"), background: "rgba(94,122,59,.1)" }} onClick={() => setEditMode(false)}>
                  ✓ Done
                </button>
              </>
            ) : (
              <button style={btnStyle("var(--gold)")} onClick={() => setEditMode(true)}>
                ✎ Customize
              </button>
            ))}
          <div
            style={{
              display: "flex", alignItems: "center", gap: 14, background: "var(--tile)",
              border: "1px solid var(--tile-border)", borderRadius: 10, padding: "9px 15px",
            }}
          >
            <div style={{ textAlign: "right" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, justifyContent: "flex-end" }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: mktColor, animation: "mp-pulse 2s ease-in-out infinite" }} />
                <span style={{ fontSize: 10, letterSpacing: ".12em", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>
                  {v.exchange}
                </span>
              </div>
              <div style={{ fontFamily: MONO, fontSize: 20, fontWeight: 500, letterSpacing: ".02em", marginTop: 2 }}>{clock}</div>
            </div>
            <div style={{ fontFamily: MONO, fontSize: 12, fontWeight: 600, color: mktColor, letterSpacing: ".06em" }}>
              {open ? "OPEN" : "CLOSED"}
            </div>
          </div>
        </div>
      </div>
      {showControls && edit && <ElementLibrary />}
    </div>
  );
}
