import type { Layout, LayoutItem } from "react-grid-layout";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Region } from "./data/types";
import { ELEMENT_MAP } from "./elements/registry";
import { defaultLayout } from "./layout/defaults";

interface DashState {
  region: Region;
  layout: LayoutItem[];
  hidden: string[];
  editMode: boolean;
  logicOpen: boolean;
  setRegion: (r: Region) => void;
  setLayout: (l: Layout) => void;
  hideElement: (id: string) => void;
  showElement: (id: string) => void;
  resetLayout: () => void;
  setEditMode: (b: boolean) => void;
  setLogicOpen: (b: boolean) => void;
}

const strip = (l: readonly LayoutItem[]): LayoutItem[] =>
  l.map(({ i, x, y, w, h, minW, minH }) => ({ i, x, y, w, h, minW, minH }));

export const useDashStore = create<DashState>()(
  persist(
    (set) => ({
      region: "US",
      layout: defaultLayout(),
      hidden: [],
      editMode: false,
      logicOpen: false,
      setRegion: (region) => set({ region }),
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
            layout: [...s.layout, { i: id, ...def.defaultLayout, x: 0, y: bottom }],
          };
        }),
      resetLayout: () => set({ layout: defaultLayout(), hidden: [] }),
      setEditMode: (editMode) => set({ editMode }),
      setLogicOpen: (logicOpen) => set({ logicOpen }),
    }),
    {
      name: "mws_state_v1",
      partialize: (s) => ({ region: s.region, layout: s.layout, hidden: s.hidden }),
    },
  ),
);
