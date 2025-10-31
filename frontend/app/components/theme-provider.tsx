import * as React from "react";
import z from "zod";
import { THEME_COOKIE_KEY } from "~/lib/constants";
import { deleteCookie, getCookie, setCookie } from "~/utils";

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

  React.useEffect(() => {
    if (!("cookieStore" in window)) return;

    const controller = new AbortController();
    window.cookieStore.addEventListener(
      "change",
      async (event) => {
        const deleted = event.deleted[0];
        const changed = event.changed[0];

        if (deleted?.name === THEME_COOKIE_KEY) {
          setTheme("SYSTEM");
        } else if (changed?.name === THEME_COOKIE_KEY) {
          const parseResult = themeSchema.safeParse(changed.value);
          if (parseResult.success) {
            setTheme(parseResult.data);
          }
        }
      },
      {
        signal: controller.signal
      }
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
