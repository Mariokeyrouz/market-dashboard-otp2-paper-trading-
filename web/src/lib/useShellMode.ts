"use client";

import { useSyncExternalStore } from "react";

/**
 * How much chrome the viewport can afford.
 *
 * - `wide`   — left POV rail expanded + Logic docked on the right.
 * - `mid`    — left rail collapses to an icon strip; Logic falls back to its
 *              floating tab (the 320px dock simply doesn't fit).
 * - `narrow` — no rails at all; the header carries the controls, exactly as
 *              it did before the rails existed.
 */
export type ShellMode = "wide" | "mid" | "narrow";

/** 180 rail + 1820 grid + 320 dock + padding ≈ 2340; below that the dock goes. */
const WIDE_MIN = 1600;
const MID_MIN = 1200;

export const RAIL_W = 180;
export const RAIL_W_COLLAPSED = 56;
export const DOCK_W = 320;
/** The always-present right icon strip that toggles the dock. */
export const DOCK_RAIL_W = 38;

function subscribe(cb: () => void): () => void {
  window.addEventListener("resize", cb);
  return () => window.removeEventListener("resize", cb);
}

function snapshot(): ShellMode {
  const w = window.innerWidth;
  return w >= WIDE_MIN ? "wide" : w >= MID_MIN ? "mid" : "narrow";
}

export function useShellMode(): ShellMode {
  // Server snapshot is "narrow" so SSR emits the pre-rails layout; the page
  // already gates render on hydration, so this never flashes.
  return useSyncExternalStore(subscribe, snapshot, () => "narrow");
}
