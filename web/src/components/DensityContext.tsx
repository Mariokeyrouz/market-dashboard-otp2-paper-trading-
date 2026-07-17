"use client";

import { createContext, useContext } from "react";

/**
 * True when the fit-to-height grid has compressed rows well below the design
 * height (27px). Tiles use it to shed secondary content deliberately —
 * annotation text inside scaled SVGs, italic taglines, explanatory notes —
 * instead of letting `overflow: hidden` crop whatever happens to sit lowest.
 * The rule: values survive, commentary goes.
 */
export const DensityContext = createContext(false);

export function useCompact(): boolean {
  return useContext(DensityContext);
}
