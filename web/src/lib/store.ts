import type { Layout, LayoutItem } from "react-grid-layout";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import { DEFAULT_DASHBOARD_TYPE, DASHBOARD_TYPES, getDashboardDef, type DashboardType } from "./dashboards";
import { REGIONS, type Region } from "./data/types";
import { defaultLayout } from "./layout/defaults";

export type Theme = "dark" | "light";

export const THEME_LABELS: Record<Theme, string> = {
  dark: "Black",
  light: "White",
};

export type DensityOverride = "auto" | "compact" | "comfortable";

export interface SavedView {
  id: string;
  name: string;
  /** Inert for dashboard types with no region lens (e.g. equity) — always set for schema uniformity, simply unused there. */
  region: Region;
  layout: LayoutItem[];
  hidden: string[];
  createdAt: number;
}

/** Everything that's scoped to ONE dashboard type — a different grid arrangement per type. */
export interface PerDashboardState {
  layout: LayoutItem[];
  hidden: string[];
  savedViews: SavedView[];
  /** Transient: not persisted (see partialize) — a stale marker would misrepresent a since-edited layout on reload. */
  activeSavedViewId: string | null;
}

const strip = (l: readonly LayoutItem[]): LayoutItem[] =>
  l.map(({ i, x, y, w, h, minW, minH }) => ({ i, x, y, w, h, minW, minH }));

/** The default grid for one dashboard type: every element that isn't hidden out of the box. */
const freshDashboardState = (type: DashboardType): PerDashboardState => {
  const def = getDashboardDef(type);
  return {
    layout: defaultLayout(def.elements).filter((l) => !def.defaultHidden.includes(l.i)),
    hidden: [...def.defaultHidden],
    savedViews: [],
    activeSavedViewId: null,
  };
};

const freshAllDashboards = (): Record<DashboardType, PerDashboardState> =>
  Object.fromEntries(DASHBOARD_TYPES.map((d) => [d.id, freshDashboardState(d.id)])) as Record<DashboardType, PerDashboardState>;

interface DashState {
  region: Region;
  theme: Theme;
  /** Which dashboard is on screen — Macro, Equity, or a future type. */
  dashboardType: DashboardType;
  /** Per-dashboard-type layout/hidden/savedViews, keyed by DashboardType. */
  dashboards: Record<DashboardType, PerDashboardState>;
  /**
   * Per-element POV override: elementId → region. Only meaningful on
   * dashboard types with a region lens; harmlessly unused otherwise.
   */
  pins: Record<string, Region>;
  editMode: boolean;
  /** Transient: the overlay drawer (narrow/mid screens). Not persisted. */
  logicOpen: boolean;
  /** Persisted: whether the right-hand Logic dock is expanded (wide screens). */
  dockOpen: boolean;
  /** Persisted: whether the left-hand Element Library dock is expanded (wide screens). */
  libraryDockOpen: boolean;
  /** Transient: the Element Library overlay drawer (mid/narrow screens). Not persisted — same reasoning as `logicOpen`. */
  libraryOpen: boolean;
  /** Persisted: manual override that collapses the left rail in `wide` mode. */
  railCollapsed: boolean;
  /**
   * Persisted: manual override for tile density. "auto" defers to the grid's
   * own fit-to-height sizing (DashboardGrid); "compact"/"comfortable" force
   * DensityContext regardless of the fitted row height.
   */
  densityOverride: DensityOverride;
  setRegion: (r: Region) => void;
  setTheme: (t: Theme) => void;
  setDashboardType: (t: DashboardType) => void;
  setLayout: (l: Layout) => void;
  hideElement: (id: string) => void;
  showElement: (id: string) => void;
  setPin: (id: string, r: Region) => void;
  clearPin: (id: string) => void;
  resetLayout: () => void;
  setEditMode: (b: boolean) => void;
  setLogicOpen: (b: boolean) => void;
  setDockOpen: (b: boolean) => void;
  setRailCollapsed: (b: boolean) => void;
  setDensityOverride: (d: DensityOverride) => void;
  setLibraryDockOpen: (b: boolean) => void;
  setLibraryOpen: (b: boolean) => void;
  saveView: (name: string) => void;
  restoreView: (id: string) => void;
  deleteView: (id: string) => void;
  renameView: (id: string, name: string) => void;
}

// Centralizes `dashboards[dashboardType]` indexing in one place instead of
// repeating it at every call site (DashboardGrid, LeftRail, Header, etc).
export const selectLayout = (s: DashState) => s.dashboards[s.dashboardType].layout;
export const selectHidden = (s: DashState) => s.dashboards[s.dashboardType].hidden;
export const selectSavedViews = (s: DashState) => s.dashboards[s.dashboardType].savedViews;
export const selectActiveSavedViewId = (s: DashState) => s.dashboards[s.dashboardType].activeSavedViewId;

/** Update just the active dashboard type's slice, leaving the others untouched. */
const setCurrent = (
  set: (fn: (s: DashState) => Partial<DashState>) => void,
  patch: (cur: PerDashboardState, s: DashState) => Partial<PerDashboardState>,
) =>
  set((s) => ({
    dashboards: { ...s.dashboards, [s.dashboardType]: { ...s.dashboards[s.dashboardType], ...patch(s.dashboards[s.dashboardType], s) } },
  }));

export const useDashStore = create<DashState>()(
  persist(
    (set) => ({
      region: "US",
      theme: "dark",
      dashboardType: DEFAULT_DASHBOARD_TYPE,
      dashboards: freshAllDashboards(),
      pins: {},
      editMode: false,
      logicOpen: false,
      dockOpen: false,
      libraryDockOpen: false,
      libraryOpen: false,
      railCollapsed: false,
      densityOverride: "auto",
      setRegion: (region) => set({ region }),
      setTheme: (theme) => set({ theme }),
      // Never carry a drag/resize gesture from one dashboard's grid into an
      // entirely different element set.
      setDashboardType: (dashboardType) => set({ dashboardType, editMode: false }),
      setLayout: (layout) => setCurrent(set, () => ({ layout: strip(layout) })),
      hideElement: (id) =>
        setCurrent(set, (cur) => ({
          hidden: [...cur.hidden.filter((x) => x !== id), id],
          layout: cur.layout.filter((l) => l.i !== id),
        })),
      showElement: (id) =>
        setCurrent(set, (cur, s) => {
          const def = getDashboardDef(s.dashboardType).elementMap.get(id);
          if (!def) return cur;
          const bottom = cur.layout.reduce((m, l) => Math.max(m, l.y + l.h), 0);
          return {
            hidden: cur.hidden.filter((x) => x !== id),
            // Drop any stale entry for this id first — a duplicate key breaks the grid.
            layout: [...cur.layout.filter((l) => l.i !== id), { i: id, ...def.defaultLayout, x: 0, y: bottom }],
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
      resetLayout: () =>
        setCurrent(set, (_cur, s) => {
          const fresh = freshDashboardState(s.dashboardType);
          return { layout: fresh.layout, hidden: fresh.hidden };
        }),
      setEditMode: (editMode) => set({ editMode }),
      setLogicOpen: (logicOpen) => set({ logicOpen }),
      setDockOpen: (dockOpen) => set({ dockOpen }),
      setRailCollapsed: (railCollapsed) => set({ railCollapsed }),
      setDensityOverride: (densityOverride) => set({ densityOverride }),
      setLibraryDockOpen: (libraryDockOpen) => set({ libraryDockOpen }),
      setLibraryOpen: (libraryOpen) => set({ libraryOpen }),
      saveView: (name) =>
        setCurrent(set, (cur, s) => ({
          savedViews: [
            ...cur.savedViews,
            { id: crypto.randomUUID(), name, region: s.region, layout: strip(cur.layout), hidden: [...cur.hidden], createdAt: Date.now() },
          ],
        })),
      restoreView: (id) =>
        setCurrent(set, (cur) => {
          const view = cur.savedViews.find((v) => v.id === id);
          if (!view) return cur;
          return { layout: strip(view.layout), hidden: [...view.hidden], activeSavedViewId: id };
        }),
      deleteView: (id) =>
        setCurrent(set, (cur) => ({
          savedViews: cur.savedViews.filter((v) => v.id !== id),
          activeSavedViewId: cur.activeSavedViewId === id ? null : cur.activeSavedViewId,
        })),
      renameView: (id, name) =>
        setCurrent(set, (cur) => ({ savedViews: cur.savedViews.map((v) => (v.id === id ? { ...v, name } : v)) })),
    }),
    {
      name: "mws_state_v1",
      version: 5,
      // Pre-v1 browsers may have a persisted `theme` from a since-removed
      // third theme option — coerce anything that isn't a known theme to the
      // new default (Black) rather than letting it fall through to a dead
      // `data-theme` value with no CSS rule.
      migrate: (persisted, version) => {
        const state = persisted as (Record<string, unknown> & { theme?: string }) | undefined;
        if (version < 1 && state && state.theme !== "dark" && state.theme !== "light") {
          state.theme = "dark";
        }
        // v2 -> v3: layout/hidden/savedViews used to be flat, global fields —
        // one dashboard, one arrangement. Now every dashboard type gets its
        // own slice. Fold the old flat fields into "macro" (the only type
        // that existed pre-v3) and seed a fresh default for every other type.
        if (version < 3 && state) {
          const old = state as { layout?: LayoutItem[]; hidden?: string[]; savedViews?: SavedView[] };
          const dashboards = freshAllDashboards();
          if (old.layout) dashboards.macro.layout = old.layout;
          if (old.hidden) dashboards.macro.hidden = old.hidden;
          if (old.savedViews) dashboards.macro.savedViews = old.savedViews;
          state.dashboardType = DEFAULT_DASHBOARD_TYPE;
          state.dashboards = dashboards;
          delete state.layout;
          delete state.hidden;
          delete state.savedViews;
          delete state.activeSavedViewId;
        }
        // v3 -> v4: Commodities/FX Changes grew their default height (5->7,
        // 6->7 rows) because Comfortable density needs more room than they
        // were allotted — rows were rendering past the tile's clipped bottom
        // edge. Bump only untouched instances (still at the old default
        // dimensions) so a manually resized tile isn't silently overridden.
        if (version < 4 && state) {
          const dashboards = (state as { dashboards?: Record<string, { layout?: LayoutItem[] }> }).dashboards;
          const macroLayout = dashboards?.macro?.layout;
          if (macroLayout) {
            for (const l of macroLayout) {
              if (l.i === "commods" && l.h === 5) l.h = 7;
              if (l.i === "fx" && l.h === 6) l.h = 7;
            }
          }
        }
        // v4 -> v5: Equity's default layout was packed into uniform
        // full-height bands (51 rows total) with no interleaving slack like
        // Macro's, so it needed ~900px+ of viewport just to avoid scrolling.
        // Tightened every tile toward its comfortable minimum (51 -> 38
        // rows). Only replace an equity layout that's still exactly the old
        // untouched default — a manually resized/moved layout is left alone.
        if (version < 5 && state) {
          const dashboards = (state as { dashboards?: Record<string, { layout?: LayoutItem[] }> }).dashboards;
          const equityLayout = dashboards?.equity?.layout;
          const oldDefaultH: Record<string, number> = {
            "eq-vix": 11, "eq-concentration": 11, "eq-sectors": 11, "eq-movers": 11,
            "eq-indices": 11, "eq-curve": 9, "eq-oil": 9, "eq-calendar": 9,
          };
          const untouched =
            equityLayout &&
            equityLayout.length === Object.keys(oldDefaultH).length &&
            equityLayout.every((l) => oldDefaultH[l.i] === l.h);
          if (untouched && dashboards?.equity) {
            const def = getDashboardDef("equity");
            dashboards.equity.layout = defaultLayout(def.elements).filter((l) => !def.defaultHidden.includes(l.i));
          }
        }
        return state;
      },
      // A plain shallow merge would replace `dashboards` wholesale from
      // storage, leaving `activeSavedViewId` `undefined` instead of `null`
      // and crashing if a future dashboard type is missing from old storage.
      // Reconcile per-type instead, always resetting the transient field.
      merge: (persisted, current) => {
        const p = persisted as Partial<DashState> | undefined;
        if (!p) return current;
        const dashboards = { ...current.dashboards };
        for (const type of Object.keys(dashboards) as DashboardType[]) {
          dashboards[type] = { ...dashboards[type], ...(p.dashboards?.[type] ?? {}), activeSavedViewId: null };
        }
        // A region persisted before REGIONS narrowed to ["US"] (e.g. "EU"
        // sitting in someone's localStorage) would otherwise crash the mock
        // lookup — coerce it back to the one valid region instead.
        const isValidRegion = (r: unknown): r is Region => REGIONS.includes(r as Region);
        const region = isValidRegion(p.region) ? p.region : REGIONS[0];
        const pins = Object.fromEntries(Object.entries(p.pins ?? {}).filter(([, r]) => isValidRegion(r)));
        return { ...current, ...p, dashboards, region, pins };
      },
      // dockOpen/libraryDockOpen persist (layout preferences) but logicOpen/
      // libraryOpen deliberately do not — the overlays are transient, and
      // persisting them would slide a drawer open over the dashboard on load
      // after you'd narrowed the window.
      partialize: (s) => ({
        region: s.region, theme: s.theme, dashboardType: s.dashboardType,
        dashboards: Object.fromEntries(
          Object.entries(s.dashboards).map(([k, v]) => [k, { layout: v.layout, hidden: v.hidden, savedViews: v.savedViews }]),
        ),
        pins: s.pins, dockOpen: s.dockOpen, libraryDockOpen: s.libraryDockOpen,
        railCollapsed: s.railCollapsed, densityOverride: s.densityOverride,
      }),
    },
  ),
);
