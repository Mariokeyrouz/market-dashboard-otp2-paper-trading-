// Ported from OpenTerminal's web/components/Terminal.tsx, renamed
// OpenTerminalShell to reflect its role here: a full-screen takeover
// rendered in place of this app's own Header/LeftRail/DashboardGrid/etc (see
// web/src/app/page.tsx). Wraps everything in a `.ot-root` class so
// openterminal.css only ever applies inside this subtree, and provides its
// own React Query client via OpenTerminalProviders (kept local rather than
// global, since no other dashboard needs it).
"use client";

import { useEffect } from "react";
import "./openterminal.css";
import OpenTerminalProviders from "./OpenTerminalProviders";
import TopBar from "./TopBar";
import Sidebar from "./Sidebar";
import Workspace from "./Workspace";
import CommandPalette from "./CommandPalette";
import { useOpenTerminal } from "@/store/openterminal";

function OpenTerminalInner() {
  const setCommandOpen = useOpenTerminal((s) => s.setCommandOpen);
  const addWidget = useOpenTerminal((s) => s.addWidget);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommandOpen(true);
        return;
      }
      if (e.altKey) {
        const map: Record<string, () => void> = {
          "1": () => addWidget("chart"),
          "2": () => addWidget("quote"),
          "3": () => addWidget("news"),
          "4": () => addWidget("screener"),
          "5": () => addWidget("heatmap"),
          "6": () => addWidget("crypto"),
          "7": () => addWidget("options"),
          "8": () => addWidget("portfolio"),
          "9": () => addWidget("ai"),
        };
        const fn = map[e.key];
        if (fn) {
          e.preventDefault();
          fn();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setCommandOpen, addWidget]);

  return (
    <div className="flex flex-col h-screen">
      <TopBar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-auto">
          <Workspace />
        </main>
      </div>
      <CommandPalette />
    </div>
  );
}

export default function OpenTerminalShell() {
  return (
    <div className="ot-root">
      <OpenTerminalProviders>
        <OpenTerminalInner />
      </OpenTerminalProviders>
    </div>
  );
}
