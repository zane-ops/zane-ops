import * as React from "react";
import { THEME_COOKIE_KEY } from "~/lib/constants";
import { deleteCookie, getCookie, setCookie } from "~/utils";

export type Theme = "LIGHT" | "DARK" | "SYSTEM";

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
  return (
    (getCookie(THEME_COOKIE_KEY) as "LIGHT" | "DARK" | undefined) ?? "SYSTEM"
  );
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const [theme, setThemeState] = React.useState(getThemePreference());

  function setTheme(newTheme: Theme) {
    const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");

    if (newTheme === "DARK") {
      document.documentElement.dataset.theme = "dark";

      setCookie(THEME_COOKIE_KEY, "DARK");
    } else if (newTheme === "LIGHT") {
      document.documentElement.dataset.theme = "light";
      setCookie(THEME_COOKIE_KEY, "LIGHT");
    } else {
      document.documentElement.dataset.theme = darkQuery.matches
        ? "dark"
        : "light";
      deleteCookie(THEME_COOKIE_KEY);
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

  return <ThemeContext value={{ theme, setTheme }}>{children}</ThemeContext>;
}

export function useTheme() {
  const ctx = React.use(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within a ThemeProvider");
  return ctx;
}
