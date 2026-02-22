import { create } from "zustand";

type ToggleStateQueueStore = {
  queue: Set<string>;
  queueToggleItem: (newItem: string) => void;
  dequeueToggleItem: (item: string) => void;
};

export const useToggleStateQueueStore = create<ToggleStateQueueStore>(
  (set, get) => ({
    queue: new Set<string>(),
    queueToggleItem: (newItem) =>
      set((store) => ({
        queue: new Set(store.queue).add(newItem)
      })),
    dequeueToggleItem: (item) =>
      set((store) => {
        const items = new Set(store.queue);
        items.delete(item);
        return {
          queue: items
        };
      })
  })
);
