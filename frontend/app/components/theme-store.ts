import * as React from "react";
import z from "zod";
import { create } from "zustand";
import { THEME_STORAGE_KEY } from "~/lib/constants";

const themeSchema = z.enum(["LIGHT", "DARK", "SYSTEM"]);
export type Theme = z.infer<typeof themeSchema>;

export function getThemePreference(): Theme {
  const stored = localStorage.getItem(THEME_STORAGE_KEY);
  const parseResult = themeSchema.safeParse(stored);
  return parseResult.success ? parseResult.data : "SYSTEM";
}

/**
 * `SYSTEM` follows the OS preference, so it is stored as the *absence*
 * of a stored preference.
 */
function applyTheme(theme: Theme) {
  if (theme === "SYSTEM") {
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)");
    document.documentElement.dataset.theme = prefersDark.matches
      ? "dark"
      : "light";
    localStorage.removeItem(THEME_STORAGE_KEY);
    return;
  }

  document.documentElement.dataset.theme = theme === "DARK" ? "dark" : "light";
  localStorage.setItem(THEME_STORAGE_KEY, theme);
}

type ThemeStore = {
  theme: Theme;
  setTheme: (theme: Theme) => void;
};

export const useThemeStore = create<ThemeStore>((set) => ({
  theme: "SYSTEM",
  setTheme: (theme) => {
    applyTheme(theme);
    set({ theme });
  }
}));

/**
 * Applies the stored preference on mount and keeps the theme in sync
 * with the other tabs. Should be called once, at the root of the app.
 */
export function useThemeSync() {
  React.useEffect(() => {
    const effectiveTheme = getThemePreference();
    useThemeStore.setState({
      theme: effectiveTheme
    });
    applyTheme(effectiveTheme);
  }, []);

  React.useEffect(() => {
    const controller = new AbortController();
    const { setTheme } = useThemeStore.getState();

    window.addEventListener(
      "storage",
      (event) => {
        if (event.key !== THEME_STORAGE_KEY) {
          return;
        }

        if (event.newValue === null) {
          setTheme("SYSTEM");
          return;
        }

        const parseResult = themeSchema.safeParse(event.newValue);
        if (parseResult.success) {
          setTheme(parseResult.data);
        }
      },
      { signal: controller.signal }
    );

    return () => {
      controller.abort();
    };
  }, []);
}
