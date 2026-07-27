import { useState, useEffect } from "react";

export function useTheme() {
  const [theme, setTheme] = useState("dark");

  useEffect(() => {
    const root = window.document.documentElement;
    root.classList.add("dark");
    root.classList.remove("light");
  }, []);

  return { theme: "dark", setTheme: () => {} };
}
