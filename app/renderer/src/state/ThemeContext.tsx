import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { AppearanceMode } from "../../../shared/contracts";

interface ThemeContextValue {
  appearance: AppearanceMode;
  resolved: "light" | "dark";
  setAppearance(mode: AppearanceMode): void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [appearance, setAppearanceState] = useState<AppearanceMode>("system");
  const [resolved, setResolved] = useState<"light" | "dark">("dark");

  useEffect(() => {
    void window.newxau.settings.get().then((settings) => setAppearanceState(settings.appearance));
  }, []);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      const next = appearance === "system" ? (media.matches ? "dark" : "light") : appearance;
      document.documentElement.dataset.theme = next;
      setResolved(next);
    };
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [appearance]);

  const value = useMemo(
    () => ({
      appearance,
      resolved,
      setAppearance: (mode: AppearanceMode) => {
        setAppearanceState(mode);
        void window.newxau.settings.update({ appearance: mode });
      }
    }),
    [appearance, resolved]
  );
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("useTheme must be used inside ThemeProvider.");
  return value;
}
