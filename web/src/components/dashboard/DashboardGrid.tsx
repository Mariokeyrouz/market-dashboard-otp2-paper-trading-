"use client";

import { useEffect, useMemo, useState } from "react";
import ReactGridLayout, { useContainerWidth, verticalCompactor } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

import { DataContext } from "@/components/DataContext";
import { DensityContext } from "@/components/DensityContext";
import { REGIONS, type Region } from "@/lib/data/types";
import { deriveAll, type Derived } from "@/lib/derive";
import { ELEMENTS } from "@/lib/elements/registry";
import { GRID_COLS, GRID_MARGIN, GRID_ROW_HEIGHT } from "@/lib/layout/defaults";
import { useDashStore } from "@/lib/store";
import ElementFrame from "./ElementFrame";

/** Space reserved below the grid for the footer badges (measured ~52px incl. margins). */
const FOOTER_ALLOWANCE = 58;
/** Fixed estimate of chrome above the grid (column top padding; no header in rail mode). */
const CHROME_ABOVE = 10;
/** Fit-to-height bounds: crush no further than MIN (then the page scrolls); MAX caps the
 *  stretch so tiles stay comfortably sized on tall screens instead of ballooning. */
const ROW_H_MIN = 20;
const ROW_H_MAX = 21;

export default function DashboardGrid() {
  const { width, containerRef, mounted } = useContainerWidth();
  const layout = useDashStore((s) => s.layout);
  const hidden = useDashStore((s) => s.hidden);
  const edit = useDashStore((s) => s.editMode);
  const region = useDashStore((s) => s.region);
  const pins = useDashStore((s) => s.pins);
  const setLayout = useDashStore((s) => s.setLayout);
  const hideElement = useDashStore((s) => s.hideElement);
  const setPin = useDashStore((s) => s.setPin);
  const clearPin = useDashStore((s) => s.clearPin);

  // deriveAll is pure, so every region can be derived up-front and each tile
  // handed its own slice — which is what makes per-element POV free: no element
  // component knows or cares that its context isn't the global one.
  // NOTE: cheap over static mock data; once real feeds land this becomes five
  // fetches and should go lazy (derive only the regions actually on screen).
  const byRegion = useMemo(
    () => Object.fromEntries(REGIONS.map((r) => [r, deriveAll(r)])) as Record<Region, Derived>,
    [],
  );

  const visible = ELEMENTS.filter((e) => !hidden.includes(e.id));
  // Guarantee every visible element has a layout entry (covers stale persisted
  // state after new elements ship); drop entries for hidden/unknown ids.
  const bottom = layout.reduce((m, l) => Math.max(m, l.y + l.h), 0);
  const fullLayout = [
    ...layout.filter((l) => visible.some((e) => e.id === l.i)),
    ...visible
      .filter((e) => !layout.some((l) => l.i === e.id))
      .map((e, k) => ({ i: e.id, ...e.defaultLayout, x: 0, y: bottom + k })),
  ];

  // Fit-to-height: scale the row unit so the grid lands inside the viewport
  // (browser zoom alone moves the target by hundreds of px), but CAP the stretch
  // at ROW_H_MAX so tiles stay comfortably sized rather than ballooning on tall
  // screens. When the grid ends up shorter than the viewport, `centerMargin`
  // splits the slack above/below so the board sits centered — a clean margin
  // instead of stretched-empty tiles. Frozen during edit mode: drags mutate the
  // row count mid-gesture, and rescaling under the cursor misplaces dropped tiles.
  const totalRows = fullLayout.reduce((m, l) => Math.max(m, l.y + l.h), 1);
  const [rowHeight, setRowHeight] = useState(GRID_ROW_HEIGHT);
  const [centerMargin, setCenterMargin] = useState(0);
  useEffect(() => {
    if (edit) return;
    const compute = () => {
      // Fixed chrome estimate (not the live top) so the centering margin we add
      // below can't feed back into the measurement.
      const marginY = GRID_MARGIN[1];
      const availTotal = window.innerHeight - CHROME_ABOVE - FOOTER_ALLOWANCE;
      const rh = Math.max(ROW_H_MIN, Math.min(ROW_H_MAX, (availTotal - (totalRows - 1) * marginY) / totalRows));
      const gridPx = totalRows * rh + (totalRows - 1) * marginY;
      setRowHeight(rh);
      setCenterMargin(Math.max(0, Math.floor((availTotal - gridPx) / 2)));
    };
    compute();
    window.addEventListener("resize", compute);
    return () => window.removeEventListener("resize", compute);
  }, [edit, totalRows]);

  return (
    <div ref={containerRef} style={{ marginTop: centerMargin, marginBottom: centerMargin }}>
      {mounted && width > 0 && (
        <DensityContext.Provider value={rowHeight < 22}>
        <ReactGridLayout
          // RGL's items memoize their geometry and miss rowHeight-only updates
          // (the container height reacts, tiles don't) — remount on change.
          // Cheap: rowHeight only changes on viewport resize, never mid-drag
          // (the fit effect is frozen during edit mode).
          key={`rh-${rowHeight.toFixed(1)}`}
          width={width}
          layout={fullLayout}
          gridConfig={{ cols: GRID_COLS, rowHeight, margin: GRID_MARGIN, containerPadding: [0, 0] }}
          dragConfig={{ enabled: edit, handle: ".mws-drag" }}
          resizeConfig={{ enabled: edit, handles: ["se"] }}
          compactor={verticalCompactor}
          onLayoutChange={(l) => setLayout(l)}
        >
          {visible.map((e) => {
            const C = e.component;
            const pin = e.crossRegion ? undefined : pins[e.id];
            return (
              <div key={e.id} style={{ height: "100%" }}>
                <DataContext.Provider value={byRegion[pin ?? region]}>
                  <ElementFrame
                    def={e}
                    edit={edit}
                    pin={pin}
                    onPin={(r) => (r ? setPin(e.id, r) : clearPin(e.id))}
                    onHide={() => hideElement(e.id)}
                  >
                    <C />
                  </ElementFrame>
                </DataContext.Provider>
              </div>
            );
          })}
        </ReactGridLayout>
        </DensityContext.Provider>
      )}
    </div>
  );
}
