"use client";

import { createContext, useContext } from "react";
import type { TerminalDerived } from "@/lib/derive-terminal";

export const TerminalDataContext = createContext<TerminalDerived | null>(null);

export function useTerminalDerived(): TerminalDerived {
  const d = useContext(TerminalDataContext);
  if (!d) throw new Error("useTerminalDerived must be used inside <TerminalDataContext.Provider>");
  return d;
}
