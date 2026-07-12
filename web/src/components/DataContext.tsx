"use client";

import { createContext, useContext } from "react";
import type { Derived } from "@/lib/derive";

export const DataContext = createContext<Derived | null>(null);

export function useDerived(): Derived {
  const d = useContext(DataContext);
  if (!d) throw new Error("useDerived must be used inside <DataContext.Provider>");
  return d;
}
