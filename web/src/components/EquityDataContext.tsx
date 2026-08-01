"use client";

import { createContext, useContext } from "react";
import type { EquityDerived } from "@/lib/derive-equity";

export const EquityDataContext = createContext<EquityDerived | null>(null);

export function useEquityDerived(): EquityDerived {
  const d = useContext(EquityDataContext);
  if (!d) throw new Error("useEquityDerived must be used inside <EquityDataContext.Provider>");
  return d;
}
