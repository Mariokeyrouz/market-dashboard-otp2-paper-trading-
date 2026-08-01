import type { LayoutItem } from "react-grid-layout";
import type { ElementDef } from "../elements/registry";

export const GRID_COLS = 12;
export const GRID_ROW_HEIGHT = 27;
export const GRID_MARGIN: [number, number] = [7, 7];

/** The default Z-pattern layout, derived from a dashboard type's element registry. */
export function defaultLayout(elements: ElementDef[]): LayoutItem[] {
  return elements.map((e) => ({ i: e.id, ...e.defaultLayout }));
}
