import { createContext, useContext, useEffect, useState } from "react";

const ThemeCtx = createContext({ theme: "system", setTheme: () => {}, resolved: "light" });
const mq = () => window.matchMedia("(prefers-color-scheme: dark)");

function read() {
  try {
    return localStorage.getItem("theme") || "system";
  } catch {
    return "system";
  }
}

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(read);
  const [systemDark, setSystemDark] = useState(() => mq().matches);
  useEffect(() => {
    const m = mq();
    const on = (e) => setSystemDark(e.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  const resolved = theme === "system" ? (systemDark ? "dark" : "light") : theme;
  useEffect(() => {
    document.documentElement.classList.toggle("dark", resolved === "dark");
  }, [resolved]);
  const setTheme = (t) => {
    setThemeState(t);
    try {
      localStorage.setItem("theme", t);
    } catch {
      /* private mode: theme just won't persist */
    }
  };
  return <ThemeCtx.Provider value={{ theme, setTheme, resolved }}>{children}</ThemeCtx.Provider>;
}

export const useTheme = () => useContext(ThemeCtx);
