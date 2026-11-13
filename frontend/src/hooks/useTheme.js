"use client";

import { useTheme as useNextTheme } from "next-themes";
import { useEffect, useState } from "react";

/**
 * useTheme hook — authoritative theme hook for AI Site Studio.
 * Wraps next-themes with SSR/hydration safety and helper flags.
 * Supports: 'light' | 'dark' | 'system'.
 */
export function useTheme() {
  const { theme, setTheme, resolvedTheme, systemTheme } = useNextTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return {
    theme: mounted ? (theme || "system") : "dark",
    setTheme,
    resolvedTheme: mounted ? (resolvedTheme || "dark") : "dark",
    systemTheme,
    isDark: mounted ? resolvedTheme === "dark" : true,
    isMounted: mounted,
  };
}

export default useTheme;
