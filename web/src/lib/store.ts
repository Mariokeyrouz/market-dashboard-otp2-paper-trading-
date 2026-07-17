import type { Layout, LayoutItem } from "react-grid-layout";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Region } from "./data/types";
import { DEFAULT_HIDDEN, ELEMENT_MAP } from "./elements/registry";
import { defaultLayout } from "./layout/defaults";

/** The default grid: every element that isn't hidden out of the box. */
const visibleDefaultLayout = (): LayoutItem[] =>
  defaultLayout().filter((l) => !DEFAULT_HIDDEN.includes(l.i));

export type Theme = "silver" | "dark" | "light";

export const THEME_LABELS: Record<Theme, string> = {
  silver: "Silver",
  dark: "Black",
  light: "White",
};

interface DashState {
  region: Region;
  theme: Theme;
  layout: LayoutItem[];
  hidden: string[];
  /**
   * Per-element POV override: elementId → region. An element not listed here
   * follows the global `region` lens.
   */
  pins: Record<string, Region>;
  editMode: boolean;
  /** Transient: the overlay drawer (narrow/mid screens). Not persisted. */
  logicOpen: boolean;
  /** Persisted: whether the right-hand Logic dock is expanded (wide screens). */
  dockOpen: boolean;
  setRegion: (r: Region) => void;
  setTheme: (t: Theme) => void;
  setLayout: (l: Layout) => void;
  hideElement: (id: string) => void;
  showElement: (id: string) => void;
  setPin: (id: string, r: Region) => void;
  clearPin: (id: string) => void;
  resetLayout: () => void;
  setEditMode: (b: boolean) => void;
  setLogicOpen: (b: boolean) => void;
  setDockOpen: (b: boolean) => void;
}

const strip = (l: readonly LayoutItem[]): LayoutItem[] =>
  l.map(({ i, x, y, w, h, minW, minH }) => ({ i, x, y, w, h, minW, minH }));

export const useDashStore = create<DashState>()(
  persist(
    (set) => ({
      region: "US",
      theme: "silver",
      layout: visibleDefaultLayout(),
      hidden: [...DEFAULT_HIDDEN],
      pins: {},
      editMode: false,
      logicOpen: false,
      dockOpen: false,
      setRegion: (region) => set({ region }),
      setTheme: (theme) => set({ theme }),
      setLayout: (layout) => set({ layout: strip(layout) }),
      hideElement: (id) =>
        set((s) => ({
          hidden: [...s.hidden.filter((x) => x !== id), id],
          layout: s.layout.filter((l) => l.i !== id),
        })),
      showElement: (id) =>
        set((s) => {
          const def = ELEMENT_MAP.get(id);
          if (!def) return s;
          const bottom = s.layout.reduce((m, l) => Math.max(m, l.y + l.h), 0);
          return {
            hidden: s.hidden.filter((x) => x !== id),
            // Drop any stale entry for this id first — a duplicate key breaks the grid.
            layout: [...s.layout.filter((l) => l.i !== id), { i: id, ...def.defaultLayout, x: 0, y: bottom }],
          };
        }),
      setPin: (id, r) => set((s) => ({ pins: { ...s.pins, [id]: r } })),
      clearPin: (id) =>
        set((s) => {
          const pins = { ...s.pins };
          delete pins[id];
          return { pins };
        }),
      // Restores the default arrangement — including the default hidden set,
      // since the one-screen default IS the arrangement. POV pins are
      // bindings, not layout, so they deliberately survive a reset.
      resetLayout: () => set({ layout: visibleDefaultLayout(), hidden: [...DEFAULT_HIDDEN] }),
      setEditMode: (editMode) => set({ editMode }),
      setLogicOpen: (logicOpen) => set({ logicOpen }),
      setDockOpen: (dockOpen) => set({ dockOpen }),
    }),
    {
      name: "mws_state_v1",
      // dockOpen persists (a layout preference) but logicOpen deliberately
      // does not — the overlay is transient, and persisting it would slide the
      // drawer open over the dashboard on load after you'd narrowed the window.
      partialize: (s) => ({
        region: s.region, theme: s.theme, layout: s.layout, hidden: s.hidden,
        pins: s.pins, dockOpen: s.dockOpen,
      }),
    },
  ),
);
