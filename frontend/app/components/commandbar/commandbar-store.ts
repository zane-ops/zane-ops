import { create } from "zustand";
import type { CommandBarView } from "~/components/commandbar/commandbar-types";

/**
 * The only views that have to be entered explicitly, the others are derived
 * by `useCommandBarState`: `action` from the search (`>` prefix) &
 * `resource` from the resource taken as the context.
 */
export type StoredCommandBarView = Exclude<
  CommandBarView["type"],
  "action" | "resource"
>;

export type CommandBarStore = {
  open: boolean;
  setOpen: (open: boolean) => void;
  toggle: () => void;
  view: StoredCommandBarView;
  setView: (view: StoredCommandBarView) => void;
};

export const useCommandBarStore = create<CommandBarStore>((set) => ({
  open: false,
  setOpen: (open) => set({ open }),
  toggle: () => set((state) => ({ open: !state.open })),
  view: "home",
  setView: (view) => set({ view })
}));
