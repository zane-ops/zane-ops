import * as React from "react";
import z from "zod";
import { THEME_STORAGE_KEY } from "~/lib/constants";

const themeSchema = z.enum(["LIGHT", "DARK", "SYSTEM"]);
export type Theme = z.infer<typeof themeSchema>;

export type ThemeProviderProps = {
  children: React.ReactNode;
  defaultTheme?: Theme;
};

type ThemeContextValue = {
  theme: Theme;
  setTheme: (theme: Theme) => void;
};

const ThemeContext = React.createContext<ThemeContextValue | undefined>(
  undefined
);

export function getThemePreference(): Theme {
  const stored = localStorage.getItem(THEME_STORAGE_KEY);
  const parseResult = themeSchema.safeParse(stored);
  return parseResult.success ? parseResult.data : "SYSTEM";
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const [theme, setThemeState] = React.useState(getThemePreference());

  function setTheme(newTheme: Theme) {
    const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");

    if (newTheme === "DARK") {
      document.documentElement.dataset.theme = "dark";
      localStorage.setItem(THEME_STORAGE_KEY, "DARK");
    } else if (newTheme === "LIGHT") {
      document.documentElement.dataset.theme = "light";
      localStorage.setItem(THEME_STORAGE_KEY, "LIGHT");
    } else {
      document.documentElement.dataset.theme = darkQuery.matches
        ? "dark"
        : "light";
      localStorage.removeItem(THEME_STORAGE_KEY);
    }

    setThemeState(newTheme);
  }

  React.useEffect(() => {
    const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");

    const theme = getThemePreference();
    if (theme === "DARK") {
      document.documentElement.dataset.theme = "dark";
    } else if (theme === "LIGHT") {
      document.documentElement.dataset.theme = "light";
    } else {
      document.documentElement.dataset.theme = darkQuery.matches
        ? "dark"
        : "light";
    }
  }, []);

  React.useEffect(() => {
    const controller = new AbortController();

    window.addEventListener(
      "storage",
      (event) => {
        if (event.key === THEME_STORAGE_KEY) {
          if (event.newValue === null) {
            setTheme("SYSTEM");
          } else {
            const parseResult = themeSchema.safeParse(event.newValue);
            if (parseResult.success) {
              setTheme(parseResult.data);
            }
          }
        }
      },
      { signal: controller.signal }
    );

    return () => {
      controller.abort();
    };
  }, []);

  return <ThemeContext value={{ theme, setTheme }}>{children}</ThemeContext>;
}

export function useTheme() {
  const ctx = React.use(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within a ThemeProvider");
  return ctx;
}
