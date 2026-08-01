"use client";

import { getDashboardDef, type DashboardTypeDef } from "./dashboards";
import { useDashStore } from "./store";

/** The active dashboard type's full definition (elements, region-lens flag, Logic copy). */
export function useDashboardDef(): DashboardTypeDef {
  const type = useDashStore((s) => s.dashboardType);
  return getDashboardDef(type);
}
