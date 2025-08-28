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
  toggleTheme: () => void;
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

  function toggleTheme() {
    const theme = getThemePreference();

    const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");
    switch (theme) {
      case "SYSTEM": {
        setCookie(THEME_COOKIE_KEY, "DARK");
        break;
      }
      case "DARK":
        setCookie(THEME_COOKIE_KEY, "LIGHT");
        break;
      case "LIGHT":
        deleteCookie(THEME_COOKIE_KEY);
        break;
    }

    const newTheme = getThemePreference();
    if (newTheme === "DARK") {
      document.documentElement.dataset.theme = "dark";
    } else if (newTheme === "LIGHT") {
      document.documentElement.dataset.theme = "light";
    } else {
      document.documentElement.dataset.theme = darkQuery.matches
        ? "dark"
        : "light";
    }

    setThemeState(newTheme);
  }

  console.log({
    theme
  });
  return <ThemeContext value={{ theme, toggleTheme }}>{children}</ThemeContext>;
}

export function useTheme() {
  const ctx = React.use(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within a ThemeProvider");
  return ctx;
}
