"use client";

import ReactGridLayout, { useContainerWidth, verticalCompactor } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

import { ELEMENTS } from "@/lib/elements/registry";
import { GRID_COLS, GRID_MARGIN, GRID_ROW_HEIGHT } from "@/lib/layout/defaults";
import { useDashStore } from "@/lib/store";
import ElementFrame from "./ElementFrame";

export default function DashboardGrid() {
  const { width, containerRef, mounted } = useContainerWidth();
  const layout = useDashStore((s) => s.layout);
  const hidden = useDashStore((s) => s.hidden);
  const edit = useDashStore((s) => s.editMode);
  const setLayout = useDashStore((s) => s.setLayout);
  const hideElement = useDashStore((s) => s.hideElement);

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

  return (
    <div ref={containerRef}>
      {mounted && width > 0 && (
        <ReactGridLayout
          width={width}
          layout={fullLayout}
          gridConfig={{ cols: GRID_COLS, rowHeight: GRID_ROW_HEIGHT, margin: GRID_MARGIN, containerPadding: [0, 0] }}
          dragConfig={{ enabled: edit, handle: ".mws-drag" }}
          resizeConfig={{ enabled: edit, handles: ["se"] }}
          compactor={verticalCompactor}
          onLayoutChange={(l) => setLayout(l)}
        >
          {visible.map((e) => {
            const C = e.component;
            return (
              <div key={e.id} style={{ height: "100%" }}>
                <ElementFrame def={e} edit={edit} onHide={() => hideElement(e.id)}>
                  <C />
                </ElementFrame>
              </div>
            );
          })}
        </ReactGridLayout>
      )}
    </div>
  );
}
