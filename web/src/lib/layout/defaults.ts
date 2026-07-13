import type { LayoutItem } from "react-grid-layout";
import { ELEMENTS } from "../elements/registry";

export const GRID_COLS = 12;
export const GRID_ROW_HEIGHT = 27;
export const GRID_MARGIN: [number, number] = [7, 7];

/** The default Z-pattern layout, derived from the element registry. */
export function defaultLayout(): LayoutItem[] {
  return ELEMENTS.map((e) => ({ i: e.id, ...e.defaultLayout }));
}
