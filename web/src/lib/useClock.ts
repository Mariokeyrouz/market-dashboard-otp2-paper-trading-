"use client";

import { useEffect, useState } from "react";

/**
 * Wall clock (HH:MM:SS) plus a naive NYSE session flag (Mon–Fri, 9–16 local).
 * Shared by the header (narrow mode) and the left rail (wide/mid), so the
 * ticking logic lives in exactly one place.
 */
export function useClock() {
  const [clock, setClock] = useState("--:--:--");
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setClock(now.toLocaleTimeString("en-US", { hour12: false }));
      const h = now.getHours();
      const day = now.getDay();
      setOpen(day >= 1 && day <= 5 && h >= 9 && h < 16);
    };
    tick();
    const iv = setInterval(tick, 1000);
    return () => clearInterval(iv);
  }, []);
  return { clock, open };
}
